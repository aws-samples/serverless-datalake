#!/bin/bash
echo "--- Upgrading npm ---"
sudo npm install n stable -g
echo "--- Installing cdk ---"
sudo npm install -g aws-cdk@2.55.1
echo "--- Bootstrapping CDK on account ---"
cdk bootstrap aws://${aws sts get-caller-identity --query "Account" --output text}/us-east-1
echo "--- Cloning serverless-datalake project from aws-samples ---"
git clone https://github.com/aws-samples/serverless-datalake.git
cd serverless-datalake
echo "--- Set python virtual environment ---"
python3 -m venv .venv
echo "--- Activate virtual environment ---"
source .venv/bin/activate
echo "--- Install Requirements ---"
pip install -r requirements.txt
echo "--- CDK synthesize ---"
cdk synth -c environment_name=dev
echo "--- CDK deploy ---"
cdk deploy -c environment_name=dev ServerlessDatalakeStack
