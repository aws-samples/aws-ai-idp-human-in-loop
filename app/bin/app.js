#!/usr/bin/env node
require('dotenv').config();
const cdk = require('aws-cdk-lib');
const { SMGTIdpStack } = require('../lib/smgt-idp-stack');

const app = new cdk.App();

// Ideally you should be able to deploy using CDK_DEFAULT_ACCOUNT & CDK_DEFAULT_REGION provided AWS credentials
// and environment variables are setup correctly 

// const deployEnv = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION }
const deployEnv = { 
                    account: process.env.IDP_ACCOUNT || process.env.CDK_DEFAULT_ACCOUNT, 
                    region: process.env.IDP_REGION || process.env.CDK_DEFAULT_REGION
                  };

new SMGTIdpStack(app, 'SMGTStack', { env: deployEnv });
