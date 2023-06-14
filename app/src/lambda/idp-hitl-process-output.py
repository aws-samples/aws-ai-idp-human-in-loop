# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import os
import boto3
import json
import time
import logging
import mimetypes
from S3Functions import S3
from Manifests import tManifest
from pypdf import PdfReader, PdfWriter
from PIL import Image

# Mime types for Amazon Textract supported file formats
PDF_MIME='application/pdf'
PNG_MIME='image/png'
JPG_MIME='image/jpeg'
TIF_MIME='image/tiff'

# Initialize environment variables
_gt_sns_topic = os.environ.get('GT_SNS_TOPIC_ARN')
_confidence_thresh_ssm = os.environ.get('THRESHOLD_SSM')
_tracking_table = os.environ.get('TEXTRACT_GT_TABLE')
_kms_key = os.environ.get('BUCKET_KMS_KEY')
log_level = os.environ.get('LOG_LEVEL', 'INFO')

logger = logging.getLogger(__name__)
ssm = boto3.client('ssm')
sns = boto3.client('sns')
ddb = boto3.client('dynamodb')

'''
Writes file to S3 (probably move this to S3Functions)
'''
def write_to_s3(data, bucket, key)  -> None: 
    client = boto3.client('s3')               
    client.put_object(Body=json.dumps(data),
                  Bucket=bucket,
                  Key=key)

def extract_page(**kwargs) -> dict:
    doc_s3 = kwargs["doc_s3"]
    doc = kwargs["doc"]    
    bucket = kwargs['bucket']
    prefix = kwargs['prefix']
    page_num=kwargs["page_num"]
    try:
        '''
        Download the document into Lambda /tmp to find the mime type
        '''
        filename = os.path.basename(doc)
        temp_file = f'/tmp/{filename}'
        logger.info("Downloading document to /tmp/")
        s3_client = S3(bucket=doc_s3, log_level=log_level)
        s3_client.download_file(source_object=doc, destination_file=temp_file)

        file_mime = mimetypes.guess_type(temp_file, strict=True)[0]
        file_extension = mimetypes.guess_all_extensions(file_mime, strict=True)[0]
        logger.debug(f"File mime type is {file_mime} and extension is {file_extension}")

        s3_doc_client = S3(bucket=bucket, log_level=log_level)        
        destination_prefix = f"{prefix}/pages/{page_num}/page/{page_num}{file_extension}"

        # Handle image files
        if file_mime in [PNG_MIME, JPG_MIME]:            
            s3_doc_client.upload_file(source_file=temp_file, 
                                      destination_object=destination_prefix, 
                                      ExtraArgs={'ContentType': file_mime})                                
        # Handle PDF files
        elif file_mime == PDF_MIME:
            reader = PdfReader(temp_file)
            writer = PdfWriter()
            writer.add_page(reader.pages[page_num - 1]) # Extract the specific page
            with open(f"/tmp/{page_num}.pdf", "wb") as out:
                writer.write(out)
            s3_doc_client.upload_file(source_file=f"/tmp/{page_num}{file_extension}", 
                                      destination_object=destination_prefix, 
                                      ExtraArgs={'ContentType': file_mime})                             
        # Handle TIF files
        elif file_mime == TIF_MIME:
            img = Image.open(temp_file)
            img.seek(page_num - 1)
            img.save(f"/tmp/{page_num}{file_extension}")
            s3_doc_client.upload_file(source_file=f"/tmp/{page_num}{file_extension}", 
                                      destination_object=destination_prefix, 
                                      ExtraArgs={'ContentType': file_mime})            
        else:
            logger.error(f"Un-supported file type {file_mime} for s3://{doc_s3}/{doc}")
            raise Exception(f"Un-supported file type {file_mime} for s3://{doc_s3}/{doc}")
        
        os.remove(temp_file)     
        logger.debug(f"Page {page_num}{file_extension} written into {destination_prefix}")
        return {'source': f'Amazon Textract review document {filename} page number {page_num}',
                'fileExtension': file_extension, 
                'inputS3Prefix': f"s3://{bucket}/{prefix}/pages/{page_num}",
                'outputS3Prefix': f"s3://{bucket}/{prefix}/pages/{page_num}",
                'currPageNumber': page_num,
                'numberOfPages': 1}
        
    except Exception as e:
        logger.error(e)
        raise Exception(e)

def check_confidence(schema, threshold, doc_s3, doc, bucket, prefix, job_id, page_num) -> dict:
    low_confidence = False
    response = {}

    logger.info(f"Writing {page_num}.json file to S3")
    write_to_s3(schema.toJson, bucket, f"{prefix}/pages/{page_num}/textract-result/{page_num}.json")

    logger.info(f"Checking confidence scores for page {page_num} for Textract JobId {job_id}")
    for p_block in schema.blocks:
        if p_block.get('BlockType') != "PAGE": #PAGE doesn't have confidence score
            if p_block.get('Confidence') < threshold and p_block.get('BlockType') in ["WORD", "TABLE", "CELL", "MERGED_CELL", "KEY_VALUE_SET", "SIGNATURE"]:
                low_confidence = True
                break    

    if low_confidence:
        logger.info(f"Found low scores in page {page_num}, extracting page")
        response = extract_page(doc_s3=doc_s3, 
                                doc=doc,                                                 
                                bucket=bucket, 
                                prefix=prefix, 
                                page_num=page_num)
        response['outputKmsKeyId'] = _kms_key
        response['textractJobId'] = job_id
        response['configuration'] = { 'defaultConfidenceThreshold': threshold }
    return response

def split_per_page(**kwargs) -> list[dict]:    
    doc_s3 = kwargs["doc_bucket"]
    doc = kwargs["document"]
    bucket = kwargs["bucket"]
    prefix = kwargs["prefix"]
    job_id = kwargs['textractJobId']
    review_pages = list() 

    try:
        '''
        Initialize S3 client helper
        '''
        s3 = S3(bucket=bucket, log_level=log_level)        
        ssm_resp = ssm.get_parameter(Name=_confidence_thresh_ssm)
        confidence_threshold = float(ssm_resp['Parameter']['Value'])
        page_blocks = list()
        page_num = 0
        output_counter = 1
        main_schema = None
        total_pages = None        
        while True:
            try:
                textract_content = s3.get_object_content(key=f"{prefix}/{output_counter}")
                textract_data = json.loads(textract_content.decode())
                if not main_schema and not total_pages:
                    main_schema = tManifest(textract_data)                
                    total_pages = textract_data.get('DocumentMetadata').get('Pages')
                output_counter = output_counter + 1
                for block in textract_data.get('Blocks'):
                    if block.get('BlockType') == "PAGE":
                        '''
                        Start writing a new page
                        ''' 
                        if page_blocks:                        
                            main_schema.add_blocks(page_blocks)
                            response = check_confidence(schema=main_schema, 
                                                        threshold=confidence_threshold, 
                                                        doc_s3=doc_s3, 
                                                        doc=doc,                                                 
                                                        bucket=bucket, 
                                                        prefix=prefix, 
                                                        job_id=job_id,
                                                        page_num=page_num)                        
                            if response:
                                review_pages.append(response)                            
                            page_blocks.clear()
                        page_num = block.get('Page', 1)     #sync API response doesn't contain 'Page' so it will default to 1
                        page_blocks.append(block)                                            
                    else:
                        page_blocks.append(block)
            except Exception as e:
                logger.error(e)
                # no more files to read break and exit
                break
        # The last page
        if page_blocks and page_num == total_pages:
            main_schema.add_blocks(page_blocks)
            response = check_confidence(schema=main_schema, 
                                        threshold=confidence_threshold, 
                                        doc_s3=doc_s3, 
                                        doc=doc,                                                 
                                        bucket=bucket, 
                                        prefix=prefix, 
                                        job_id=job_id,
                                        page_num=page_num)                        
            if response:
                review_pages.append(response)                            
            page_blocks.clear()
        return review_pages
    except Exception as e:        
        logger.error(e)
        raise Exception(e)

def send_to_gt(tasks) -> None:
    sent_task = 0    
    for task in tasks:
        logger.info(f"Sending task to Ground Truth for {task.get('textractJobId')} page at {task.get('inputS3Prefix')}")
        try:
            sns.publish(TopicArn=_gt_sns_topic, Message=json.dumps(task))    
            sent_task = sent_task + 1
        except Exception as e:
            logger.error(e)
    try:
        # make an entry to the tracking table
        job_id = tasks[0].get('textractJobId')
        stmt = f"INSERT INTO \"{_tracking_table}\" VALUE {{'job_id' : ?, 'pages_sent' : ?, 'date_sent': ?}}"
        logger.debug(stmt)
        ddresponse = ddb.execute_statement(Statement=stmt, Parameters=[
            {'S': str(job_id)},
            {'N': str(sent_task)},
            {'N': str(int(time.time()))}
        ])
        logger.debug(json.dumps(ddresponse))
        logger.info(f"Sent {sent_task} pages to Ground Truth for review")
    except Exception as e:
        logger.error(e)

def lambda_handler(event, context):        
    logger.setLevel(log_level)
    logger.info(json.dumps(event))

    if not _gt_sns_topic or not _confidence_thresh_ssm:
        logger.error("A SageMaker Ground Truth SNS Topic for streaming job and confidence threshold SSM Parameter are required")
        raise Exception("A SageMaker Ground Truth SNS Topic and Confidence threshold are required")

    '''
    location of the output bucket and prefix since SNS Notification
    Doesn't contian that info - https://docs.aws.amazon.com/textract/latest/dg/async-notification-payload.html
    '''
    output_bucket = os.environ.get('TEXTRACT_OUTPUT_BKT')
    output_prefix = f"{os.environ.get('TEXTRACT_OUTPUT_PREFIX').rstrip('/')}/" if os.environ.get('TEXTRACT_OUTPUT_PREFIX') else ""

    '''
    Grab details from the SNS Event notification
    '''
    message = json.loads(event['Records'][0]['Sns']['Message'])
    jobId = message['JobId']    
    status= message['Status']
    document_bucket = message['DocumentLocation']['S3Bucket']
    document = message['DocumentLocation']['S3ObjectName']

    if status != "SUCCEEDED":
        logger.info(f"Textract Job status is {status}. Skipping processing...")
        return
    try:
        tasks = split_per_page(bucket=output_bucket, 
                               prefix=f"{output_prefix}{jobId}",
                               doc_bucket=document_bucket,
                               document=document,
                               textractJobId=jobId)
        if tasks:
            send_to_gt(tasks)
    except Exception as e:
        logger.error(e)        
    return event
