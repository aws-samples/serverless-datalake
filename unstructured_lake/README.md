# Document Insight Extraction System (Built with Kiro)

A serverless AWS CDK application for processing PDF documents, generating vector embeddings, and extracting structured insights using Amazon Bedrock.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Installation](#installation)
- [Deployment](#deployment)
- [Post-Deployment Setup](#post-deployment-setup)
- [Usage](#usage)
- [Environment Variables](#environment-variables)
- [CDK Commands](#cdk-commands)
- [Troubleshooting](#troubleshooting)
- [Cost Estimation](#cost-estimation)
- [Security](#security)
- [License](#license)

## Architecture Overview

This system provides a complete serverless solution for document processing and insight extraction:

- **Document Upload**: Direct S3 upload via presigned URLs
- **Automated Processing**: Event-driven PDF text extraction and OCR using Amazon Bedrock
- **Vector Embeddings**: Amazon Titan V2 embeddings stored in S3 Vector buckets
- **Insight Extraction**: Natural language queries powered by Claude 3 Sonnet
- **Real-time Updates**: WebSocket notifications for processing progress
- **Intelligent Caching**: DynamoDB cache with 24-hour TTL for faster repeated queries
- **Modern Frontend**: React application with AWS Cloudscape Design System hosted on AppRunner

### Architecture Diagram

```
User → AppRunner (React UI) → API Gateway (REST) → Lambda Functions
                            ↓                           ↓
                      WebSocket API              S3 (Documents)
                            ↓                           ↓
                      Lambda (Progress)         S3 Vectors (Embeddings)
                                                        ↓
                                                  DynamoDB (Cache)
                                                        ↓
                                                  Amazon Bedrock
```

## Features

- ✅ **PDF Processing**: Extract text and images from PDF documents
- ✅ **OCR Support**: Optical character recognition for images using Bedrock
- ✅ **Vector Search**: Semantic search using S3 Vectors with metadata filtering
- ✅ **Insight Extraction**: Generate structured insights from natural language prompts
- ✅ **Real-time Progress**: WebSocket updates during document processing
- ✅ **Caching**: Intelligent caching of insights for 24 hours
- ✅ **Authentication**: Cognito user pool for secure access
- ✅ **Auto-scaling**: AppRunner and Lambda auto-scale based on demand
- ✅ **Multi-environment**: Separate dev and prod configurations

## Prerequisites

Before deploying, ensure you have the following installed:

- **AWS CLI**: Version 2.x or later ([Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
  ```bash
  aws --version
  aws configure  # Configure with your credentials
  ```

- **AWS CDK**: Version 2.192.0 or later ([Installation Guide](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html))
  ```bash
  npm install -g aws-cdk
  cdk --version
  ```

- **Python**: Version 3.12 or later ([Download](https://www.python.org/downloads/))
  ```bash
  python3 --version
  ```

- **Node.js**: Version 18 or later ([Download](https://nodejs.org/))
  ```bash
  node --version
  npm --version
  ```

- **AWS Account Requirements**:
  - Access to Amazon Bedrock with model access enabled for:
    - `amazon.titan-embed-text-v2:0` (embeddings)
    - `global.anthropic.claude-sonnet-4-20250514-v1:0` (insights)
  - Sufficient service quotas for Lambda, API Gateway, AppRunner, etc.


## Configuration

The system supports multiple environments with configuration in `cdk.json`:

### Development Environment (`dev`)

```json
{
  "lambda_memory": 3008,
  "lambda_timeout": 600,
  "apprunner_cpu": "2048",
  "apprunner_memory": "4096",
  "apprunner_min_instances": 1,
  "apprunner_max_instances": 10,
  "api_throttle_rate": 1000,
  "enable_xray_tracing": false
}
```

### Production Environment (`prod`)

```json
{
  "lambda_memory": 10240,
  "lambda_timeout": 900,
  "apprunner_cpu": "4096",
  "apprunner_memory": "8192",
  "apprunner_min_instances": 2,
  "apprunner_max_instances": 25,
  "api_throttle_rate": 5000,
  "enable_xray_tracing": true
}
```

### Customization

You can customize the configuration by editing `cdk.json`:

- **Model IDs**: Change Bedrock models (`embed_model_id`, `insight_model_id`)
- **Chunking**: Adjust chunk size and overlap (`chunk_size`, `chunk_overlap`)
- **Cache TTL**: Modify cache expiration (`cache_ttl_hours`)
- **Resource Limits**: Set Lambda memory, timeout, concurrency limits

## Installation

### 1. Clone the Repository

```bash
cd document-insight-extraction
```

### 2. Create Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```


## Deployment

### Automated Deployment (Recommended)

Use the installer script for fully automated deployment via CodeBuild:

```bash
# Make script executable
chmod +x installer.sh

# Deploy to development environment
./installer.sh dev

# Deploy to production environment
./installer.sh prod
```

The installer will:
1. Create a CodeBuild project with all necessary permissions
2. Upload your code to S3
3. Execute the complete deployment automatically
4. Monitor progress and display results
5. Handle Lambda layer builds, CDK deployment, and frontend Docker image

## Post-Deployment Setup

### 1. Access the Application

Head to AppRunner to access the frontend url.
Open the URL in your browser and log in with your Cognito credentials.

## Usage

### Upload a Document

1. Log in to the frontend application
2. Click "Upload Document"
3. Select a PDF file (up to 100 MB)
4. Monitor real-time processing progress via WebSocket
5. Wait for processing to complete

### Extract Insights

1. Select a processed document from the list
2. Enter a natural language prompt, e.g.:
   - "Summarize the key points of this document"
   - "Extract all dates and events mentioned"
   - "List all people and organizations"
3. Click "Extract Insights"
4. View structured JSON results
5. Export as JSON or CSV

### API Usage

You can also use the REST API directly:

```bash
# Get presigned URL for upload
curl -X POST https://API_ENDPOINT/documents/presigned-url \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fileName": "document.pdf", "fileSize": 1024000}'

# Extract insights
curl -X POST https://API_ENDPOINT/insights/extract \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"docId": "abc123", "prompt": "Summarize this document"}'

# Retrieve cached insights
curl -X GET https://API_ENDPOINT/insights/abc123 \
  -H "Authorization: Bearer $ID_TOKEN"
```

## Environment Variables

The following environment variables are used during deployment:

- `CDK_DEFAULT_ACCOUNT`: AWS account ID (auto-detected)
- `CDK_DEFAULT_REGION`: AWS region (default: us-east-1)
- `AWS_REGION`: Alternative to CDK_DEFAULT_REGION

Lambda functions use these environment variables (set automatically):

- `VECTOR_BUCKET_NAME`: S3 Vector bucket name
- `VECTOR_INDEX_ARN`: S3 Vector index ARN
- `EMBED_MODEL_ID`: Bedrock embedding model ID
- `INSIGHT_MODEL_ID`: Bedrock insight model ID
- `DYNAMODB_TABLE_NAME`: DynamoDB cache table name
- `WSS_URL`: WebSocket API URL
- `REGION`: AWS region
- `LOG_LEVEL`: Logging level (INFO/WARN/ERROR)

## CDK Commands

Common CDK commands for managing the infrastructure:

```bash
# List all stacks
cdk ls --context env=dev

# Synthesize CloudFormation templates
cdk synth --context env=dev

# Show differences between deployed and local
cdk diff --context env=dev

# Deploy specific stack
cdk deploy --context env=dev DocumentInsightCognitoDevStack

# Deploy all stacks
cdk deploy --context env=dev --all

# Destroy all stacks
cdk destroy --context env=dev --all

# Watch mode (auto-deploy on changes)
cdk watch --context env=dev
```

## Troubleshooting

### CDK Bootstrap Issues

**Problem**: CDK bootstrap fails or stacks can't be deployed

**Solution**:
```bash
cdk bootstrap \
  --trust $CDK_DEFAULT_ACCOUNT \
  --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess \
  aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION
```

### Python Virtual Environment Issues

**Problem**: Module import errors or dependency conflicts

**Solution**:
```bash
deactivate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### S3 Vectors Not Working

**Problem**: Vector queries fail or return no results

**Solution**:
- Ensure S3 Vectors feature is available in your region
- Check that vector index is created correctly
- Verify metadata filtering syntax
- Check CloudWatch logs for detailed errors

### Bedrock Access Denied

**Problem**: Lambda functions can't invoke Bedrock models

**Solution**:
1. Enable model access in Bedrock console
2. Wait for approval (may take time for Claude)
3. Verify IAM permissions in Lambda execution role
4. Check model IDs in configuration match available models

### AppRunner Deployment Fails

**Problem**: AppRunner service fails to start or health checks fail

**Solution**:
- Check Docker image was pushed to ECR successfully
- Verify environment variables are set correctly
- Check AppRunner logs in CloudWatch
- Ensure health check endpoint `/health` exists

### WebSocket Connection Issues

**Problem**: Real-time updates not working

**Solution**:
- Verify WebSocket URL is correct
- Check CORS configuration
- Ensure Cognito token is included in connection
- Check CloudWatch logs for WebSocket Lambda

### Stack Deployment Failures

**Problem**: CDK deploy fails with CloudFormation errors

**Solution**:
```bash
# View detailed logs
cdk deploy --context env=dev --verbose

# Check CloudFormation console for specific errors
# Common issues:
# - Resource limits exceeded
# - IAM permission issues
# - Resource name conflicts

# Force destroy and redeploy
cdk destroy --context env=dev --force
cdk deploy --context env=dev --all
```

### Cost Overruns

**Problem**: AWS costs higher than expected

**Solution**:
- Check CloudWatch metrics for Lambda invocations
- Review Bedrock usage in Cost Explorer
- Verify DynamoDB is using on-demand billing
- Check AppRunner instance count and size
- Enable cost allocation tags for better tracking

## Cost Estimation

### Development Environment

Estimated monthly costs for 1,000 documents (10 pages average):

| Service | Usage | Cost |
|---------|-------|------|
| Lambda (Processing) | 10,000 invocations, 3GB, 60s avg | $50 |
| Lambda (Insights) | 5,000 invocations, 3GB, 30s avg | $30 |
| S3 (Documents) | 10 GB storage, 1,000 uploads | $5 |
| S3 Vectors | 5 GB storage, 5,000 queries | $20 |
| DynamoDB | 10,000 reads, 5,000 writes | $10 |
| Bedrock (Titan V2) | 100,000 embeddings | $40 |
| Bedrock (Claude 3) | 5,000 queries, 50K tokens avg | $60 |
| API Gateway | 15,000 requests | $10 |
| AppRunner | 1 instance, 2 vCPU, 4 GB | $25 |
| **Total** | | **~$250/month** |

### Production Environment

Costs scale linearly with usage. For 10,000 documents/month:

- Lambda: ~$800/month
- Bedrock: ~$1,000/month
- Other services: ~$200/month
- **Total**: ~$2,000/month

### Cost Optimization Tips

1. **Use caching**: DynamoDB cache reduces Bedrock costs by 50-70%
2. **Batch processing**: Process multiple documents together
3. **Right-size Lambda**: Adjust memory based on actual usage
4. **AppRunner auto-scaling**: Scale to zero during low usage
5. **S3 lifecycle policies**: Archive old documents to Glacier
6. **Reserved capacity**: Use Savings Plans for predictable workloads

## Security

### Data Protection

- **Encryption at Rest**:
  - S3 buckets: SSE-S3 encryption
  - DynamoDB: AWS-managed encryption
  - S3 Vectors: Encrypted by default

- **Encryption in Transit**:
  - All API calls over HTTPS/WSS
  - TLS 1.2+ enforced

### Access Control

- **Authentication**: Cognito User Pool with JWT tokens
- **Authorization**: API Gateway Cognito authorizer on all endpoints
- **IAM Roles**: Least privilege principle for Lambda execution roles
- **S3 Bucket Policies**: Restrict access to Lambda functions only

### Network Security

- **API Gateway**: Regional endpoint with throttling
- **AppRunner**: Private VPC option available
- **Lambda**: VPC configuration optional for enhanced security

### Compliance

- **Audit Logging**: CloudTrail enabled for all API calls
- **Access Logs**: S3 and API Gateway access logging
- **Monitoring**: CloudWatch metrics and alarms

### Best Practices

1. **Rotate Credentials**: Regularly rotate IAM access keys
2. **MFA**: Enable MFA for Cognito users in production
3. **Least Privilege**: Review and minimize IAM permissions
4. **Secrets Management**: Use AWS Secrets Manager for sensitive data
5. **Regular Updates**: Keep dependencies and Lambda runtimes updated

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:

- **Documentation**: See additional docs in the repository
- **Issues**: Create an issue in the repository
- **AWS Support**: Contact AWS Support for service-specific issues

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [S3 Vectors Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vector-search.html)
- [AWS AppRunner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Project Architecture](ARCHITECTURE.md)
- [Lambda Layers Guide](LAMBDA_LAYERS.md)
- [WebSocket Implementation](infrastructure/WEBSOCKET_IMPLEMENTATION.md)
