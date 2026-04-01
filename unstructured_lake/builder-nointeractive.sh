#!/usr/bin/bash 
Green='\033[0;32m'
Red='\033[0;31m'
NC='\033[0m'

# Get account ID
account_id=$(aws sts get-caller-identity --query "Account" --output text)

if [ -z "$1" ]
then
    infra_env='dev'
else
    infra_env=$1
fi  

if [ $infra_env != "dev" -a $infra_env != "prod" ]
then
    echo "Environment name can only be dev or prod. example 'sh builder-nointeractive.sh dev' "
    exit 1
fi

echo "Environment: $infra_env"
echo ' '
echo '*************************************************************'
echo '*************************************************************'
echo ' Starting deployment ... '

deployment_region=$(aws ec2 describe-availability-zones --output text --query 'AvailabilityZones[0].RegionName')

echo "--- Upgrading npm ---"
sudo npm install n stable -g
echo "--- Installing cdk ---"
sudo npm install -g aws-cdk@2.1031.2

echo "--- Bootstrapping CDK on account in region $deployment_region ---"
echo "Account ID: $account_id"
echo "Region: $deployment_region"

# CDK bootstrap is idempotent - safe to run multiple times
cdk bootstrap aws://$account_id/$deployment_region

if [ $? -eq 0 ]; then
    echo "✓ CDK bootstrap completed successfully"
else
    echo "✗ CDK bootstrap failed"
    exit 1
fi

CURRENT_UTC_TIMESTAMP=$(date -u +"%Y%m%d%H%M%S")

ls -lrt

echo "--- pip install requirements ---"
python3 -m pip install -r requirements.txt

echo "--- CDK synthesize ---"
cdk synth --context env=$infra_env

echo "--- CDK deploy Lambda Layer Stack ---"
cdk deploy --context env=$infra_env DocumentInsightLambdaLayer${infra_env^}Stack --require-approval never --outputs-file layer-outputs.json

if [ $? -eq 0 ]; then
    echo "✓ Lambda Layer stack deployed successfully"
    
    # Check what was actually created
    if [ -f "layer-outputs.json" ]; then
        echo "Lambda Layer stack outputs:"
        cat layer-outputs.json | jq '.'
        
        # Extract the build project name from outputs
        BUILD_PROJECT_NAME=$(cat layer-outputs.json | grep -o '"LayersBuildProjectName": "[^"]*"' | cut -d'"' -f4)
        echo "Build project name from outputs: $BUILD_PROJECT_NAME"
    fi
else
    echo "✗ Lambda Layer stack deployment failed"
    exit 1
fi

echo "--- Get Lambda Layer Build Container ---"

# First try to get the project name from the stack outputs
if [ -f "layer-outputs.json" ] && [ -n "$BUILD_PROJECT_NAME" ]; then
    echo "Using build project from stack outputs: $BUILD_PROJECT_NAME"
    build_container="$BUILD_PROJECT_NAME"
else
    echo "Stack outputs not available, searching for project..."
    expected_project="document-insight-lambda-layer-builder-$infra_env"
    echo "Expected project name: $expected_project"

    # Try to find the exact project name first
    build_container=$(aws codebuild list-projects --query "projects[?@ == '$expected_project']" --output text)

    if [ -z "$build_container" ]; then
        echo "Exact project name not found, searching for lambda-layer-builder pattern..."
        # Try to find any project with lambda-layer-builder in the name
        build_container=$(aws codebuild list-projects --query "projects[?contains(@, 'lambda-layer-builder')]" --output text)
    fi

    if [ -z "$build_container" ]; then
        echo "Lambda layer builder not found, searching for any document-insight builder..."
        # Fallback: look for any document-insight builder project
        build_container=$(aws codebuild list-projects --query "projects[?contains(@, 'document-insight') && contains(@, 'builder')]" --output text | head -1)
    fi
fi

echo "Build container: $build_container"

if [ -n "$build_container" ]; then
    echo "--- Trigger Lambda Layer Build ---"
    BUILD_ID=$(aws codebuild start-build --project-name $build_container --query 'build.id' --output text)
    echo "Build ID: $BUILD_ID"
    
    if [ "$?" != "0" ] || [ -z "$BUILD_ID" ]; then
        echo "✗ Could not start CodeBuild project"
        echo "This will cause Lambda function deployment to fail"
        exit 1
    else
        echo "✓ Lambda layer build started successfully"
        
        # Monitor the build with better error handling
        echo "Monitoring lambda layer build progress..."
        build_failed=false
        
        while true; do
          # Get build status with error handling
          build_info=$(aws codebuild batch-get-builds --ids $BUILD_ID 2>/dev/null)
          
          if [ $? -ne 0 ]; then
            echo "⚠ Warning: Could not get build status"
            sleep 30
            continue
          fi
          
          status=$(echo $build_info | jq -r '.builds[0].buildStatus // "UNKNOWN"')
          phase=$(echo $build_info | jq -r '.builds[0].currentPhase // "UNKNOWN"')
          
          echo "$(date): Status: $status, Phase: $phase"
          
          if [ "$status" == "SUCCEEDED" ]; then
            echo "✓ Lambda layer build completed successfully!"
            break
          elif [ "$status" == "FAILED" ] || [ "$status" == "STOPPED" ] || [ "$status" == "FAULT" ] || [ "$status" == "TIMED_OUT" ]; then
            echo "✗ Lambda layer build failed with status: $status"
            
            # Get build logs for debugging
            echo "Build logs:"
            aws logs get-log-events \
              --log-group-name "/aws/codebuild/$build_container" \
              --log-stream-name "$BUILD_ID" \
              --query 'events[*].message' \
              --output text 2>/dev/null | tail -20
            
            build_failed=true
            break
          else
            echo "Build is still in progress... sleeping for 30 seconds"
          fi
          
          sleep 30
        done
        
        if [ "$build_failed" = true ]; then
            echo "✗ Lambda layer build failed - cannot proceed with deployment"
            echo "Lambda functions require these layers to be available"
            exit 1
        fi
    fi
else
    echo "✗ Lambda layer build project not found: $project"
    echo "Available projects:"
    aws codebuild list-projects --query 'projects' --output table
    exit 1
fi

echo ""
echo "=========================================="
echo "Lambda Layers Ready - Deploying Infrastructure"
echo "=========================================="
echo ""

echo "--- CDK deploy core infrastructure stacks ---"
# Deploy core stacks (excluding ECR and AppRunner)
cdk deploy --context env=$infra_env \
  DocumentInsightCognito${infra_env^}Stack \
  DocumentInsightS3${infra_env^}Stack \
  DocumentInsightDynamoDB${infra_env^}Stack \
  DocumentInsightProcessingStatus${infra_env^}Stack \
  DocumentInsightLambda${infra_env^}Stack \
  DocumentInsightApiGateway${infra_env^}Stack \
  --require-approval never --outputs-file core-outputs.json

if [ $? -eq 0 ]; then
    echo "✓ Core infrastructure stacks deployed successfully"
else
    echo "✗ Core infrastructure deployment failed"
    exit 1
fi

if [ $? -eq 0 ]; then
    echo "✓ CDK stacks deployed successfully"
else
    echo "CDK deployment failed"
    exit 1
fi

echo "--- Configuring S3 event notifications ---"
if [ -f "core-outputs.json" ]; then
    # Extract required values from core stack outputs
    DOCUMENTS_BUCKET=$(cat core-outputs.json | grep -o '"DocumentsBucketName": "[^"]*"' | cut -d'"' -f4 | head -1)
    LAMBDA_ARN=$(cat core-outputs.json | grep -o '"DocumentProcessorLambdaArn": "[^"]*"' | cut -d'"' -f4 | head -1)
    
    if [ -n "$DOCUMENTS_BUCKET" ] && [ -n "$LAMBDA_ARN" ]; then
        echo "Configuring S3 bucket: $DOCUMENTS_BUCKET"
        echo "Lambda function: $LAMBDA_ARN"
        
        # Create notification configuration JSON with PDF filter
        cat > s3-notification-config.json << EOF
{
    "LambdaFunctionConfigurations": [
        {
            "Id": "DocumentProcessorTrigger",
            "LambdaFunctionArn": "$LAMBDA_ARN",
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "suffix",
                            "Value": ".pdf"
                        }
                    ]
                }
            }
        },
        {
            "Id": "DocumentProcessorCleanup",
            "LambdaFunctionArn": "$LAMBDA_ARN",
            "Events": ["s3:ObjectRemoved:Delete"],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "suffix",
                            "Value": ".pdf"
                        }
                    ]
                }
            }
        }
    ]
}
EOF
        
        # Grant S3 permission to invoke Lambda (idempotent)
        echo "Granting S3 permission to invoke Lambda..."
        STATEMENT_ID="AllowS3Invocation"
        
        # Check if permission already exists
        if aws lambda get-policy --function-name "$LAMBDA_ARN" --query 'Policy' --output text 2>/dev/null | grep -q "$STATEMENT_ID"; then
            echo "S3 invoke permission already exists, removing old permission..."
            aws lambda remove-permission \
                --function-name "$LAMBDA_ARN" \
                --statement-id "$STATEMENT_ID" \
                2>/dev/null || true
        fi
        
        # Add the permission
        aws lambda add-permission \
            --function-name "$LAMBDA_ARN" \
            --principal s3.amazonaws.com \
            --action lambda:InvokeFunction \
            --statement-id "$STATEMENT_ID" \
            --source-arn "arn:aws:s3:::$DOCUMENTS_BUCKET" \
            2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "✓ Lambda permission granted successfully"
        else
            echo "⚠ Warning: Failed to grant Lambda permission"
        fi
        
        # Configure S3 bucket notification
        echo "Configuring S3 bucket notification..."
        aws s3api put-bucket-notification-configuration \
            --bucket "$DOCUMENTS_BUCKET" \
            --notification-configuration file://s3-notification-config.json
        
        if [ $? -eq 0 ]; then
            echo "✓ S3 event notifications configured successfully"
        else
            echo "⚠ Warning: Failed to configure S3 event notifications"
        fi
        
        # Clean up temporary file
        rm -f s3-notification-config.json
    else
        echo "⚠ Warning: Could not find required outputs for S3 event notification configuration"
        echo "Documents bucket: $DOCUMENTS_BUCKET"
        echo "Lambda ARN: $LAMBDA_ARN"
    fi
else
    echo "⚠ Warning: core-outputs.json not found, skipping S3 event notification configuration"
fi

echo ""
echo "=========================================="
echo "Deploying CloudFront + S3 Hosting"
echo "=========================================="
echo ""

echo "--- CDK deploy CloudFront stack ---"
cdk deploy --context env=$infra_env \
  DocumentInsightCloudFront${infra_env^}Stack \
  --require-approval never --outputs-file cloudfront-outputs.json

if [ $? -eq 0 ]; then
    echo "✓ CloudFront stack deployed successfully"
else
    echo "✗ CloudFront stack deployment failed"
    exit 1
fi

echo "--- Building and deploying frontend via CodeBuild ---"
# Merge core and CloudFront outputs
jq -s 'add' core-outputs.json cloudfront-outputs.json > ui-build-config.json

# Get UI build project name from CloudFront stack outputs
UI_BUILD_PROJECT=$(cat cloudfront-outputs.json | grep -o '"UIBuildProjectName": "[^"]*"' | cut -d'"' -f4 | head -1)

if [ -n "$UI_BUILD_PROJECT" ]; then
    echo "UI Build Project: $UI_BUILD_PROJECT"

    # Extract configuration values
    USER_POOL_ID=$(cat ui-build-config.json | grep -o '"UserPoolId": "[^"]*"' | cut -d'"' -f4 | head -1)
    USER_POOL_CLIENT_ID=$(cat ui-build-config.json | grep -o '"UserPoolClientId": "[^"]*"' | cut -d'"' -f4 | head -1)
    REST_API_URL=$(cat ui-build-config.json | grep -o '"RestApiUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
    WEBSOCKET_URL=$(cat ui-build-config.json | grep -o '"WebSocketApiUrl": "[^"]*"' | cut -d'"' -f4 | head -1)

    echo "Configuration for UI build:"
    echo "  User Pool ID: $USER_POOL_ID"
    echo "  Client ID: $USER_POOL_CLIENT_ID"
    echo "  REST API URL: $REST_API_URL"
    echo "  WebSocket URL: $WEBSOCKET_URL"

    # Validate required configuration
    if [ -z "$USER_POOL_ID" ] || [ -z "$USER_POOL_CLIENT_ID" ] || [ -z "$REST_API_URL" ] || [ -z "$WEBSOCKET_URL" ]; then
        echo "✗ Missing required configuration values for UI build"
        [ -z "$USER_POOL_ID" ] && echo "  - USER_POOL_ID is empty"
        [ -z "$USER_POOL_CLIENT_ID" ] && echo "  - USER_POOL_CLIENT_ID is empty"
        [ -z "$REST_API_URL" ] && echo "  - REST_API_URL is empty"
        [ -z "$WEBSOCKET_URL" ] && echo "  - WEBSOCKET_URL is empty"
        exit 1
    fi

    # Trigger UI build via CodeBuild
    echo "Starting UI build via CodeBuild..."
    ENV_VARS_OVERRIDE="[
      {\"name\": \"USER_POOL_ID\", \"value\": \"$USER_POOL_ID\"},
      {\"name\": \"USER_POOL_CLIENT_ID\", \"value\": \"$USER_POOL_CLIENT_ID\"},
      {\"name\": \"REST_API_URL\", \"value\": \"$REST_API_URL\"},
      {\"name\": \"WEBSOCKET_URL\", \"value\": \"$WEBSOCKET_URL\"}
    ]"

    UI_BUILD_ID=$(aws codebuild start-build \
      --project-name "$UI_BUILD_PROJECT" \
      --environment-variables-override "$ENV_VARS_OVERRIDE" \
      --query 'build.id' --output text)

    if [ "$?" != "0" ] || [ -z "$UI_BUILD_ID" ]; then
        echo "✗ Could not start UI build project"
        exit 1
    fi

    echo "✓ UI build started successfully"
    echo "Build ID: $UI_BUILD_ID"

    # Monitor the UI build
    echo "Monitoring UI build progress..."
    ui_build_failed=false

    while true; do
        build_info=$(aws codebuild batch-get-builds --ids $UI_BUILD_ID 2>/dev/null)

        if [ $? -ne 0 ]; then
            echo "⚠ Warning: Could not get UI build status"
            sleep 30
            continue
        fi

        status=$(echo $build_info | jq -r '.builds[0].buildStatus // "UNKNOWN"')
        phase=$(echo $build_info | jq -r '.builds[0].currentPhase // "UNKNOWN"')

        echo "$(date): Status: $status, Phase: $phase"

        if [ "$status" == "SUCCEEDED" ]; then
            echo "✓ UI build and deployment completed successfully!"
            break
        elif [ "$status" == "FAILED" ] || [ "$status" == "STOPPED" ] || [ "$status" == "FAULT" ] || [ "$status" == "TIMED_OUT" ]; then
            echo "✗ UI build failed with status: $status"
            ui_build_failed=true
            break
        else
            echo "Build is still in progress... sleeping for 30 seconds"
        fi

        sleep 30
    done

    if [ "$ui_build_failed" = true ]; then
        echo "✗ UI build and deployment failed"
        echo "Check CodeBuild logs for details"
        exit 1
    fi
else
    echo "✗ Could not find UI build project name in outputs"
    exit 1
fi

# Merge all outputs into final cdk-outputs.json
echo "Merging all stack outputs..."
jq -s 'add' core-outputs.json cloudfront-outputs.json > cdk-outputs.json
rm -f ui-build-config.json

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""

if [ -f "cdk-outputs.json" ]; then
    echo "Deployment Outputs:"
    echo ""
    
    # Extract key outputs
    REST_API_URL=$(cat cdk-outputs.json | grep -o '"RestApiUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
    WSS_URL=$(cat cdk-outputs.json | grep -o '"WebSocketUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
    CLOUDFRONT_URL=$(cat cdk-outputs.json | grep -o '"CloudFrontDistributionUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
    USER_POOL_ID=$(cat cdk-outputs.json | grep -o '"UserPoolId": "[^"]*"' | cut -d'"' -f4 | head -1)
    USER_POOL_CLIENT_ID=$(cat cdk-outputs.json | grep -o '"UserPoolClientId": "[^"]*"' | cut -d'"' -f4 | head -1)
    
    [ -n "$REST_API_URL" ] && echo "  REST API URL: $REST_API_URL"
    [ -n "$WSS_URL" ] && echo "  WebSocket URL: $WSS_URL"
    [ -n "$CLOUDFRONT_URL" ] && echo "  Frontend URL: $CLOUDFRONT_URL"
    [ -n "$USER_POOL_ID" ] && echo "  User Pool ID: $USER_POOL_ID"
    [ -n "$USER_POOL_CLIENT_ID" ] && echo "  User Pool Client ID: $USER_POOL_CLIENT_ID"
    
    echo ""
    echo "Full outputs saved to: cdk-outputs.json"
else
    echo "Note: cdk-outputs.json not found. Check AWS Console for outputs."
fi

echo ""
echo "Next Steps:"
echo "  1. Create a Cognito user: aws cognito-idp admin-create-user --user-pool-id <USER_POOL_ID> --username <EMAIL>"
echo "  2. Access the frontend at the CloudFront URL"
echo "  3. Upload a PDF document and extract insights"
echo ""
echo "Deployment Complete"