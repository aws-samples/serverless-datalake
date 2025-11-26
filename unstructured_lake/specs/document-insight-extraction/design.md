# Design Document

## Overview

The Document Insight Extraction System is a serverless, event-driven application built on AWS CDK (Python) that enables users to upload PDF documents, automatically process them into vector embeddings, and extract structured insights through natural language queries. The system leverages AWS managed services to provide a scalable, cost-effective solution with real-time progress tracking and intelligent caching.

### Key Design Principles

1. **Serverless-First**: All compute resources use Lambda functions to minimize operational overhead and costs
2. **Event-Driven Architecture**: S3 event notifications trigger processing workflows automatically
3. **Real-Time Communication**: WebSocket connections provide live progress updates during document ingestion
4. **Intelligent Caching**: DynamoDB with TTL reduces costs by caching frequently accessed insights
5. **Metadata-Driven Retrieval**: S3 Vectors metadata filtering enables document-specific queries
6. **Infrastructure as Code**: Complete AWS CDK implementation for reproducible deployments

## Architecture

### High-Level Architecture Diagram

```
┌─────────────┐
│   User      │
│  Browser    │
└──────┬──────┘
       │
       │ HTTPS
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS AppRunner                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  React UI (Cloudscape Design System)                   │ │
│  │  - Document Upload                                      │ │
│  │  - Document Selection                                   │ │
│  │  - Insight Extraction                                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
       │                                    │
       │ REST API                           │ WebSocket
       ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐
│  API Gateway     │              │  API Gateway     │
│  (REST)          │              │  (WebSocket)     │
└────────┬─────────┘              └────────┬─────────┘
         │                                  │
         │                                  │
         ▼                                  ▼
┌─────────────────────────────────────────────────────┐
│              Lambda Functions                        │
│  ┌──────────────────┐    ┌──────────────────────┐  │
│  │  Document        │    │  Insight Extraction  │  │
│  │  Processing      │    │  & Query             │  │
│  │  Lambda          │    │  Lambda              │  │
│  └──────────────────┘    └──────────────────────┘  │
└─────────────────────────────────────────────────────┘
         │                           │
         │                           │
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│  S3 Bucket       │       │  DynamoDB        │
│  (Documents)     │       │  (Cache)         │
│                  │       │  - docId (PK)    │
│  Event           │       │  - timestamp(SK) │
│  Notifications   │       │  - TTL (24h)     │
└────────┬─────────┘       └──────────────────┘
         │                           │
         │                           │
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│  S3 Vector       │       │  Amazon Bedrock  │
│  Bucket          │       │  - Titan V2      │
│  - Embeddings    │       │    Embeddings    │
│  - Metadata      │       │  - Claude/Other  │
│    Filtering     │       │    for Insights  │
└──────────────────┘       └──────────────────┘
```

### Component Interaction Flow

#### Document Upload Flow
1. User requests presigned POST URL from API Gateway
2. Lambda generates presigned URL for S3 bucket
3. User uploads PDF directly to S3 using presigned URL
4. S3 event notification triggers Document Processing Lambda
5. Lambda sends progress updates via WebSocket

#### Document Processing Flow
1. Lambda receives S3 event notification
2. Extract text from each page using pypdf
3. Detect images and perform OCR using Bedrock
4. After every 10 pages, chunk text (8192 tokens, 10% overlap)
5. Generate embeddings using Titan V2
6. Store vectors in S3 Vector Bucket with metadata
7. Send completion status via WebSocket

#### Insight Extraction Flow
1. User selects document and enters prompt
2. API Gateway routes request to Insight Extraction Lambda
3. Lambda checks DynamoDB cache for existing insights
4. If cache miss, query S3 Vectors with metadata filter
5. Send retrieved chunks to Bedrock for insight generation
6. Store insights in DynamoDB with TTL
7. Return JSON-formatted insights to user

## Components and Interfaces

### 1. CDK Infrastructure Stacks

#### Main Stack (`DocumentInsightStack`)
- Orchestrates all nested stacks
- Manages cross-stack dependencies
- Outputs API endpoints and service URLs

#### S3 Stack (`S3BucketStack`)
- **Document Bucket**: Stores uploaded PDF files
  - Versioning: Disabled
  - Lifecycle: Optional (configurable retention)
  - CORS: Enabled for presigned POST uploads
  - Event Notifications: Configured for Lambda triggers
- **S3 Vector Bucket**: Stores vector embeddings
  - Bucket Type: Vector bucket (preview feature)
  - Vector Index Configuration:
    - Dimensions: 1024 (Titan V2 output)
    - Distance Metric: Cosine similarity
    - Filterable Metadata Keys: `docId`, `pageRange`, `uploadTimestamp`
    - Non-Filterable Metadata Keys: `textChunk` (for context retrieval)

#### Lambda Stack (`LambdaFunctionStack`)
- **Document Processing Lambda**:
  - Runtime: Python 3.12
  - Architecture: x86_64 (for pypdf compatibility)
  - Memory: 3008 MB
  - Timeout: 600 seconds (10 minutes)
  - Layers: pypdf-layer, boto3-layer
  - Environment Variables:
    - `VECTOR_BUCKET_NAME`
    - `VECTOR_INDEX_ARN`
    - `EMBED_MODEL_ID`: `amazon.titan-embed-text-v2:0`
    - `WSS_URL`: WebSocket endpoint
    - `REGION`
  - IAM Permissions:
    - S3: GetObject, DeleteObject
    - S3 Vectors: PutVectors, DeleteVectors
    - Bedrock: InvokeModel
    - API Gateway: ManageConnections (WebSocket)

- **Insight Extraction Lambda**:
  - Runtime: Python 3.12
  - Architecture: ARM64 (Graviton2 for cost optimization)
  - Memory: 3008 MB
  - Timeout: 300 seconds (5 minutes)
  - Layers: boto3-layer
  - Environment Variables:
    - `VECTOR_BUCKET_NAME`
    - `VECTOR_INDEX_ARN`
    - `EMBED_MODEL_ID`: `amazon.titan-embed-text-v2:0`
    - `INSIGHT_MODEL_ID`: `anthropic.claude-3-sonnet-20240229-v1:0`
    - `DYNAMODB_TABLE_NAME`
    - `REGION`
  - IAM Permissions:
    - S3 Vectors: QueryVectors
    - Bedrock: InvokeModel
    - DynamoDB: GetItem, PutItem, Query

#### Lambda Layer Stack (`LambdaLayerStack`)
- **pypdf Layer**: PyPDF2 library for PDF text extraction
- **boto3 Layer**: Latest boto3 with S3 Vectors support
- Build Process: CodeBuild project creates layers from requirements.txt

#### API Gateway Stack (`ApiGatewayStack`)
- **REST API**:
  - Endpoints:
    - `POST /documents/presigned-url`: Generate upload URL
    - `GET /documents`: List user's documents
    - `POST /insights/extract`: Extract insights from document
    - `GET /insights/{docId}`: Retrieve cached insights
  - Authorization: Cognito User Pool
  - CORS: Enabled for AppRunner origin
  
- **WebSocket API**:
  - Routes:
    - `$connect`: Establish connection
    - `$disconnect`: Close connection
    - `$default`: Handle messages
    - `progress`: Document processing updates
  - Authorization: Cognito User Pool (via query string token)
  - Integration: Lambda proxy integration

#### DynamoDB Stack (`DynamoDBStack`)
- **Insights Cache Table**:
  - Table Name: `document-insights-cache`
  - Partition Key: `docId` (String)
  - Sort Key: `extractionTimestamp` (Number - Unix timestamp)
  - TTL Attribute: `expiresAt` (24 hours from creation)
  - Attributes:
    - `prompt` (String): User's query
    - `insights` (Map): JSON-formatted extraction results
    - `modelId` (String): Bedrock model used
    - `chunkCount` (Number): Number of chunks retrieved
  - Billing Mode: PAY_PER_REQUEST
  - Point-in-Time Recovery: Enabled

#### AppRunner Stack (`AppRunnerHostingStack`)
- **ECR Repository**: Stores Docker image for React UI
- **AppRunner Service**:
  - Source: ECR image
  - Instance Configuration: 2 vCPU, 4 GB RAM
  - Auto Scaling: 1-10 instances
  - Health Check: HTTP GET /
  - Environment Variables:
    - `REACT_APP_API_ENDPOINT`
    - `REACT_APP_WSS_ENDPOINT`
    - `REACT_APP_USER_POOL_ID`
    - `REACT_APP_USER_POOL_CLIENT_ID`

#### Cognito Stack (`CognitoAuthStack`)
- **User Pool**:
  - Sign-in: Email
  - Password Policy: 8+ chars, uppercase, lowercase, number, symbol
  - MFA: Optional
- **User Pool Client**:
  - Auth Flows: USER_PASSWORD_AUTH, USER_SRP_AUTH
  - Token Validity: 24 hours

### 2. Lambda Function Components

#### Document Processing Lambda (`document_processor.py`)

**Core Modules**:
- `pdf_extractor.py`: PyPDF2-based text extraction
- `image_detector.py`: Identifies images in PDF pages
- `ocr_processor.py`: Bedrock-based OCR for images
- `text_chunker.py`: Recursive character splitter
- `embedding_generator.py`: Titan V2 embedding creation
- `vector_store.py`: S3 Vectors client wrapper
- `websocket_notifier.py`: Progress update sender

**Processing Algorithm**:
```python
def process_document(s3_event):
    bucket = s3_event['bucket']
    key = s3_event['key']
    doc_id = generate_doc_id(key)
    
    # Download PDF from S3
    pdf_bytes = s3_client.get_object(Bucket=bucket, Key=key)['Body'].read()
    
    # Initialize tracking
    page_texts = []
    total_pages = get_page_count(pdf_bytes)
    
    # Send initial progress
    send_websocket_message(connection_id, {
        'status': 'processing_started',
        'docId': doc_id,
        'totalPages': total_pages
    })
    
    # Process each page
    for page_num in range(total_pages):
        # Extract text
        text = extract_text_from_page(pdf_bytes, page_num)
        
        # Check for images
        if has_images(pdf_bytes, page_num):
            # Extract image and perform OCR
            image_bytes = extract_image(pdf_bytes, page_num)
            ocr_text = perform_ocr(image_bytes)
            text += "\n" + ocr_text
        
        page_texts.append({
            'page': page_num + 1,
            'text': text
        })
        
        # Chunk and embed every 10 pages
        if (page_num + 1) % 10 == 0:
            process_batch(page_texts, doc_id)
            send_websocket_message(connection_id, {
                'status': 'progress',
                'pagesProcessed': page_num + 1,
                'totalPages': total_pages
            })
    
    # Process remaining pages
    if len(page_texts) > 0:
        process_batch(page_texts, doc_id)
    
    # Send completion
    send_websocket_message(connection_id, {
        'status': 'processing_complete',
        'docId': doc_id
    })

def process_batch(page_texts, doc_id):
    # Combine text from pages
    combined_text = "\n\n".join([p['text'] for p in page_texts])
    
    # Split into chunks
    chunks = recursive_character_splitter(
        text=combined_text,
        chunk_size=8192,
        chunk_overlap=819  # 10% of 8192
    )
    
    # Generate embeddings and store
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)
        
        # Store in S3 Vectors
        put_vector(
            vector_index_arn=VECTOR_INDEX_ARN,
            key=f"{doc_id}#chunk{i}",
            vector=embedding,
            filterable_metadata={
                'docId': doc_id,
                'pageRange': f"{page_texts[0]['page']}-{page_texts[-1]['page']}",
                'uploadTimestamp': int(time.time())
            },
            non_filterable_metadata={
                'textChunk': chunk
            }
        )
    
    # Clear processed pages
    page_texts.clear()
```

#### Insight Extraction Lambda (`insight_extractor.py`)

**Core Modules**:
- `cache_manager.py`: DynamoDB cache operations
- `vector_query.py`: S3 Vectors query with metadata filtering
- `insight_generator.py`: Bedrock-based insight extraction
- `response_formatter.py`: JSON schema validation

**Extraction Algorithm**:
```python
def extract_insights(event):
    body = json.loads(event['body'])
    doc_id = body['docId']
    prompt = body['prompt']
    
    # Check cache first
    cached_insights = check_cache(doc_id, prompt)
    if cached_insights:
        return {
            'statusCode': 200,
            'body': json.dumps({
                'insights': cached_insights['insights'],
                'source': 'cache',
                'timestamp': cached_insights['extractionTimestamp']
            })
        }
    
    # Generate query embedding
    query_embedding = generate_embedding(prompt)
    
    # Query S3 Vectors with metadata filter
    results = query_vectors(
        vector_index_arn=VECTOR_INDEX_ARN,
        query_vector=query_embedding,
        top_k=5,
        metadata_filter={
            'docId': {'$eq': doc_id}
        },
        return_metadata=['textChunk']
    )
    
    # Extract text chunks from results
    context_chunks = [r['metadata']['textChunk'] for r in results]
    
    # Generate insights using Bedrock
    insights = generate_insights_with_bedrock(
        prompt=prompt,
        context=context_chunks,
        model_id=INSIGHT_MODEL_ID
    )
    
    # Store in cache
    store_in_cache(
        doc_id=doc_id,
        prompt=prompt,
        insights=insights,
        ttl_hours=24
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'insights': insights,
            'source': 'generated',
            'chunkCount': len(context_chunks)
        })
    }

def check_cache(doc_id, prompt):
    response = dynamodb.query(
        TableName=DYNAMODB_TABLE_NAME,
        KeyConditionExpression='docId = :docId',
        FilterExpression='prompt = :prompt AND expiresAt > :now',
        ExpressionAttributeValues={
            ':docId': doc_id,
            ':prompt': prompt,
            ':now': int(time.time())
        },
        ScanIndexForward=False,  # Most recent first
        Limit=1
    )
    
    if response['Items']:
        return response['Items'][0]
    return None

def store_in_cache(doc_id, prompt, insights, ttl_hours):
    timestamp = int(time.time())
    expires_at = timestamp + (ttl_hours * 3600)
    
    dynamodb.put_item(
        TableName=DYNAMODB_TABLE_NAME,
        Item={
            'docId': doc_id,
            'extractionTimestamp': timestamp,
            'prompt': prompt,
            'insights': insights,
            'modelId': INSIGHT_MODEL_ID,
            'expiresAt': expires_at
        }
    )
```

### 3. Frontend Components

#### React Application Structure
```
src/
├── components/
│   ├── DocumentUpload/
│   │   ├── UploadButton.tsx
│   │   ├── UploadProgress.tsx
│   │   └── DocumentList.tsx
│   ├── InsightExtraction/
│   │   ├── DocumentSelector.tsx
│   │   ├── PromptInput.tsx
│   │   └── InsightDisplay.tsx
│   └── Common/
│       ├── Header.tsx
│       └── Layout.tsx
├── services/
│   ├── api.ts
│   ├── websocket.ts
│   └── auth.ts
├── hooks/
│   ├── useDocuments.ts
│   ├── useWebSocket.ts
│   └── useInsights.ts
└── types/
    ├── document.ts
    └── insight.ts
```

#### Key UI Components

**DocumentUpload Component**:
- Cloudscape FileUpload component
- Requests presigned POST URL from API
- Uploads directly to S3
- Establishes WebSocket connection for progress
- Displays real-time progress bar

**DocumentSelector Component**:
- Cloudscape Select component
- Fetches user's documents from API
- Displays document name, upload date, page count
- Filters by processing status

**PromptInput Component**:
- Cloudscape Textarea component
- Character limit: 1000
- Submit button with loading state
- Example prompts dropdown

**InsightDisplay Component**:
- Cloudscape Container component
- JSON tree view for structured insights
- Copy to clipboard functionality
- Export as JSON/CSV options

## Data Models

### S3 Vector Metadata Schema

**Filterable Metadata**:
```json
{
  "docId": "string (UUID)",
  "pageRange": "string (e.g., '1-10')",
  "uploadTimestamp": "number (Unix timestamp)"
}
```

**Non-Filterable Metadata**:
```json
{
  "textChunk": "string (up to 8192 tokens)"
}
```

### DynamoDB Item Schema

```json
{
  "docId": "string (UUID) - Partition Key",
  "extractionTimestamp": "number (Unix timestamp) - Sort Key",
  "prompt": "string",
  "insights": {
    "type": "object",
    "properties": {
      "summary": "string",
      "keyPoints": ["string"],
      "entities": [
        {
          "name": "string",
          "type": "string",
          "context": "string"
        }
      ],
      "metadata": {
        "confidence": "number",
        "processingTime": "number"
      }
    }
  },
  "modelId": "string",
  "chunkCount": "number",
  "expiresAt": "number (Unix timestamp) - TTL Attribute"
}
```

### API Request/Response Models

**Presigned URL Request**:
```json
{
  "fileName": "string",
  "fileSize": "number",
  "contentType": "string"
}
```

**Presigned URL Response**:
```json
{
  "url": "string",
  "fields": {
    "key": "string",
    "AWSAccessKeyId": "string",
    "policy": "string",
    "signature": "string"
  },
  "docId": "string",
  "expiresIn": "number"
}
```

**Insight Extraction Request**:
```json
{
  "docId": "string",
  "prompt": "string"
}
```

**Insight Extraction Response**:
```json
{
  "insights": {
    "summary": "string",
    "keyPoints": ["string"],
    "entities": [...]
  },
  "source": "cache | generated",
  "chunkCount": "number",
  "timestamp": "number"
}
```

## Error Handling

### Lambda Error Handling Strategy

1. **Retryable Errors**: S3 event notifications automatically retry with exponential backoff
2. **Non-Retryable Errors**: Send error message via WebSocket and log to CloudWatch
3. **Partial Failures**: Continue processing remaining pages, mark document as partially processed
4. **Timeout Handling**: Implement checkpointing for long-running documents

### Error Categories

**Document Processing Errors**:
- Invalid PDF format → Return 400 error via WebSocket
- File too large → Return 413 error via WebSocket
- OCR failure → Log warning, continue with text-only extraction
- Embedding generation failure → Retry 3 times, then fail batch

**Insight Extraction Errors**:
- Document not found → Return 404 error
- No vectors found for document → Return 404 with message
- Bedrock throttling → Implement exponential backoff
- Invalid JSON response → Retry with modified prompt

### WebSocket Error Messages

```json
{
  "status": "error",
  "errorCode": "PROCESSING_FAILED",
  "message": "Failed to process page 15: Invalid image format",
  "docId": "uuid",
  "recoverable": false
}
```

## Testing Strategy

### Unit Tests

**Lambda Functions**:
- Test PDF text extraction with sample PDFs
- Test chunking algorithm with various text lengths
- Test embedding generation with mock Bedrock responses
- Test cache hit/miss scenarios
- Test metadata filtering queries

**Frontend Components**:
- Test file upload with mock presigned URLs
- Test WebSocket connection and message handling
- Test insight display with various JSON structures
- Test error state rendering

### Integration Tests

**End-to-End Flows**:
- Upload PDF → Process → Extract insights → Verify cache
- Upload PDF with images → Verify OCR execution
- Query cached insights → Verify DynamoDB retrieval
- Delete document → Verify vector cleanup

**API Tests**:
- Test all REST endpoints with valid/invalid inputs
- Test WebSocket connection lifecycle
- Test Cognito authentication flow

### Performance Tests

**Load Testing**:
- Concurrent document uploads (10, 50, 100 users)
- Large PDF processing (100+ pages)
- High-frequency insight queries
- WebSocket connection limits

**Latency Benchmarks**:
- Presigned URL generation: < 200ms
- Insight extraction (cache hit): < 500ms
- Insight extraction (cache miss): < 30s
- WebSocket message delivery: < 100ms

### Security Tests

**Authentication/Authorization**:
- Test unauthenticated access rejection
- Test cross-user document access prevention
- Test token expiration handling

**Input Validation**:
- Test SQL injection in prompts
- Test XSS in document names
- Test file upload size limits
- Test malformed JSON handling

## Deployment Strategy

### CDK Deployment Steps

1. **Bootstrap CDK** (first time only):
   ```bash
   cdk bootstrap aws://ACCOUNT-ID/REGION
   ```

2. **Build Lambda Layers**:
   ```bash
   # Trigger CodeBuild to create pypdf and boto3 layers
   aws codebuild start-build --project-name lambda-layer-builder
   ```

3. **Deploy Infrastructure**:
   ```bash
   cdk deploy --all --require-approval never
   ```

4. **Build and Push UI**:
   ```bash
   # Build React app
   cd artifacts/ui
   npm run build
   
   # Build Docker image
   docker build -t document-insight-ui .
   
   # Push to ECR
   aws ecr get-login-password | docker login --username AWS --password-stdin ECR_URI
   docker tag document-insight-ui:latest ECR_URI:latest
   docker push ECR_URI:latest
   ```

5. **Verify Deployment**:
   ```bash
   # Get AppRunner URL
   aws apprunner list-services
   
   # Test API endpoints
   curl -X GET API_ENDPOINT/documents
   ```

### Environment Configuration

**Development Environment** (`cdk.context.json`):
```json
{
  "dev": {
    "s3_documents_bucket": "doc-insight-docs-dev",
    "s3_vector_bucket": "doc-insight-vectors-dev",
    "dynamodb_table": "doc-insight-cache-dev",
    "embed_model_id": "amazon.titan-embed-text-v2:0",
    "insight_model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
    "lambda_memory": 3008,
    "lambda_timeout": 600,
    "apprunner_cpu": "2048",
    "apprunner_memory": "4096"
  }
}
```

**Production Environment**:
- Increase Lambda memory to 10240 MB for faster processing
- Enable CloudWatch detailed monitoring
- Configure CloudWatch alarms for errors and latency
- Enable X-Ray tracing for distributed tracing

### Monitoring and Observability

**CloudWatch Metrics**:
- Lambda invocations, errors, duration
- API Gateway request count, latency, 4xx/5xx errors
- DynamoDB read/write capacity, throttles
- AppRunner request count, response time

**CloudWatch Logs**:
- Lambda function logs with structured logging
- API Gateway access logs
- AppRunner application logs

**CloudWatch Alarms**:
- Lambda error rate > 5%
- API Gateway 5xx error rate > 1%
- DynamoDB throttling events
- S3 Vectors query latency > 5s

**X-Ray Tracing**:
- Enable on all Lambda functions
- Trace document processing pipeline
- Identify bottlenecks in insight extraction

## Security Considerations

### Data Protection

**Encryption at Rest**:
- S3 buckets: SSE-S3 encryption
- DynamoDB: AWS-managed encryption
- S3 Vectors: Encrypted by default

**Encryption in Transit**:
- All API calls over HTTPS/WSS
- TLS 1.2+ enforced

### Access Control

**IAM Policies**:
- Least privilege principle for Lambda execution roles
- Separate roles for document processing and insight extraction
- S3 bucket policies restrict access to Lambda functions only

**Cognito Authentication**:
- Email verification required
- Strong password policy enforced
- JWT tokens with 24-hour expiration

**API Gateway Authorization**:
- Cognito authorizer on all endpoints
- Rate limiting: 1000 requests/second per user
- Request validation for all inputs

### Data Privacy

**User Isolation**:
- Document metadata includes user ID
- S3 object keys prefixed with user ID
- DynamoDB queries filtered by user ID

**Data Retention**:
- DynamoDB TTL automatically deletes insights after 24 hours
- S3 lifecycle policies for document retention (configurable)
- CloudWatch logs retention: 30 days

### Compliance

**Audit Logging**:
- CloudTrail enabled for all API calls
- S3 access logging enabled
- Lambda execution logs retained

**Data Residency**:
- All data stored in specified AWS region
- No cross-region replication by default

## Cost Optimization

### Estimated Monthly Costs (1000 documents/month, 10 pages avg)

**Compute**:
- Lambda (Document Processing): ~$50
- Lambda (Insight Extraction): ~$30
- AppRunner: ~$25

**Storage**:
- S3 (Documents): ~$5
- S3 Vectors: ~$20
- DynamoDB: ~$10

**AI Services**:
- Bedrock (Titan V2 Embeddings): ~$40
- Bedrock (Claude Insights): ~$60
- Bedrock (OCR): ~$30

**Networking**:
- API Gateway: ~$10
- Data Transfer: ~$5

**Total**: ~$285/month

### Cost Optimization Strategies

1. **Lambda**: Use ARM64 architecture where possible (10% cost reduction)
2. **DynamoDB**: Use on-demand billing for unpredictable workloads
3. **S3 Vectors**: Leverage metadata filtering to reduce query costs
4. **Bedrock**: Batch embedding requests when possible
5. **AppRunner**: Configure auto-scaling to scale to zero during low usage
6. **CloudWatch**: Adjust log retention and metric resolution

## Future Enhancements

1. **Multi-Format Support**: Add support for DOCX, PPTX, images
2. **Advanced OCR**: Integrate Textract for table and form extraction
3. **Streaming Insights**: Stream Bedrock responses for faster perceived performance
4. **Collaborative Features**: Share documents and insights between users
5. **Custom Models**: Fine-tune embedding models for domain-specific documents
6. **Analytics Dashboard**: Visualize document processing metrics and insight trends
7. **Batch Processing**: Support bulk document uploads
8. **Version Control**: Track document versions and insight history
