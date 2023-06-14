const { Stack, RemovalPolicy, Duration, Tags, CfnOutput } = require('aws-cdk-lib');
const dynamodb = require('aws-cdk-lib/aws-dynamodb');
const s3 = require('aws-cdk-lib/aws-s3');
const s3deploy = require('aws-cdk-lib/aws-s3-deployment');
const sns = require('aws-cdk-lib/aws-sns');
const iam = require('aws-cdk-lib/aws-iam');
const lambda = require('aws-cdk-lib/aws-lambda');
const ssm = require('aws-cdk-lib/aws-ssm');
const { Rule, Schedule } = require('aws-cdk-lib/aws-events');
const {LambdaFunction} = require ('aws-cdk-lib/aws-events-targets');
const { SnsEventSource } = require('aws-cdk-lib/aws-lambda-event-sources');
const path = require('path');

class SMGTIdpStack extends Stack {

  constructor(scope, id, props) {
    super(scope, id, props);


    /**
     * Create an SSM Parameter store to store the confidence threshold
     * define confidence threshold value in .env file before deployment.
     * After deployment, you can update the value directly from SSM Console
     * or CLI.
     */    
    const thresholdSSM = new ssm.StringParameter(this, 'idp-textract-confidence-threshold', {
        description: 'SSM Parameter store to store the Textract confidence threshold',
        name: 'idp-textract-confidence-threshold',
        stringValue: process.env.TEXTRACT_CONFIDENCE_THRESHOLD
    });


    /**
     * Create Dynamo DB table to store and track Job Id and count pages reviewed.
     * data is used to automatically trigger an alert to customer informing them that all pages 
     * within a Job (All pages in a PDF) have been reviewed and completed withing SMGT.
     */
    const smgtDynamoTable = new dynamodb.Table(this, 'idp-groundtruth-review-tracking', {
        removalPolicy: RemovalPolicy.DESTROY,
        tableName: 'idp-groundtruth-review-tracking',
        partitionKey: {
            name: 'job_id',
            type: dynamodb.AttributeType.STRING
        },
        encryption: dynamodb.TableEncryption.AWS_MANAGED,
        writeCapacity: 5
    });
  
    /**
     * Set scaling appropriately, for low expected volume of documents scaling lines below can be commented with
     * default DynamoDB scaling properties
     */    
    const readScaling = smgtDynamoTable.autoScaleReadCapacity({minCapacity: 5, maxCapacity: 20});
    readScaling.scaleOnUtilization({ targetUtilizationPercent: 50 });

    const writeScaling = smgtDynamoTable.autoScaleWriteCapacity({ minCapacity: 5, maxCapacity: 20});
    writeScaling.scaleOnUtilization({ targetUtilizationPercent: 50 });

    /**
     * Create SNS topic that Textract will write Job information to. 
     * so that our Lambda function gets triggered and can then process the Textract output 
     */
    const smgtIdpTextractSNS = new sns.Topic(this, 'idp-textract-topic', {
      topicName: 'idp-textract-topic'                      
    });

    new CfnOutput(this, 'idp-textract-topic-arn', {
      value: smgtIdpTextractSNS.topicArn,
      description: 'Amazon SNS Topic for Amazon Textract',
      exportName: 'textractOutputSNSArn'
    });

    /**
     * Create SNS topic for SageMaker Ground Truth streaming job. 
     * Manifest messages are sent to this topic to start human review process.
     */
    const smgtManifestSNSTopic = new sns.Topic(this, 'idp-groundtruth-manifest-topic', {
      topicName: 'smgt-groundtruth-manifest-topic'
    });


    /**
     * Create SNS topic for customer notification. 
     * when all pages have been reviewed associated with a Textract Job ID
     */
    const smgtIdpAllPagesReviewedSNS = new sns.Topic(this, 'idp-groundtruth-consolidation-topic', {
      topicName: 'idp-groundtruth-consolidation-topic'                      
    });

    new CfnOutput(this, 'idp-groundtruth-consolidation-topic-arn', {
      value: smgtIdpAllPagesReviewedSNS.topicArn,
      description: 'Amazon SNS Topic for customer notifcation when all pages reviewed',
      exportName: 'AllPagesReviewedSNSArn'
    });

    /**
     * S3 buckets
     */

    /**
     *   Creates bucket that stores the HTML liquid template used by UI
    */
    const smgtHTMLTemplateBucket = new s3.Bucket(this, 'idp-groundtruth-tmpl', {
      bucketName: `idp-groundtruth-tmpl-${this.account}-${this.region}`,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,      
    });     


    /**
     * copy liquid template into S3 bucket
     */
    new s3deploy.BucketDeployment(this, 'save-template-file', {
      sources: [s3deploy.Source.asset('template')], 
      destinationBucket: smgtHTMLTemplateBucket,
    });


    /**
     *   Creates bucket for textract output
    */
    const smgtsagemakerTextractOutputS3 = new s3.Bucket(this, 'idp-textract-output-bucket', {
      bucketName: `idp-textract-output-bucket-${this.account}-${this.region}`,
      versioned: false,
      encryption: s3.BucketEncryption.KMS,
      bucketKeyEnabled: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      cors: [{
              allowedMethods: [
                s3.HttpMethods.GET,
                s3.HttpMethods.HEAD,
                s3.HttpMethods.POST,
                s3.HttpMethods.PUT
              ],
              allowedOrigins: ['*'],
              allowedHeaders: ['*'],
              exposedHeaders: [
                "Access-Control-Allow-Origin",
                "x-amz-server-side-encryption",
                "x-amz-request-id",
                "x-amz-id-2",
                "ETag"
              ],
              maxAge: 3000
            }]
    });   

    new CfnOutput(this, 'textract-output-bucket-name', {
      value: smgtsagemakerTextractOutputS3.bucketName,
      description: 'Amazon S3 output bucket for Amazon Textract',
      exportName: 'textractOutputBucketName'
    });


    /**
     * Role required for textract to send notifications to the SNS Topic
     */
    const textractSNSRole = new iam.Role(this, 'idp-textract-service-sns-role', {
      roleName: 'idp-textract-service-sns-role',
      assumedBy: new iam.ServicePrincipal('textract.amazonaws.com')
    });

    /* add policy to role */
    textractSNSRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      resources: [smgtIdpTextractSNS.topicArn],
      actions: ["sns:Publish"]
    }));

    new CfnOutput(this, 'idp-textract-sns-role', {
      value: textractSNSRole.roleArn,
      description: 'Amazon SNS Topic IAM Role for Amazon Textract',
      exportName: 'textractSNSRole'
    });

    /**
     * Create SMGT Job role with Sagemaker policy, used when creating the Job.
     */
    const smgtSageMakerRole = new iam.Role(this, 'idp-groundtruth-service-role', {
      roleName: 'idp-groundtruth-service-role',
      assumedBy: new iam.ServicePrincipal('sagemaker.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSageMakerGroundTruthExecution')],
      inlinePolicies:{
          "idp-s3-policy": new iam.PolicyDocument({
              statements: [                    
                  new iam.PolicyStatement({
                      sid: "IDPGTS3ServicesAccess",
                      effect: iam.Effect.ALLOW,
                      actions: [
                        "s3:DeleteObject",
                        "s3:GetObject",
                        "s3:PutObject"
                      ],
                      resources: [`${smgtsagemakerTextractOutputS3.bucketArn}/*`]
                  })
              ]
          }),
          "idp-kms-policy": new iam.PolicyDocument({
              statements:[
                  new iam.PolicyStatement({
                    sid: "IDPGTKMSAccess",
                    effect: iam.Effect.ALLOW,
                    actions: [
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey"
                    ],
                    resources: [
                      `arn:aws:kms:${this.region}:${this.account}:key/*`
                    ]
                })
              ]
            })
        }
    });

    /**
     * Lambda IAM Role
     */
    const lambdaRole = new iam.Role(this, 'idp-smgt-lambda-execution-role',{
                      roleName: 'idp-smgt-lambda-execution-role',
                      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
                      managedPolicies: [
                                          iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaVPCAccessExecutionRole"),
                                          iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole"),
                                          iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaSQSQueueExecutionRole")
                                      ],
                      inlinePolicies:{
                          "idp-sagemaker-policy": new iam.PolicyDocument({
                              statements: [                    
                                  new iam.PolicyStatement({
                                      sid: "IDPGTServicesAccess",
                                      effect: iam.Effect.ALLOW,
                                      actions: [
                                          "sagemaker:CreateLabelingJob",
                                          "sagemaker:ListLabelingJobs",
                                          "sagemaker:ListLabelingJobForWorkteam",
                                          "sagemaker:AddTags"
                                      ],
                                      resources: ["*"]
                                  })
                              ]
                          }),
                          "idp-s3-policy": new iam.PolicyDocument({
                              statements: [
                                  new iam.PolicyStatement({
                                      sid: "LambdaS3Access",
                                      effect: iam.Effect.ALLOW,
                                      actions: [
                                          "s3:ListBucket",
                                          "s3:DeleteObject",
                                          "s3:GetObject",
                                          "s3:PutObject",
                                          "s3:PutObjectAcl"
                                      ],
                                      resources: ["*"]
                                  })
                              ]
                          }),                          
                          "idp-sns-policy": new iam.PolicyDocument({
                              statements: [
                                  new iam.PolicyStatement({
                                      sid: "SNSPublishAccess",
                                      effect: iam.Effect.ALLOW,                                      
                                      actions: [
                                        "sns:Publish"
                                      ],
                                      resources: [
                                        smgtManifestSNSTopic.topicArn,
                                        smgtIdpAllPagesReviewedSNS.topicArn
                                      ]
                                  })
                              ]
                          }),   
                          "idp-ssm-policy": new iam.PolicyDocument({
                            statements: [
                                new iam.PolicyStatement({
                                    sid: "SSMParameterAccess",
                                    effect: iam.Effect.ALLOW,                                    
                                    actions: [
                                      "ssm:GetParameters",
                                      "ssm:GetParameter",
                                      "ssm:GetParametersByPath"
                                    ],
                                    resources: [thresholdSSM.parameterArn]
                                })
                            ]
                          }),                       
                          "idp-sagemaker-passrole-policy": new iam.PolicyDocument({
                              statements: [
                                  new iam.PolicyStatement({
                                      sid: "SMPassRole",
                                      effect: iam.Effect.ALLOW,
                                      actions: [
                                        "iam:PassRole"
                                      ],
                                      resources: [smgtSageMakerRole.roleArn]
                                  })
                              ]
                          }),
                          "idp-lambda-dynamodb-policy": new iam.PolicyDocument({
                            statements: [                    
                                new iam.PolicyStatement({
                                    sid: "DynamoDBTableAccess",
                                    effect: iam.Effect.ALLOW,
                                    actions: [
                                        "dynamodb:PartiQLInsert",
                                        "dynamodb:PartiQLUpdate",
                                        "dynamodb:PartiQLDelete",
                                        "dynamodb:PartiQLSelect"
                                    ],
                                    resources: ["*"]
                                })
                            ]
                          }),
                          "idp-lambda-kms-policy": new iam.PolicyDocument({
                              statements:[
                                  new iam.PolicyStatement({
                                    sid: "IDPGTKMSAccess",
                                    effect: iam.Effect.ALLOW,
                                    actions: [
                                        "kms:Encrypt",
                                        "kms:Decrypt",
                                        "kms:ReEncrypt*",
                                        "kms:GenerateDataKey*",
                                        "kms:DescribeKey"
                                    ],
                                    resources: [
                                      `arn:aws:kms:${this.region}:${this.account}:key/*`
                                    ]
                                })
                              ]
                            })
                        }
                    });

    /**
     * Create Lambda that will consume message from topic and process the output from Textract
     * extracting the low confidence scores data that will be later used for the SMGT manifest message
    */
    const smgtFindLowScoresLambdaFn = new lambda.DockerImageFunction(this, 'idp-groundtruth-process-textract-output',{
      functionName: 'idp-groundtruth-process-textract-output',
      description: 'Process Textract output, identify low confidences scores and send to SMGT for human review',
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../src/lambda'), {
                  cmd: [ "idp-hitl-process-output.lambda_handler" ],
                  entrypoint: ["/lambda-entrypoint.sh"],
              }),
      environment:{
          LOG_LEVEL: 'DEBUG',
          GT_SNS_TOPIC_ARN: smgtManifestSNSTopic.topicArn,
          THRESHOLD_SSM: thresholdSSM.parameterName, 
          TEXTRACT_GT_TABLE: smgtDynamoTable.tableName,
          TEXTRACT_OUTPUT_BKT: smgtsagemakerTextractOutputS3.bucketName,
          TEXTRACT_OUTPUT_PREFIX: "output",    // optional 
          BUCKET_KMS_KEY: smgtsagemakerTextractOutputS3.encryptionKey?.keyId
      },
      role: lambdaRole,
      timeout: Duration.minutes(15),
      memorySize: 512
    }); 

    /* Subscribe Lambda to SNS topic for events */
    smgtFindLowScoresLambdaFn.addEventSource(new SnsEventSource(smgtIdpTextractSNS));


    /**
     * create Lambda pre-annotation function for SMGT
     */
    const smgtPreAnnotationLambdaFn = new lambda.DockerImageFunction(this, 'idp-groundtruth-pre-annotation',{
      functionName: 'idp-groundtruth-sagemaker-pre-annotation',
      description: 'Lambda function processes the manifest message and formats it for human review UI',
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../src/lambda'), {
                  cmd: [ "idp-hitl-pre-annotation.lambda_handler" ],
                  entrypoint: ["/lambda-entrypoint.sh"],
              }),
      environment:{
          LOG_LEVEL: 'DEBUG'
      },
      role: lambdaRole,
      timeout: Duration.minutes(2),
      memorySize: 128
    });      


    /**
     * create Lambda post annotation function
     */
    const smgtPostAnnotationLambdaFn = new lambda.DockerImageFunction(this, 'idp-groundtruth-post-annotation',{
      functionName: 'idp-groundtruth-sagemaker-post-annotation',
      description: 'Lambda function processes the review completion messages from SageMaker GroundTruth',
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../src/lambda'), {
                  cmd: [ "idp-hitl-post-annotation.lambda_handler" ],
                  entrypoint: ["/lambda-entrypoint.sh"],
              }),
      environment:{
          LOG_LEVEL: 'DEBUG',
          SMGT_DYNAMO_TABLE_NAME: smgtDynamoTable.tableName,
          ALL_PAGES_COMPLETE_SNS_TOPIC_ARN: smgtIdpAllPagesReviewedSNS.topicArn
      },
      role: lambdaRole,
      timeout: Duration.minutes(2),
      memorySize: 128
    });         

    /**
     * adding 'SageMaker' tag to buckets so that SMGT can access these 
     * with the AmazonSageMakerGroundTruthExecution policy
     */
    Tags.of(smgtHTMLTemplateBucket).add('SageMaker','true');
    Tags.of(smgtsagemakerTextractOutputS3).add('SageMaker','true');

    /**
     * Create Lambda monitoring function. Used to both create and keep SMGT streaming alive
     */
    const smgtJobMonitoringLambdaFn = new lambda.DockerImageFunction(this, 'idp-groundtruth-job-monitoring',{
      functionName: 'idp-groundtruth-job-monitoring',
      description: 'Lambda function to launch a new streaming job if one doesnt exist',
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../src/lambda'), {
                  cmd: [ "idp-hitl-smgt-monitoring.lambda_handler" ],
                  entrypoint: ["/lambda-entrypoint.sh"],
              }),
      environment:{
          LOG_LEVEL: 'DEBUG',
          TEXTRACT_LABELING_JOB_NAME: 'idp-groundtruth',
          SNS_TOPIC_MANIFEST_GO_ARN: smgtManifestSNSTopic.topicArn,
          S3_OUTPUT_PATH: 's3://'+smgtsagemakerTextractOutputS3.bucketName,
          TEXTRACT_LABELING_JOB_ROLE_ARN: smgtSageMakerRole.roleArn,
          WORK_TEAM_ARN: `${process.env.WORKTEAM_ARN}`,
          UI_TEMPLATE_S3_URL: 's3://'+smgtHTMLTemplateBucket.bucketName+'/textract-hil.liquid.html',
          PRE_HUMAN_TASK_LAMBDA_ARN: smgtPreAnnotationLambdaFn.functionArn ,
          TASK_TIME_LIMIT_IN_SECONDS: '28800',
          POST_HUMAN_TASK_LAMBDA_ARN: smgtPostAnnotationLambdaFn.functionArn,
          HUMAN_WORKERS_PER_OBJECT: '1',
          CONCURRENT_TASKS: '1000',
          TEXTRACT_TAGS: '{"Key": "GroundTruth", "Value": "Textract Review Job"}'
      },
      role: lambdaRole,
      timeout: Duration.minutes(2),
      memorySize: 128
    });   

    /**
     * create eventbridge schedule that runs every 24 hours at midnight UTC.
     * This calls the lambda house keeping function, which in turns
     * validates that the SMGT streaming infastructure is still available
     * and if required will create a new job should the old one have expired.
     */
    const cronRule = new Rule(this, 'idp-groundtruth-cronrule', {
      schedule: Schedule.expression('cron(59 23 * * ? *)')
    })
    //Set Lambda function as target for EventBridge
    cronRule.addTarget(new LambdaFunction(smgtJobMonitoringLambdaFn))
  }
}

module.exports = { SMGTIdpStack }