#!/bin/bash

while getopts i:s:b:r: flag
do
    case "${flag}" in
        i) iamrole=${OPTARG};;
        s) snsarn=${OPTARG};;
        b) bucket=${OPTARG};;
        r) region=${OPTARG};;
    esac
done

for f in $(aws s3 ls s3://$bucket/input/ | awk '{print $4}' | awk NF); do
    echo "$(date +%d-%m-%Y_%H-%M-%S) [INFO:] Submitting Job for file $f"    
    aws textract start-document-analysis \
    --document-location '{"S3Object":{"Bucket":"'$bucket'","Name":"input/'"$f"'"}}' \
    --feature-types '["TABLES","FORMS","SIGNATURES"]' \
    --notification-channel 'SNSTopicArn='$snsarn',RoleArn='$iamrole'' \
    --output-config '{"S3Bucket":"'$bucket'","S3Prefix":"output"}' \
    --region $region \
    --output text > test.out.txt
    cat test.out.txt
    sleep 1
done