#!/bin/bash
set -e

# Document Insight Extraction System - Destroy Script
# This script removes all deployed resources

echo "=========================================="
echo "Document Insight Extraction System"
echo "Destroy Script"
echo "=========================================="
echo ""

# Get environment (default to dev)
ENV=${1:-dev}
echo "WARNING: This will destroy all resources in environment: $ENV"
echo ""

# Set AWS environment variables
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=${AWS_REGION:-us-east-1}

echo "AWS Account: $CDK_DEFAULT_ACCOUNT"
echo "AWS Region: $CDK_DEFAULT_REGION"
echo ""

# Confirm destruction
read -p "Are you sure you want to destroy all resources? (yes/NO): " -r
echo
if [[ ! $REPLY == "yes" ]]; then
    echo "Destruction cancelled."
    exit 0
fi

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Destroy stacks
echo "Destroying stacks..."
cdk destroy --context env=$ENV --all --force

echo ""
echo "=========================================="
echo "Destruction Complete!"
echo "=========================================="
