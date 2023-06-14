
## Amazon Textract Human-in-the-loop Architecture with SageMaker Ground Truth

![Architecture](./SMGT-HITL.png)

The architecture diagram above shows the end-to-end orchestration flow for Amazon Textract HITL with Amazon SageMaker Ground Truth. This architecture and the preceeding details are applicable to a new set of CHE (Crowd HTML Elements) specifically being built for Amazon Textract Human review purposes that differs from the existing A2I CHE but may technically be similar and an extension of it. The new CHE will support PDF, PNG, and JPG documents for review of WORD, LINE, KEY_VALUE_SET, and TABLE blocks from Amazon Textract.

#### _**NOTE: The following sections are a bit fluid at the moment and is subject to minor changes**_

### Key facts and assumptions

- This architecture depends on Amazon Textract sending Async Job completion notification to SNS and as such will work with Async API calls OOTB without any modifications.
- This architecture currently does not support API call level confidence threshold setting. The confidence threshold will need to be defined on a per workflow basis.
- Structural confidence scores such as KEY_VALUE_SET or CELL/MERGED_CELL confidence scores are not supported, only the text (or key text for FORM) value level confidence are supported similar to LINE or TEXT. See best practices on how to setup confidence thresholds.
- The human review task portal will support PDF, PNG, and JPG files via CHE and support WORD, LINE, KEY_VALUE_SET, and CELL Blocks. We will iterate and improve on these specific aspects as we get into a customer beta since much of what the UX should ideally be is unknown at this point.
- We will use a minimum number of required AWS services to ensure that customers in regulatory or strict infosec environments do not have to wait for service approvals internally to deploy HITL solution for their IDP workloads.
- The solution must be deployed with a specific set of confidence threshold values for one or more block type. The default threshold values in this architecture is set to `null` specifically to prevent unintended costs incurred due to tasks being sent to SMGT due to low confidence scores.
- There will be no support for AnalyzeDocument SIGNATURE & QUERY, AnalyzeID, AnalyzeExpense, and AnalyzeLending at beta.
- The solution will be delivered to customers in form of a packaged Cloud Development Kit (CDK) application which will contain all the necessary resources required, and full detailed instructions on how to deploy this HITL solution.
- The solution will come in a single command (CLI) wizard based deployment.
- A version of the solution will be made open-source for customers/partners to use/customize per their needs.
- The solution will come with a pre-defined Liquid HTML template (with some minimal modification capabilities).
- Reviewed data back from reviewers will be added back as an extension to the original JSON. The original JSON values will not be overwritten (how A2I currently works). Customers must implement post-processing logic to process the reviewed data from the original JSON.
- For a SMGT Worker Team of more than 1 reviewer, different parts of the document may be routed to different workers based on the queuing logic internal to SMGT. Due to maximum document size supported by Amazon Textract (3000 pages), SMGT will receive per page input due to payload size limitations at several stages of the process.
- We will follow a "[what you get is what you see](https://www.youtube.com/watch?v=e0GVixJvt-g)" approach from a human review perspective. _What is extracted from Textract is what the user sees in the SMGT review UI_. Providing additional contextual information is limited to the user being able to download the entire document, if it is a multi-page pdf (or tiff), and if allowed by the administrator at the time of setup via `isRefDownloadable` attribute as discussed below.

### Confidence threshold for human review best practices

- Define atleast one confidence threshold from WORD, LINE, KEY_VALUE_SET, or TABLE.
- If using `StartDocumentTextDetection` Async API, use either `WORD` or `LINE` thresholds (or both).
- If using `StartDocumentAnalysis` with FORMS feature, define the `KEY_VALUE_SET` threshold.
- If using `StartDocumentAnalysis` with TABLE feature, define the `CELL` threshold.
- If using both FORMS and TABLES features with `StartDocumentAnalysis`, define both `KEY_VALUE_SET` & `CELL` thresholds.
- Do not define `WORD`, `LINE` when using `StartDocumentAnalysis` as this may mean more tasks sent to SMGT for reviews incurring additional costs. 

## Supported file mime types

At beta we plan to support the following file mime types-

- `image/png`
- `image/jpg`
- `image/tif`  (TBD)
- `image/tiff` (TBD)
- `application/pdf`

The crowd UI will be agnostic of the specific mime types for display purposes and it will receive Base64 encoded image URIs regardless of what the actual file type is. This is especially because rendering large PDFs in the browser is a resource intensive task and can impact the user experience. For each review task, SMGT will receive per page information which will include the page number, the low score JSON for that page, a Base64 encoded image of the page. For `application/pdf` and `image/tif` variations the UI will also display an open in new tab/download button in the UI so that the reviewer may be able to view the full document for more context (should they need it). Typically, from a pure "whether this word/line/key value/table cell is correctly extracted by Textract or not?" perspective, not a lot of context is required and the task remains isolated to the binary yes/no decision based on what the user see's on the left (in the document image) vs what Textract extracted on the right side of the UI. We will explore additional usability requirements as we get to beta testing with customers, iterate and improve.

## Data contracts between Amazon Textract and SMGT
### Simplified JSON for SMGT CHE (Crowd HTML Elements)

Below are the JSON schema structures for each block type that will be sent to SMGT. We will refer these as _**Low score blocks (LSB)**_.

WORD / LINE

```json
{
  "WORD" | "LINE" : "John"  --> Only value editable
  "Confidence": ...,  
  "Id": ...,
  "PageNum": ...,
  "Geometry": {}
}
```

Forms

```json
{
   "Name:" : "John Doe",  --> Both key and value editable
   "KeyConfidence": ...,
   "ValueConfidence": ...,   
   "Id": ...,
   "PageNum": ...,
   "Geometry": {}
}
```

Table

```json
{
   "CELL" | "MERGED_CELL" : "John Doe",  --> Only value editable
   "Confidence": ...,   
   "Id": ...,
   "PageNum": ...,
   "Geometry": {}
}
```

## GroundTruth manifest messages

SMGT Streaming jobs will receive SNS messages from `idp-hitl-process-output` Lambda function in the following JSON Line format

```json
{ 
    "source-ref": "s3://<bucket>/<prefix>/document.pdf|png|jpg", 
    "isRefDownloadable": boolean,
    "data": "s3://<bucket>/<prefix>/<textract-job-id>/page-jsons/low-scores-page-1.json",
    "page-num": 1,
    "mime_type": ...,
    "base64_image": "s3://<bucket>/<prefix>/document-base64.txt",
    "textract-job-id": "xxxxxxxxxxx"
}
```

- `source-ref` is the location of the document file itself 
- `data` contains the S3 prefix where per page JSON containing the low score Blocks from textract will reside, 
- `page-num` is the page number for which the low  scores are being sent,  
- `textract-job-id` is the Textract Async Job ID. 
- `mime_type` is the file's mime type 
- `base64_image` is the base64 encoded URI of the document page to be rendered on screen
- `isRefDownloadable` is a boolean flag that allows/denies the reviewer to download the full document (in case of PDF)

It is important to note that this single message is per page (especially for multi-page PDFs).

## GroundTruth pre-annotation Lambda function (PRLF)

The SMGT PRLF will recieve an event of the following format

```json
{
    "version": "2018-10-16",
    "labelingJobArn": <labelingJobArn>
    "dataObject" : {
        "source-ref": "s3://<bucket>/<prefix>/document.pdf|png|jpg", 
        "data": "s3://<bucket>/<prefix>/<textract-job-id>/page-jsons/low-scores-page-1.json",
        "page-num": 1,
        "mime_type": ...,
        "base64_image": "s3://<bucket>/<prefix>/document-base64.txt",
        "textract-job-id": "xxxxxxxxxxx"
    }
}
```

The PALF will read the JSON file specified under `data` and construct the following message for Ground Truth.

```json
{
    "taskInput": {
        "page-num": 1,        
        "textract-job-id": "xxxxxxxxxxx",
        "lsb": [ lsb, lsb, ... ],
        "mime_type": ...,
        "base64_image": "data:image/png;base64,xxx...."
    },
    "isHumanAnnotationRequired": true
}
```

`lsb` attribute above refers to _**Low score blocks**_ and is a list of low score blocks as defined in the sections above.

## GroundTruth post-annotation Lambda function (POLF)

When all workers have reviewed the data object or when `TaskAvailabilityLifetimeInSeconds` has been reached, the expectation is that SMGT will send atleast the following information.

```json
{
    "page-num": 1,        
    "textract-job-id": "xxxxxxxxxxx",
    "rb": [rb, rb, ...]
}
```

The attribute `rb` above refers to _**Reviewed block**_ and is of the same structure of `lsb` with the key/values modified/updated by the human reviewer. The POLF is then expected to recieve a message of the following format. Note that we will assume that `NumberOfHumanWorkersPerDataObject` is set to `1` per data object.

```json
{
    "version": "2018-10-16",
    "labelingJobArn": <string>,
    "labelCategories": [<string>],
    "labelAttributeName": <string>,
    "roleArn" : <string>,
    "payload": {
        "s3Uri": "s3://<bucket>/low-scores-page-1-reviewed.json"
    }
}
```

The POLF will then read the output JSON from the `s3Uri` to put back the reviewed data into the raw Textract output JSON (by extending it, no midifications to the low score values will be done in the original output) for that document page number and job-id.

## Ground Truth Streaming Job Keep Alive - _the monitoring Lambda Function_

As of this writing, SMGT Streaming Jobs are terminated after 10 days of inactivity. We will have a Lambda function scheduled to check if a streaming job is in `InProgress` state using using a combination of SageMaker [`ListLabelingJob`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker.html#SageMaker.Client.list_labeling_jobs) and [`DescribeLabelingJob`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker.html#SageMaker.Client.describe_labeling_job) APIs to check for a specific _Tag_. If the streaming job is found to be in either `'Completed'|'Failed'|'Stopping'|'Stopped'` statuses, a new streaming job will be created using SageMaker [`CreateLabelingJob`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker.html#SageMaker.Client.create_labeling_job) API and a specific job Tag, with the existing WorkerTeam, PRLF and POLF Lambda functions.

#### Implications:
This mechanism may encounter an edge case where there is a short delay (perhaps a few hours) between when the job completes (or stops, fails) and when our monitoring Lambda function detects it and subsequently launches a new job. Manifest messages coming in during that period will be sent to an SNS Dead Letter Queue (SQS). Once our monitoring Lambda successfully launches an SMGT streaming job, it can scan the dead letter queue for any messages that failed to deliver due to a stopped SMGT streaming job and can further put them back into the SNS Topic.
