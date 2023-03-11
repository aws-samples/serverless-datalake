#!/bin/bash
# Assuming we are in Serverless-datalake folder
cd ..
echo "--- Upgrading npm ---"
sudo npm install n stable -g
echo "--- Installing cdk ---"
sudo npm install -g aws-cdk@2.55.1
echo "--- Bootstrapping CDK on account ---"
cdk bootstrap aws://$(aws sts get-caller-identity --query "Account" --output text)/us-east-1
echo "--- Cloning serverless-datalake project from aws-samples ---"
# assuming we have already cloned. 
# git clone https://github.com/aws-samples/serverless-datalake.git
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
# read -p "Press any key to deploy the Serverless Datalake ..."
cdk deploy -c environment_name=dev ServerlessDatalakeStack
echo "Lake deployed successfully"
aws lambda invoke --function-name serverless-event-simulator-dev --invocation-type Event --cli-binary-format raw-in-base64-out  --payload '{ "name": "sample" }' response.json