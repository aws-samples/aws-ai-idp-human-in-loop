# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import os
import json
import logging
import boto3
from boto3.dynamodb.types import TypeDeserializer
from urllib.parse import urlparse
from S3Functions import S3


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


    labeling_job_arn = event["labelingJobArn"]
    label_attribute_name = event["labelAttributeName"]

    label_categories = None
    if "label_categories" in event:
        label_categories = event["labelCategories"]
        print(" Label Categories are : " + label_categories)

    payload = event["payload"]
    role_arn = event["roleArn"]

    kms_key_id = None
    if "kmsKeyId" in event:
        kms_key_id = event["kmsKeyId"]

    returnAnnots = do_consolidation(labeling_job_arn, payload, label_attribute_name)


    # go grab the JSON file and extract textract Job ID and input S3 prefix to PDFs
    response = getJobIdfromJSON(event)
    jobId = response[0]
    inputS3Prefix = response[1] 
    inputKey = response[2]

    if len(jobId) == 0:
        logger.error("Unable to find textract JobId in JSON SMGT output")
        logger.info('No job ID found, exiting - returning')
        return
    
    # go get pages left with the job ID from DynamoDB
    pagesLeft = getPDFPagesLeft(jobId)
    
    logger.info(str(pagesLeft) + '-- Pages left')


    # decrement pages left and update row in DynamoDB, then delete PDF page from S3
    pagesLeft -= 1
    logger.info('Updating pages count')
    updatetPDFPagesLeft(jobId,pagesLeft) 
    
    logger.info('Deleting PDF page')
    deletePDFPage(jobId, inputKey)

    # notify customer via SNS topic that job review has been completed
    if pagesLeft == 0 :
        logger.info('Sending SNS notification')
        sendSNSPagesComplete(jobId)
   

    logger.info('Exiting - Returning ' + json.dumps(returnAnnots))
    return returnAnnots



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

def do_consolidation(labeling_job_arn, payload, label_attribute_name):
    """
        Core Logic for consolidation

    :param labeling_job_arn: labeling job ARN
    :param payload:  payload data for consolidation
    :param label_attribute_name: identifier for labels in output JSON
    :param s3_client: S3 helper class
    :return: output JSON string
    """

    # Extract payload data
    if "s3Uri" in payload:
        s3_ref = payload["s3Uri"]
        path_parts = s3_ref.replace("s3://", "").split("/")
        bucket = path_parts.pop(0)
        keyObjName = "/".join(path_parts)

        s3_object = s3.Object(bucket_name=bucket, key=keyObjName)
        
        payload = json.loads(s3_object.get().get('Body').read().decode('utf-8'))


    # Payload data contains a list of data objects.
    # Iterate over it to consolidate annotations for individual data object.
    consolidated_output = []
    success_count = 0  # Number of data objects that were successfully consolidated
    failure_count = 0  # Number of data objects that failed in consolidation

    for p in range(len(payload)):
        response = None
        try:
            dataset_object_id = payload[p]['datasetObjectId']
            log_prefix = "[{}] data object id [{}] :".format(labeling_job_arn, dataset_object_id)
            #print("{} Consolidating annotations BEGIN ".format(log_prefix))

            annotations = payload[p]['annotations']
            #print("{} Received Annotations from all workers {}".format(log_prefix, annotations))

 

            # Notice that, no consolidation is performed, worker responses are combined and appended to final output
            # You can put your consolidation logic here
            consolidated_annotation = {"annotationsFromAllWorkers": annotations} # TODO : Add your consolidation logic

            # Build consolidation response object for an individual data object
            response = {
                "datasetObjectId": dataset_object_id,
                "consolidatedAnnotation": {
                    "content": {
                        label_attribute_name: consolidated_annotation
                    }
                }
            }

            success_count += 1
            #print("{} Consolidating annotations END ".format(log_prefix))

            # Append individual data object response to the list of responses.
            if response is not None:
                consolidated_output.append(response)

        except:
            failure_count += 1
            print(" Consolidation failed for dataobject {}".format(p))

    #print("Consolidation Complete. Success Count {}  Failure Count {}".format(success_count, failure_count))


    return consolidated_output

if __name__ == "__main__":   
    event={"version":"2018-10-06"}
    context={} 
    response = lambda_handler(event,context)
    print (response)
