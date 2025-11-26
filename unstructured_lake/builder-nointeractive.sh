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
  DocumentInsightWebSocket${infra_env^}Stack \
  DocumentInsightLambda${infra_env^}Stack \
  DocumentInsightApiGateway${infra_env^}Stack \
  --require-approval never --outputs-file core-outputs.json

if [ $? -eq 0 ]; then
    echo "✓ Core infrastructure stacks deployed successfully"
else
    echo "✗ Core infrastructure deployment failed"
    exit 1
fi

echo "--- CDK deploy ECR stack ---"
# Deploy ECR stack separately
cdk deploy --context env=$infra_env \
  DocumentInsightECR${infra_env^}Stack \
  --require-approval never --outputs-file ecr-outputs.json

if [ $? -eq 0 ]; then
    echo "✓ ECR stack deployed successfully"
else
    echo "✗ ECR stack deployment failed"
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

echo "--- Building and pushing frontend Docker image via CodeBuild ---"
if [ -f "ecr-outputs.json" ]; then
    # Merge core and ECR outputs for configuration extraction
    echo "Merging core and ECR outputs for UI build configuration..."
    jq -s 'add' core-outputs.json ecr-outputs.json > ui-build-config.json
    
    # Get UI build project name from ECR stack outputs
    UI_BUILD_PROJECT=$(cat ecr-outputs.json | grep -o '"UIBuildProjectName": "[^"]*"' | cut -d'"' -f4 | head -1)
    
    if [ -n "$UI_BUILD_PROJECT" ]; then
        echo "UI Build Project: $UI_BUILD_PROJECT"
        
        # Extract configuration values from merged outputs
        USER_POOL_ID=$(cat ui-build-config.json | grep -o '"UserPoolId": "[^"]*"' | cut -d'"' -f4 | head -1)
        USER_POOL_CLIENT_ID=$(cat ui-build-config.json | grep -o '"UserPoolClientId": "[^"]*"' | cut -d'"' -f4 | head -1)
        REST_API_URL=$(cat ui-build-config.json | grep -o '"RestApiUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
        WEBSOCKET_URL=$(cat ui-build-config.json | grep -o '"WebSocketApiUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
        
        echo "Configuration for UI build:"
        echo "  User Pool ID: $USER_POOL_ID"
        echo "  Client ID: $USER_POOL_CLIENT_ID"
        echo "  REST API URL: $REST_API_URL"
        echo "  WebSocket URL: $WEBSOCKET_URL"
        
        # Debug: Show all available outputs
        echo "Debug - All available outputs:"
        cat ui-build-config.json | jq '.'
        
        # Validate required configuration
        if [ -z "$USER_POOL_ID" ] || [ -z "$USER_POOL_CLIENT_ID" ] || [ -z "$REST_API_URL" ] || [ -z "$WEBSOCKET_URL" ]; then
            echo "✗ Missing required configuration values for UI build"
            echo "Missing values:"
            [ -z "$USER_POOL_ID" ] && echo "  - USER_POOL_ID is empty"
            [ -z "$USER_POOL_CLIENT_ID" ] && echo "  - USER_POOL_CLIENT_ID is empty"
            [ -z "$REST_API_URL" ] && echo "  - REST_API_URL is empty"
            [ -z "$WEBSOCKET_URL" ] && echo "  - WEBSOCKET_URL is empty"
            echo "Available output keys:"
            cat ui-build-config.json | jq 'keys'
            exit 1
        fi
        
        # Trigger UI build via CodeBuild with environment variables
        echo "Starting UI build via CodeBuild..."
        
        # Create environment variables override for CodeBuild
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
            echo "Falling back to local Docker build..."
            
            # Fallback to local build
            ECR_URI=$(cat ecr-outputs.json | grep -o '"ECRRepositoryUri": "[^"]*"' | cut -d'"' -f4 | head -1)
            
            if [ -n "$ECR_URI" ]; then
                echo "ECR Repository: $ECR_URI"
                
                # Navigate to frontend directory
                cd frontend
                
                # Create config.json using the same logic as buildspec
                echo "Creating environment configuration..."
                echo "Variables - Region:$deployment_region, UserPoolId:$USER_POOL_ID, ClientId:$USER_POOL_CLIENT_ID, API URL:$REST_API_URL, WebSocket URL:$WEBSOCKET_URL"
                
                # Create config directory and remove existing config files
                mkdir -p src/config
                rm -f src/config/config.json
                
                # Create config.json using jq (same as buildspec)
                jq -n \
                  --arg region "$deployment_region" \
                  --arg userPoolId "$USER_POOL_ID" \
                  --arg clientId "$USER_POOL_CLIENT_ID" \
                  --arg apiUrl "$REST_API_URL" \
                  --arg websocketUrl "$WEBSOCKET_URL" \
                  '{
                    region: $region,
                    userPoolId: $userPoolId,
                    clientId: $clientId,
                    apiUrl: $apiUrl,
                    websocketUrl: $websocketUrl
                  }' > src/config/config.json
                
                echo "Generated config.json:"
                cat src/config/config.json
                
                # Install npm dependencies (same as buildspec)
                echo "========================================="
                echo "Installing npm dependencies..."
                echo "========================================="
                echo "Clearing npm cache..."
                npm cache clean --force
                
                echo "Setting npm registry to default..."
                npm config set registry https://registry.npmjs.org/
                
                echo "Running npm ci with verbose logging..."
                if ! npm ci --verbose --no-audit --no-fund; then
                    echo "npm ci failed, trying with legacy peer deps..."
                    if ! npm ci --verbose --no-audit --no-fund --legacy-peer-deps; then
                        echo "npm ci with legacy-peer-deps failed, trying npm install as fallback..."
                        rm -rf node_modules package-lock.json
                        npm install --no-audit --no-fund --legacy-peer-deps
                    fi
                fi
                
                # Build React application
                echo "========================================="
                echo "Building React app with Vite..."
                echo "========================================="
                npm run build
                
                if [ $? -ne 0 ]; then
                    echo "✗ React build failed"
                    cd ..
                    exit 1
                fi
                
                echo "✓ React build completed successfully"
                echo "Build output size:"
                du -sh dist
                ls -la dist
                
                # Login to ECR
                echo "========================================="
                echo "Logging in to ECR..."
                echo "========================================="
                aws ecr get-login-password --region $deployment_region | docker login --username AWS --password-stdin $ECR_URI
                
                # Build Docker image
                echo "========================================="
                echo "Building Docker image..."
                echo "========================================="
                docker build -t document-insight-ui:latest .
                
                if [ $? -eq 0 ]; then
                    echo "✓ Docker image built successfully"
                    
                    # Tag and push image
                    echo "Tagging and pushing image..."
                    docker tag document-insight-ui:latest $ECR_URI:latest
                    docker push $ECR_URI:latest
                    
                    if [ $? -eq 0 ]; then
                        echo "✓ Docker image pushed successfully (local build)"
                    else
                        echo "✗ Failed to push Docker image"
                        cd ..
                        exit 1
                    fi
                else
                    echo "✗ Docker build failed"
                    cd ..
                    exit 1
                fi
                
                cd ..
            else
                echo "✗ Could not find ECR repository URI"
                exit 1
            fi
        else
            echo "✓ UI build started successfully"
            echo "Build ID: $UI_BUILD_ID"
            
            # Monitor the UI build
            echo "Monitoring UI build progress..."
            ui_build_failed=false
            
            while true; do
                # Get build status
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
                    echo "✓ UI build completed successfully!"
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
                echo "⚠ UI build failed - AppRunner may not start properly"
                echo "Check CodeBuild logs for details"
            fi
        fi
        
    else
        echo "✗ Could not find UI build project name in outputs"
        echo "Available outputs:"
        cat ecr-outputs.json | jq 'keys'
        exit 1
    fi
else
    echo "✗ ecr-outputs.json not found"
    exit 1
fi

echo ""
echo "=========================================="
echo "Docker Image Ready - Deploying AppRunner"
echo "=========================================="
echo ""

echo "--- CDK deploy AppRunner stack ---"
# Deploy AppRunner stack after Docker image is ready
cdk deploy --context env=$infra_env \
  DocumentInsightAppRunner${infra_env^}Stack \
  --require-approval never --outputs-file apprunner-outputs.json

if [ $? -eq 0 ]; then
    echo "✓ AppRunner stack deployed successfully"
    
    # Merge all outputs into final cdk-outputs.json
    echo "Merging all stack outputs..."
    jq -s 'add' core-outputs.json ecr-outputs.json apprunner-outputs.json > cdk-outputs.json
    
    # Clean up temporary config file
    rm -f ui-build-config.json
    
    # Trigger AppRunner deployment to ensure it picks up the latest image
    echo "Triggering AppRunner deployment..."
    APPRUNNER_SERVICE_ARN=$(cat apprunner-outputs.json | grep -o '"AppRunnerServiceArn": "[^"]*"' | cut -d'"' -f4 | head -1)
    
    if [ -n "$APPRUNNER_SERVICE_ARN" ]; then
        aws apprunner start-deployment --service-arn "$APPRUNNER_SERVICE_ARN" || echo "Note: AppRunner deployment will start automatically"
        echo "✓ AppRunner deployment triggered"
    fi
else
    echo "✗ AppRunner stack deployment failed"
    exit 1
fi

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
    APPRUNNER_URL=$(cat cdk-outputs.json | grep -o '"AppRunnerServiceUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
    USER_POOL_ID=$(cat cdk-outputs.json | grep -o '"UserPoolId": "[^"]*"' | cut -d'"' -f4 | head -1)
    USER_POOL_CLIENT_ID=$(cat cdk-outputs.json | grep -o '"UserPoolClientId": "[^"]*"' | cut -d'"' -f4 | head -1)
    
    [ -n "$REST_API_URL" ] && echo "  REST API URL: $REST_API_URL"
    [ -n "$WSS_URL" ] && echo "  WebSocket URL: $WSS_URL"
    [ -n "$APPRUNNER_URL" ] && echo "  Frontend URL: $APPRUNNER_URL"
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
echo "  2. Access the frontend at the AppRunner URL"
echo "  3. Upload a PDF document and extract insights"
echo ""
echo "Deployment Complete"