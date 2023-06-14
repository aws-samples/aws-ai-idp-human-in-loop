# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import os
import json
import logging
import boto3
from boto3.dynamodb.types import TypeDeserializer
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

s3 = boto3.resource('s3')
snsClient = boto3.client('sns')
ddb = boto3.client('dynamodb')
deserializer = TypeDeserializer()

_sns_topic_arn =  os.environ.get('ALL_PAGES_COMPLETE_SNS_TOPIC_ARN')
_tracking_table = os.environ.get('SMGT_DYNAMO_TABLE_NAME')


dbDynoSelect = f"SELECT pages_sent FROM \"{_tracking_table}\" WHERE job_id=?"
dbDynoUpdate = f"UPDATE \"{_tracking_table}\" SET pages_sent=? WHERE job_id=?"


def lambda_handler(event, context):
    logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
    logger.info(json.dumps(event))

    # go grab the JSON file and extract textract Job ID and input S3 prefix to PDFs
    response = getJobIdfromJSON(event)
    jobId = response[0]
    inputS3Prefix = response[1] 
    inputKey = response[2]

    if len(jobId) == 0:
        logger.error("Unable to find textract JobId in JSON SMGT output")
        return
    
    # go get pages left with the job ID from DynamoDB
    pagesLeft = getPDFPagesLeft(jobId)
    
    # decrement pages left and update row in DynamoDB, then delete PDF page from S3
    pagesLeft -= 1
    updatetPDFPagesLeft(jobId,pagesLeft) 
    
    deletePDFPage(jobId, inputKey)

    # notify customer via SNS topic that job review has been completed
    if pagesLeft == 0 :
        sendSNSPagesComplete(jobId)

   
    return


# Job ID is located in JSON file that contains the annotations. Fist we need to load the meta file
# found under consolidation-request location, then from here we can find the location to the JSON file
# that contains the annotation output and the Job ID.
# in addition the meta file that contains the location of the textract output from GT, also contains
# the single paged PDF(TIFF) that will be removed.
def getJobIdfromJSON(event):
    
    try:
        bucketfileObjURI = event['payload']['s3Uri']
        parsedS3uri = urlparse(bucketfileObjURI, allow_fragments=False)
        bucket = parsedS3uri.netloc
        fileObjKey = parsedS3uri.path.lstrip('/')
        obj = s3.Object(bucket, fileObjKey)
        gtOutputDoc = obj.get()['Body'].read().decode('utf-8') 
        annotationData = json.loads(gtOutputDoc)[0]['annotations'][0]['annotationData']['content']
        answerFile = json.loads(annotationData)['answerFiles'][0]
        answerPrefix = json.loads(annotationData)['answerPrefix']
        answerKey = answerPrefix + '/' + answerFile
        
        inputFile = json.loads(annotationData)['inputFiles'][0]
        inputPrefix = json.loads(annotationData)['inputPrefix']
        inputKey = inputPrefix + '/page/' + inputFile
    except Exception as e:
        logger.error("Unable to find meta JSON file containing path to Textract/GT output and path to single page PDF(TIFF)")
        logger.error(e)
        return ""

    try:

        obj = s3.Object(bucket, answerKey)
        texttactAnnotation = obj.get()['Body'].read().decode('utf-8')
        jobId = json.loads(texttactAnnotation)['JobId']


        return jobId, bucketfileObjURI, inputKey
    
    except Exception as e:
        logger.error("Unable to find Textract/GT JSON file containing Job ID")
        logger.error(e)
        return ""


def getPDFPagesLeft(jobId):
    try:
        ddbresponse = ddb.execute_statement(Statement=dbDynoSelect, Parameters=[
                                                                    {'S': f"{jobId}"}])                                         
        
        deserialized_document = {k: deserializer.deserialize(v) for k, v in ddbresponse['Items'][0].items()}
        pagesLeft = int(deserialized_document['pages_sent'])
    except Exception as e:
        logger.error(e)
        return 1

    return pagesLeft


def updatetPDFPagesLeft(jobId, page_left):
    try:
        ddbresponse = ddb.execute_statement(Statement=dbDynoUpdate, Parameters=[
                                                                    {'N': f"{page_left}"},
                                                                    {'S': f"{jobId}"}])  
    except Exception as e:
        logger.error("Unable to update pages left count for job ID in DynamoDB")
        logger.error(e)



def deletePDFPage(jobId, inputS3Object):
# Delete generated PDF or Image page from S3
    try:
        s3UrlParse = urlparse(inputS3Object, allow_fragments=False)
        bucket = s3UrlParse.netloc
        basePathtoGeneratePage = s3UrlParse.path.lstrip('/')
        s3.Object(bucket, basePathtoGeneratePage).delete()
        logger.info(basePathtoGeneratePage + '-- Sucessfully deleted')

    except Exception as e:
        logger.error("Unable to delete single PDF/TIFF pages that were generated for GroundTruth.")
        logger.error(e)

    return

def sendSNSPagesComplete(jobId):
    
    # with all pages now reviewed from Job, sent notification to customer
    try:
        snsClient.publish(
            TopicArn=_sns_topic_arn,
            Message=f"Job {jobId} has completed reviewing all sent pages.",
            Subject="Job Complete"
        )
        
    except Exception as e:
        logger.error("Unable to send SNS message")
        logger.error(e) 
    
    return

if __name__ == "__main__":   
    #event={"version":"2018-10-06","labelingJobArn":"arn:aws:sagemaker:eu-central-1:710096454740:labeling-job/idp-groundtruth-fccf52ef-e54d-499a-8cc9-f1280800e0a5","payload":{"s3Uri":"s3://idp-textract-output-bucket-8f2896c0-c1d3-5de7-9bbc-83e1f95efe27/idp-groundtruth-fccf52ef-e54d-499a-8cc9-f1280800e0a5/annotations/consolidated-annotation/consolidation-request/iteration-1/2023-04-17_15_48_07.json"},"labelAttributeName":"idp","roleArn":"arn:aws:iam::710096454740:role/idp-groundtruth-service-role","outputConfig":"s3://idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb/idp-groundtruth-fccf52ef-e54d-499a-8cc9-f1280800e0a5/annotations","maxHumanWorkersPerDataObject":1}
    event={"version":"2018-10-06","labelingJobArn":"arn:aws:sagemaker:eu-central-1:710096454740:labeling-job/idp-groundtruth-fccf52ef-e54d-499a-8cc9-f1280800e0a5","payload":{"s3Uri":"s3://idp-textract-output-bucket-8f2896c0-c1d3-5de7-9bbc-83e1f95efe27/idp-groundtruth-5d8ae0d2-246f-4734-8451-58d1b0ba490b/annotations/consolidated-annotation/consolidation-request/iteration-1/2023-04-19_18:19:40.json"},"labelAttributeName":"idp","roleArn":"arn:aws:iam::710096454740:role/idp-groundtruth-service-role","outputConfig":"s3://idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb/idp-groundtruth-fccf52ef-e54d-499a-8cc9-f1280800e0a5/annotations","maxHumanWorkersPerDataObject":1}
    context={} 
    response = lambda_handler(event,context)
    print (response)

   