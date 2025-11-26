#!/usr/bin/bash
Green='\033[0;32m'
Red='\033[0;31m'
NC='\033[0m'

# Get account ID
account_id=$(aws sts get-caller-identity --query "Account" --output text)
deployment_region=$(aws ec2 describe-availability-zones --output text --query 'AvailabilityZones[0].RegionName')

if [ -z "$1" ]
then
    infra_env='dev'
else
    infra_env=$1
fi  

if [ "$infra_env" != "dev" -a "$infra_env" != "prod" ]
then
    echo "Environment name can only be dev or prod. example 'sh installer.sh dev' "
    exit 1
fi

echo "Environment: $infra_env"
echo "Region: $deployment_region"
echo "Account ID: $account_id"
echo ' '
echo '*************************************************************'
printf "$Green Press Enter to proceed with deployment else ctrl+c to cancel $NC "
read -p " "
echo '*************************************************************'
echo ' Starting deployment ... '

# Create a temporary buildspec file
cat > buildspec.yml << EOF
version: 0.2

phases:
  install:
    runtime-versions:
      nodejs: 22
      python: 3.12
    commands:
      - echo Installing dependencies...
      - npm install -g aws-cdk@2.1031.2
      - pip install -r requirements.txt
      
  build:
    commands:
      - echo Running builder script...
      - chmod +x builder-nointeractive.sh
      - ./builder-nointeractive.sh $infra_env
  
  post_build:
    commands:
      - echo Build completed on \`date\`
      
artifacts:
  files:
    - '**/*'
EOF

# Create a unique project name
timestamp=$(date +%Y%m%d%H%M%S)
project_name="document-insight-builder-$infra_env-$timestamp"

# Check if the service role exists, if not create it
if ! aws iam get-role --role-name codebuild-document-insight-service-role --query 'Role.RoleName' --output text &>/dev/null; then
  echo "Creating CodeBuild service role..."
  
  # Create the role
  aws iam create-role \
    --role-name codebuild-document-insight-service-role \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "codebuild.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }'
    
  # Attach necessary policies
  aws iam attach-role-policy \
    --role-name codebuild-document-insight-service-role \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
    
  # Wait for role propagation
  echo "Waiting for role propagation..."
  sleep 10
fi

# Create S3 input bucket if it doesn't exist
input_bucket="codebuild-$infra_env-$deployment_region-$account_id-document-insight-input"
if ! aws s3api head-bucket --bucket $input_bucket &>/dev/null; then
  echo "Creating S3 input bucket: $input_bucket"
  aws s3 mb s3://$input_bucket
fi

# Zip the current directory
echo "Zipping project files..."
zip -r document-insight-extraction.zip . -x "*.git*" "*.zip" "node_modules/*" ".venv/*" "cdk.out/*"

# Upload to S3
echo "Uploading project files to S3..."
aws s3 cp document-insight-extraction.zip s3://$input_bucket/

# Create the CodeBuild project
echo "Creating CodeBuild project: $project_name"
response=$(aws codebuild create-project \
  --name $project_name \
  --source type=S3,location=$input_bucket/document-insight-extraction.zip \
  --artifacts type=NO_ARTIFACTS \
  --environment type=LINUX_CONTAINER,image=aws/codebuild/amazonlinux2-x86_64-standard:5.0,computeType=BUILD_GENERAL1_LARGE,privilegedMode=true,environmentVariables="[{name=infra_env,value=$infra_env,type=PLAINTEXT}]" \
  --service-role codebuild-document-insight-service-role \
  --timeout-in-minutes 180 \
  --output text)

# Start the build
echo "Starting CodeBuild project..."
build_id=$(aws codebuild start-build --project-name $project_name | jq -r '.build.id')
echo "Build started with ID: $build_id"

# Monitor the build
echo "Monitoring build progress..."
retry_count=0
while true; do
  status=$(aws codebuild batch-get-builds --ids $build_id | jq -r '.builds[0].buildStatus')
  phase=$(aws codebuild batch-get-builds --ids $build_id | jq -r '.builds[0].currentPhase')
  
  echo "Current status: $status, Phase: $phase"
  
  if [ "$status" == "SUCCEEDED" ] || [ "$status" == "FAILED" ] || [ "$status" == "STOPPED" ]; then
    break
  else
    echo "Build is still in progress (Usually takes 30-40 minutes to complete)... sleeping for 60 seconds"
    if [ $((retry_count % 2)) -eq 0 ]; then
      echo -e "${Green}TIP: You can monitor CloudFormation stack deployments in the AWS Console:${NC}"
      echo -e "https://$deployment_region.console.aws.amazon.com/cloudformation/home?region=$deployment_region#/stacks"
    fi
    # Increment retry count
    retry_count=$((retry_count + 1))
    
    # Show AppRunner tip every 3 retries (3, 6, 9, etc.)
    if [ $((retry_count % 3)) -eq 0 ]; then
      echo -e "${Green}TIP: Once deployment completes, you can find your application URL in AppRunner:${NC}"
      echo -e "https://$deployment_region.console.aws.amazon.com/apprunner/home?region=$deployment_region#/services"
    fi
  fi
  
  sleep 60
done

if [ "$status" == "SUCCEEDED" ]; then
  echo -e "${Green}Deployment completed successfully!${NC}"
  echo -e "${Green}You can access your application at the URL available in AppRunner:${NC}"
  echo -e "https://$deployment_region.console.aws.amazon.com/apprunner/home?region=$deployment_region#/services"
  echo ""
  echo -e "${Green}Next Steps:${NC}"
  echo "1. Create a Cognito user in the AWS Console"
  echo "2. Access the frontend application via AppRunner URL"
  echo "3. Upload a PDF document and extract insights"
  exit 0
else
  echo -e "${Red}Deployment failed!${NC}"
  echo -e "${Green}You can check CloudFormation stacks for more details:${NC}"
  echo -e "https://$deployment_region.console.aws.amazon.com/cloudformation/home?region=$deployment_region#/stacks"
  exit 1
fi

# Clean up
rm -f document-insight-extraction.zip
rm -f buildspec.yml

# Get build logs
log_group="/aws/codebuild/$project_name"
log_stream=$(aws logs describe-log-streams --log-group-name $log_group --order-by LastEventTime --descending --limit 1 | jq -r '.logStreams[0].logStreamName')

echo "Build completed with status: $status"
echo "To view detailed logs, run:"
echo "aws logs get-log-events --log-group-name $log_group --log-stream-name $log_stream"