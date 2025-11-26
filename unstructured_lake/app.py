#!/usr/bin/env python3
"""
Document Insight Extraction System - CDK Application Entry Point

This application deploys a serverless document processing and insight extraction
system using AWS services including S3, Lambda, API Gateway, DynamoDB, and Bedrock.

Stack Dependencies:
1. Cognito Stack (authentication)
2. S3 Stack (document and vector storage)
3. Lambda Layer Stack (dependencies)
4. DynamoDB Stack (cache)
5. WebSocket API Stack (real-time updates)
6. Lambda Function Stack (processing and extraction)
7. API Gateway Stack (REST endpoints)
8. AppRunner Stack (frontend hosting)
"""
import os
import aws_cdk as cdk
from aws_cdk import Tags

from infrastructure.cognito_stack import CognitoAuthStack
from infrastructure.s3_stack import S3BucketStack
from infrastructure.lambda_layer_stack import LambdaLayerStack
from infrastructure.dynamodb_stack import DynamoDBStack
from infrastructure.processing_status_stack import ProcessingStatusStack

from infrastructure.lambda_function_stack import LambdaFunctionStack
from infrastructure.api_gateway_stack import ApiGatewayStack
from infrastructure.ecr_stack import ECRStack
from infrastructure.apprunner_hosting_stack import AppRunnerHostingStack

# Initialize CDK app
app = cdk.App()

# Get environment configuration
env_name = app.node.try_get_context("env") or "dev"
config = app.node.try_get_context(env_name)

if not config:
    raise ValueError(f"Configuration for environment '{env_name}' not found in cdk.json")

# Get AWS account and region from environment or use defaults
account_id = os.getenv('CDK_DEFAULT_ACCOUNT')
region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
env = cdk.Environment(account=account_id, region=region)

print(f"Deploying to environment: {env_name}")
print(f"AWS Account: {account_id}")
print(f"AWS Region: {region}")

# ============================================================================
# STEP 1: Create Cognito authentication stack
# ============================================================================
cognito_stack = CognitoAuthStack(
    app,
    f"DocumentInsightCognito{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    description=f"Document Insight Extraction System - Cognito Auth - {env_name} environment"
)

# ============================================================================
# STEP 2: Create S3 bucket stack (documents and vectors)
# ============================================================================
s3_stack = S3BucketStack(
    app,
    f"DocumentInsightS3{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    description=f"Document Insight Extraction System - S3 Buckets - {env_name} environment"
)

# ============================================================================
# STEP 3: Create Lambda Layer stack (pypdf, boto3)
# ============================================================================
lambda_layer_stack = LambdaLayerStack(
    app,
    f"DocumentInsightLambdaLayer{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    description=f"Document Insight Extraction System - Lambda Layers - {env_name} environment"
)

# ============================================================================
# STEP 4: Create DynamoDB stack (insights cache)
# ============================================================================
dynamodb_stack = DynamoDBStack(
    app,
    f"DocumentInsightDynamoDB{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    description=f"Document Insight Extraction System - DynamoDB Cache - {env_name} environment"
)

# ============================================================================
# STEP 4b: Create Processing Status DynamoDB stack
# ============================================================================
processing_status_stack = ProcessingStatusStack(
    app,
    f"DocumentInsightProcessingStatus{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    description=f"Document Insight Extraction System - Processing Status Table - {env_name} environment"
)

# ============================================================================
# STEP 5: Create Lambda Function stack (document processor and insight extractor)
# ============================================================================
lambda_function_stack = LambdaFunctionStack(
    app,
    f"DocumentInsightLambda{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    description=f"Document Insight Extraction System - Lambda Functions - {env_name} environment"
)

# Create WebSocket API first (without routes)
websocket_api = lambda_function_stack.create_websocket_api()

# Create Document Processing Lambda with WebSocket URL placeholder
document_processor_lambda = lambda_function_stack.create_document_processor_lambda(
    documents_bucket_name=s3_stack.documents_bucket.bucket_name,
    vector_bucket_name=s3_stack.vector_bucket_name,
    vector_index_arn=s3_stack.vector_index_arn,
    websocket_url="wss-placeholder",  # Will be updated after WebSocket configuration
    processing_status_table_name=processing_status_stack.processing_status_table.table_name,
    pypdf_layer_arn=lambda_layer_stack.pypdf_layer_arn,
    boto3_layer_arn=lambda_layer_stack.boto3_layer_arn,
    langchain_layer_arn=lambda_layer_stack.langchain_layer_arn
)

# Configure WebSocket routes with Document Processor Lambda and get the URL
websocket_url = lambda_function_stack.configure_websocket_routes(document_processor_lambda, websocket_api)

# Update Document Processor Lambda with actual WebSocket URL
document_processor_lambda.add_environment("WSS_URL", websocket_url)

# Create Document API Lambda
document_api_lambda = lambda_function_stack.create_document_api_lambda(
    documents_bucket_name=s3_stack.documents_bucket.bucket_name,
    processing_status_table_name=processing_status_stack.processing_status_table.table_name,
    boto3_layer_arn=lambda_layer_stack.boto3_layer_arn
)

# Create Insight Extraction Lambda
insight_extractor_lambda = lambda_function_stack.create_insight_extractor_lambda(
    vector_bucket_name=s3_stack.vector_bucket_name,
    vector_index_arn=s3_stack.vector_index_arn,
    dynamodb_table_name=dynamodb_stack.insights_cache_table.table_name,
    boto3_layer_arn=lambda_layer_stack.boto3_layer_arn
)

# Grant S3 Vectors permissions to Insight Extractor
lambda_function_stack.grant_insight_extractor_s3_permissions(
    vector_bucket_name=s3_stack.vector_bucket_name,
    vector_index_arn=s3_stack.vector_index_arn
)

# Grant Bedrock permissions to Insight Extractor
lambda_function_stack.grant_insight_extractor_bedrock_permissions()

# Grant DynamoDB permissions to Insight Extractor
lambda_function_stack.grant_insight_extractor_dynamodb_permissions(
    dynamodb_table_arn=dynamodb_stack.insights_cache_table.table_arn
)

# Create Image Insights Lambda
image_insights_lambda = lambda_function_stack.create_image_insights_lambda(
    pypdf_layer_arn=lambda_layer_stack.pypdf_layer_arn,
    boto3_layer_arn=lambda_layer_stack.boto3_layer_arn
)

# Configure S3 event notifications to trigger Document Processor
# Note: This is done in the Lambda Function stack to avoid cyclic dependencies
#lambda_function_stack.configure_s3_event_notifications(s3_stack.documents_bucket)

# ============================================================================
# STEP 6: Create API Gateway stack (REST endpoints)
# ============================================================================
api_gateway_stack = ApiGatewayStack(
    app,
    f"DocumentInsightApiGateway{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    cognito_user_pool=cognito_stack.user_pool,
    insight_extractor_arn=insight_extractor_lambda.function_arn,
    document_processor_arn=document_processor_lambda.function_arn,
    document_api_arn=document_api_lambda.function_arn,
    image_insights_arn=image_insights_lambda.function_arn,
    description=f"Document Insight Extraction System - API Gateway - {env_name} environment"
)

# ============================================================================
# STEP 7: Create ECR stack (Docker image repository and build)
# ============================================================================
ecr_stack = ECRStack(
    app,
    f"DocumentInsightECR{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    description=f"Document Insight Extraction System - ECR Repository - {env_name} environment"
)

# ============================================================================
# STEP 8: Create AppRunner hosting stack (frontend)
# ============================================================================
apprunner_stack = AppRunnerHostingStack(
    app,
    f"DocumentInsightAppRunner{env_name.capitalize()}Stack",
    env=env,
    env_name=env_name,
    config=config,
    api_endpoint=api_gateway_stack.rest_api.url,
    wss_endpoint=websocket_url,
    user_pool_id=cognito_stack.user_pool.user_pool_id,
    user_pool_client_id=cognito_stack.user_pool_client.user_pool_client_id,
    ecr_repository_uri=ecr_stack.ecr_repository.repository_uri,
    description=f"Document Insight Extraction System - AppRunner Hosting - {env_name} environment"
)

# ============================================================================
# Configure stack dependencies
# ============================================================================
# Lambda Function stack depends on S3, Lambda Layers, DynamoDB, and Processing Status
lambda_function_stack.add_dependency(s3_stack)
lambda_function_stack.add_dependency(lambda_layer_stack)
lambda_function_stack.add_dependency(dynamodb_stack)
lambda_function_stack.add_dependency(processing_status_stack)
# Removed WebSocket dependency to avoid cyclic reference

# API Gateway stack depends on Cognito and Lambda Functions
api_gateway_stack.add_dependency(cognito_stack)
api_gateway_stack.add_dependency(lambda_function_stack)

# ECR stack is independent (no dependencies)

# AppRunner stack depends on API Gateway, Lambda Functions (includes WebSocket), Cognito, and ECR
apprunner_stack.add_dependency(api_gateway_stack)
apprunner_stack.add_dependency(lambda_function_stack)
apprunner_stack.add_dependency(cognito_stack)
apprunner_stack.add_dependency(ecr_stack)

# ============================================================================
# Apply common tags to all stacks
# ============================================================================
all_stacks = [
    cognito_stack,
    s3_stack,
    lambda_layer_stack,
    dynamodb_stack,
    processing_status_stack,
    lambda_function_stack,  # Now includes WebSocket API
    api_gateway_stack,
    ecr_stack,
    apprunner_stack
]

for stack in all_stacks:
    Tags.of(stack).add("Project", "DocumentInsightExtraction")
    Tags.of(stack).add("Environment", env_name)
    Tags.of(stack).add("ManagedBy", "CDK")
    Tags.of(stack).add("Application", "DocumentProcessing")
    Tags.of(stack).add("CostCenter", config.get("cost_center", "Engineering"))
    Tags.of(stack).add("Owner", config.get("owner", "Platform Team"))

# ============================================================================
# Synthesize CloudFormation template
# ============================================================================
app.synth()
