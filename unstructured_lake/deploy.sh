#!/bin/bash
set -e

# Document Insight Extraction System - Local Deployment Script
# This script provides a local deployment option with full control
# For automated deployment via CodeBuild, use installer.sh instead

echo "=========================================="
echo "Document Insight Extraction System"
echo "Local Deployment Script"
echo "=========================================="
echo ""
echo "Note: For automated deployment via CodeBuild, use './installer.sh [env]' instead"
echo ""

# ============================================================================
# Configuration
# ============================================================================

# Get environment (default to dev)
ENV=${1:-dev}

echo "Deployment Configuration:"
echo "  Environment: $ENV"
echo ""

# ============================================================================
# Prerequisites Check
# ============================================================================

echo "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is required but not installed."; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "Error: AWS CLI is required but not installed."; exit 1; }
command -v cdk >/dev/null 2>&1 || { echo "Error: AWS CDK is required but not installed. Run: npm install -g aws-cdk"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Error: Node.js is required but not installed."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Error: Docker is required for UI build but not installed."; exit 1; }

echo "✓ All prerequisites satisfied"
echo ""

# ============================================================================
# AWS Environment Setup
# ============================================================================

echo "Setting up AWS environment..."

export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=${AWS_REGION:-us-east-1}

echo "  AWS Account: $CDK_DEFAULT_ACCOUNT"
echo "  AWS Region: $CDK_DEFAULT_REGION"
echo ""

# ============================================================================
# Python Environment Setup
# ============================================================================

echo "Setting up Python environment..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "  Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "  Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "✓ Python environment ready"
echo ""

# ============================================================================
# CDK Bootstrap (if needed)
# ============================================================================

echo "Checking CDK bootstrap status..."
read -p "Do you need to bootstrap CDK? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Bootstrapping CDK..."
    cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION
    echo "✓ CDK bootstrap complete"
else
    echo "Skipping CDK bootstrap"
fi
echo ""

# ============================================================================
# CDK Synthesis
# ============================================================================

echo "Synthesizing CloudFormation templates..."
cdk synth --context env=$ENV --quiet
echo "✓ CloudFormation templates synthesized"
echo ""

# ============================================================================
# CDK Deployment
# ============================================================================

echo "Deploying CDK stacks..."
echo "This will deploy the following stacks:"
echo "  1. Cognito Stack (authentication)"
echo "  2. S3 Stack (document and vector storage)"
echo "  3. Lambda Layer Stack (dependencies)"
echo "  4. DynamoDB Stack (cache)"
echo "  5. WebSocket API Stack (real-time updates)"
echo "  6. Lambda Function Stack (processing and extraction)"
echo "  7. API Gateway Stack (REST endpoints)"
echo "  8. CloudFront Stack (frontend hosting)"
echo ""
echo "Note: Lambda layers will be built automatically via CodeBuild during deployment"
echo ""

read -p "Ready to deploy all stacks? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deploying stacks..."
    cdk deploy --context env=$ENV --all --require-approval never --outputs-file cdk-outputs.json
    
    echo ""
    echo "✓ CDK stacks deployed successfully"
else
    echo "Deployment cancelled."
    exit 0
fi
echo ""

# ============================================================================
# Frontend Build and Deploy to S3 + CloudFront
# ============================================================================

echo "Building and deploying frontend to S3 + CloudFront..."

read -p "Build and deploy UI? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "cdk-outputs.json" ]; then
        UI_BUCKET=$(cat cdk-outputs.json | grep -o '"UIBucketName": "[^"]*"' | cut -d'"' -f4 | head -1)
        DISTRIBUTION_ID=$(cat cdk-outputs.json | grep -o '"CloudFrontDistributionId": "[^"]*"' | cut -d'"' -f4 | head -1)
        REST_API_URL=$(cat cdk-outputs.json | grep -o '"RestApiUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
        WEBSOCKET_URL=$(cat cdk-outputs.json | grep -o '"WebSocketUrl": "[^"]*"' | cut -d'"' -f4 | head -1)
        USER_POOL_ID=$(cat cdk-outputs.json | grep -o '"UserPoolId": "[^"]*"' | cut -d'"' -f4 | head -1)
        USER_POOL_CLIENT_ID=$(cat cdk-outputs.json | grep -o '"UserPoolClientId": "[^"]*"' | cut -d'"' -f4 | head -1)

        if [ -n "$UI_BUCKET" ] && [ -n "$DISTRIBUTION_ID" ]; then
            echo "  S3 Bucket: $UI_BUCKET"
            echo "  Distribution ID: $DISTRIBUTION_ID"

            cd frontend

            # Create config.json
            mkdir -p src/config
            jq -n \
              --arg region "$CDK_DEFAULT_REGION" \
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

            echo "  Generated config.json"

            # Install and build
            echo "  Installing dependencies..."
            npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund --legacy-peer-deps

            echo "  Building React app..."
            npm run build

            # Sync to S3
            echo "  Syncing to S3..."
            aws s3 sync dist/ s3://$UI_BUCKET/ --delete

            # Invalidate CloudFront
            echo "  Invalidating CloudFront cache..."
            aws cloudfront create-invalidation \
              --distribution-id "$DISTRIBUTION_ID" \
              --paths "/*" > /dev/null

            cd ..

            echo "✓ Frontend deployed successfully"
        else
            echo "  Warning: Could not find UI bucket or distribution ID in outputs"
        fi
    else
        echo "  Warning: cdk-outputs.json not found. Deploy CDK stacks first."
    fi
else
    echo "Skipping UI deployment"
fi
echo ""

# ============================================================================
# Display Deployment Outputs
# ============================================================================

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
echo "For more information, see README.md"
echo ""
