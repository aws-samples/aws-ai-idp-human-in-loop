# aws textract start-document-analysis \
#     --document-location '{"S3Object":{"Bucket":"idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb","Name":"input/sample-hitl.pdf"}}' \
#     --feature-types '["TABLES","FORMS","SIGNATURES"]' \
#     --notification-channel "SNSTopicArn=arn:aws:sns:eu-central-1:710096454740:idp-textract-topic,RoleArn=arn:aws:iam::710096454740:role/idp-textract-service-sns-role" \
#     --output-config '{"S3Bucket": "idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb", "S3Prefix": "output"}' \
#     --region eu-central-1 \
#     --output text > test.out.txt
# cat test.out.txt

aws textract start-document-analysis \
    --document-location '{"S3Object":{"Bucket":"idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb","Name":"input/OH_GIMC.jpg"}}' \
    --feature-types '["TABLES","FORMS","SIGNATURES"]' \
    --notification-channel "SNSTopicArn=arn:aws:sns:eu-central-1:710096454740:idp-textract-topic,RoleArn=arn:aws:iam::710096454740:role/idp-textract-service-sns-role" \
    --output-config '{"S3Bucket": "idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb", "S3Prefix": "output"}' \
    --region eu-central-1 \
    --output text > test.out.txt
cat test.out.txt

aws textract start-document-analysis \
    --document-location '{"S3Object":{"Bucket":"idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb","Name":"input/1Table_Alignment.pdf"}}' \
    --feature-types '["TABLES","FORMS","SIGNATURES"]' \
    --notification-channel "SNSTopicArn=arn:aws:sns:eu-central-1:710096454740:idp-textract-topic,RoleArn=arn:aws:iam::710096454740:role/idp-textract-service-sns-role" \
    --output-config '{"S3Bucket": "idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb", "S3Prefix": "output"}' \
    --region eu-central-1 \
    --output text > test.out.txt
cat test.out.txt

# 419caddb030eba4da7a687eb08b7cfee44bc113e27471d73b266a9f1a21bc716
# c84bd6f73e216e443718a8e3aa26c47fb560dec37895fd38b7411cd0c51cc0fa
# 45f322ec1c275ae85beace7feade29b0dcdd19a1fd61aa8741cbd8555fa03295
# b943cab540d5537f271d33f57eb3c7f307027a5e5427164cd455aba9a8f61076
# d2899aef83e57854d5ddc22bce559fd2e97c9508236288b2e8342d9f2a0ab3b2


aws textract start-document-analysis \
    --document-location '{"S3Object":{"Bucket":"idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb","Name":"input/1Table_MissingDate.pdf"}}' \
    --feature-types '["TABLES","FORMS","SIGNATURES"]' \
    --notification-channel "SNSTopicArn=arn:aws:sns:eu-central-1:710096454740:idp-textract-topic,RoleArn=arn:aws:iam::710096454740:role/idp-textract-service-sns-role" \
    --output-config '{"S3Bucket": "idp-textract-output-bucket-45d0c9d1-75f5-5824-9af7-c2a4131e76eb", "S3Prefix": "output"}' \
    --region eu-central-1 \
    --output text > test.out.txt
cat test.out.txt