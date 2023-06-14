# IDP AI Human in the Loop with SageMaker GroundTruth

## Get Started

This repo contains a CDK (AWS Cloud Development Kit) application that deploys the necessary code required for setting up Human-in-the-loop for Amazon Textract. You can clone the repo and perform the deployment steps just as for a normal CDK app. However, it is recommended that you use an Amazon Cloud9 environment to deploy this since Cloud9 comes pre-installed with all the necessary dependencies required to deploy the application.

Setup a AWS Cloud9 environment by clicking the launch stack button below or follow the [step-by-step instructions](./documentation/CLOUD9.md) to deploy an AWS Cloud9 environment. _(estimated time to deploy 10 minutes)_

[![Launch Stack](https://cdn.rawgit.com/buildkite/cloudformation-launch-stack-button-svg/master/launch-stack.svg)](https://console.aws.amazon.com/cloudformation/home?region=us-east-2#/stacks/new?stackName=idp-smgt-cloud9&templateURL=https://idp-assets-wwso.s3.us-east-2.amazonaws.com/cfn/idp-deploy-cloud9.yaml)

---

## Installation

Before proceeding with the steps for installing, please [review the architecure](./documentation/ARCHITECTURE.md) to understand the solution. You must create a Workteam using Amazon SageMaker GroundTruth Labeling Workforces. Follow the instructions [here](./documentation/WORKTEAM.md) to create the workteam. Once you have your Private Workforce ready, take a note of the ARN of the workteam.

In your AWS Cloud9 or local machine, start by cloning this repository. 

```bash
git clone <repo_url>
```

The first thing required is to update the `.env` file found under `/app` directory. Below is what the `.env` file looks like. You should replace the `IDP_REGION`, `IDP_ACCOUNT`, and the `TEXTRACT_CONFIDENCE_THRESHOLD` values per your needs. Update the workteam ARN for `WORKTEAM_ARN` based on the private work team you just created.

Note: the `TEXTRACT_CONFIDENCE_THRESHOLD` value is the confidence threshold value that this deployment and SageMaker Ground Truth will use to evaluate confidence for sending Amazon Textract outputs, and any confidence scores less than this threshold's value is sent to human for review. Once deployed, you can change the confidence threshold value from AWS Systems Manager Parameter Store. See _Updating Confidence Thresholds_ section below for details.

Change into the `/app` directory `cd app` and update the `.env` file by replacing the appropriate values

```
IDP_REGION=<your-region>
IDP_ACCOUNT=<your-aws-account-number>
TEXTRACT_CONFIDENCE_THRESHOLD=<your-confidence-threshold>
WORKTEAM_ARN=<your-smgt-workteam-arn>
```

example

```
IDP_REGION=us-east-1
IDP_ACCOUNT=123456789
TEXTRACT_CONFIDENCE_THRESHOLD=90
WORKTEAM_ARN="arn:aws:sagemaker:eu-central-1:123456789:workteam/private-crowd/idp-workteam"
```

If you are in a Cloud9 environment, you will have [AWS CDK Toolkit (CLI)](https://docs.aws.amazon.com/cdk/v2/guide/cli.html) already installed for you. From there, all you need to do is run the following commands.

- Change into the `/app` directory if you are not already in that directory and install the dependencies
  
  ```bash
  cd app
  npm install --save
  ```

- Bootstrap CDK for your account. Note that the `account-id` and `region` in the command below are the same values from the `.env` file.
  
  ```bash
  cdk bootstrap aws://<account>/<region>
  ```

- Run CDK Synth to synthesize the CDK app to Cloudformation template
  
  ```bash
  cdk synth
  ```

- Run CDK deploy to deploy the application

  ```bash
  cdk deploy --outputs-file ./cdk-outputs.json
  ```

Once the deployment is complete, the `cdk-outputs.json` will contain the log of resources created with the stack.

## Updating Confidence Thresholds

Once deployed the application will create a threshold parameter under AWS SSM Parameter store. You can easily change the value of your confidence thresholds while testing via Parameter store directly without having to re-deploy this application again. To update the threshold value-

1. Log on to your AWS console and search for "SSM" in the **_Search_** field and click on **_Systems Manager_** from the menu.
2. In the **_Systems Manager_** console, select the **_Parameter store_** option from under **_Application Management_** in the left navigation menu.
3. The following screen will display a list of parameters. Search for parameter name `CFN-idptextractconfidencethreshold` 
4. Click the name of the parameter to view it's details. Notice that the **_Value_** of the parameter is set to the value that was specified in the `.env` file.
5. To edit/modify this value, click **_Edit_** button from the top right and modify the value. Note: the value should be numeric represenation with acceptable value range between 0 and 100.
6. Once done, click **_Save changes_** to save your changes.

**Important Note about updating threshold**: Changing the threshold value will take affect for new Amazon Textract results. Existing tasks in the SageMaker Ground Truth human review task queue will not consider this new value and will continue to use the prior threshold value

## Cleaning up

> ⚠️ **WARNING**: The step below is destructive, which means that all resources including the Amazon S3 bucket, the Amazon DynamoDB table will be deleted. It is recommended that you back up the Amazon S3 bucket before deleting the application.

To clean-up and delete the application and all the corresponding AWS resources from your account, run the following command from the `/app` directory.

```bash
cdk destroy
```

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](./LICENSE) file.

