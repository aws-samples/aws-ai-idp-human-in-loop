# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import json
import boto3
import uuid
import logging
import os
logger = logging.getLogger(__name__)

client = boto3.client('sagemaker')

'''
Lambda code to check the Amazon SageMaker GroundTruth Labeling job status as well as create new job based on the Failed or Stopped Labelling job Status.
This Lambda will be trigger by the Amazon EventBridge 
'''

'''
Get all the env variables 
'''
#Labeling Job name
_job_name = os.environ.get('TEXTRACT_LABELING_JOB_NAME')
#ARN for SNS Topic
_sns_topic_arn =  os.environ.get('SNS_TOPIC_MANIFEST_GO_ARN')
#S3 outout path to store back the output
_s3_output_path = os.environ.get('S3_OUTPUT_PATH')
#Role ARN for Labeling job
_role_arn = os.environ.get('TEXTRACT_LABELING_JOB_ROLE_ARN')
#Ground Truth Lableling workforce Private team arn
_work_team_arn = os.environ.get('WORK_TEAM_ARN')
#S3 path for the Template
_ui_template_s3_url = os.environ.get('UI_TEMPLATE_S3_URL')
#Pre anotation Lambda ARN
_pre_human_task_lambda_arn = os.environ.get('PRE_HUMAN_TASK_LAMBDA_ARN')
#Task time in seconds . The TaskTimeLimitInSec for Custom task type cant be greater than 28800 seconds
_task_time_limit_in_seconds = os.environ.get('TASK_TIME_LIMIT_IN_SECONDS',28800)
#Lambda Post Anotation ARN
_post_human_task_lambda_arn = os.environ.get('POST_HUMAN_TASK_LAMBDA_ARN')
#Tags
_tags = os.environ.get('TEXTRACT_TAGS',{})
#one page review by only 1 worker
_human_workers_per_object = os.environ.get('HUMAN_WORKERS_PER_OBJECT', 1)
#max 1500 pages reviewed concurrently, this number should directly coorelate to number of workers available
_concurrent_tasks = os.environ.get('CONCURRENT_TASKS', 1000)


def lambda_handler(event, context):
    log_level = os.environ.get('LOG_LEVEL', 'INFO')    
    logger.setLevel(log_level)
    logger.info(json.dumps(event))

    '''
    Get the current labeling job status 
    '''
    smgt_job_list = get_labeling_job_status()
    logger.info(smgt_job_list)
    start_job_flag = False
    if smgt_job_list is not None and smgt_job_list['LabelingJobSummaryList']:
        '''
        Check the GroundTruth Labeling job status
        '''
        job_status = smgt_job_list['LabelingJobSummaryList'][0]['LabelingJobStatus']
        if any(item in job_status for item in ['Failed','Stopped','Stopping']):
            start_job_flag = True
        else:
            logger.info(smgt_job_list['LabelingJobSummaryList'][0]['LabelingJobName'] + ' is running')
            return {'statusCode': 200, 'body': smgt_job_list['LabelingJobSummaryList'][0]['LabelingJobName'] + ' is running'}
    else:
        start_job_flag = True
    
    if start_job_flag:
        '''
        Create new labeling job
        '''
        create_job = create_labeling_job()
        logger.info('New Labeling Job created successfully')
        return {'statusCode': 200, 'body': json.dumps(create_job)}
 
'''
Get the latest job status
'''   
def get_labeling_job_status():
    response = client.list_labeling_jobs(
        NameContains=_job_name,
        SortBy='CreationTime',
        MaxResults=1,
        SortOrder='Descending'
        )
    return response


'''
Create new labeling job.
'''
def create_labeling_job():
    print(_tags)
    response = client.create_labeling_job(
        LabelingJobName=f"{_job_name}-{str(uuid.uuid4())}",
        LabelAttributeName='idp',
        InputConfig={'DataSource': {
                        'SnsDataSource': {
                            'SnsTopicArn': _sns_topic_arn
                            }
                        }
                    },
        OutputConfig={'S3OutputPath': _s3_output_path},
        RoleArn=_role_arn,
        HumanTaskConfig={
                'WorkteamArn': _work_team_arn,
                'UiConfig': {
                    'UiTemplateS3Uri': _ui_template_s3_url
                },
                'PreHumanTaskLambdaArn': _pre_human_task_lambda_arn,
                'TaskTitle': 'Amazon Textract IDP Human Review',
                'TaskDescription': 'Amazon Textract IDP Human Review',
                'NumberOfHumanWorkersPerDataObject': int(_human_workers_per_object),
                'MaxConcurrentTaskCount': int(_concurrent_tasks),
                'TaskTimeLimitInSeconds': int(_task_time_limit_in_seconds),
                'AnnotationConsolidationConfig': {
                    'AnnotationConsolidationLambdaArn': _post_human_task_lambda_arn                    
                },
            },
        Tags=[json.loads(_tags)])
    return response
