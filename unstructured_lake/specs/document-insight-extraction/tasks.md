# Implementation Plan

- [x] 1. Set up CDK project structure and core infrastructure
  - Create main CDK app entry point with environment configuration
  - Define base stack class with common tags and naming conventions
  - Configure cdk.json with context parameters for dev/prod environments
  - Set up requirements.txt with CDK dependencies
  - _Requirements: 10.1, 10.2_

- [x] 2. Implement Cognito authentication stack
  - [x] 2.1 Create CognitoAuthStack with user pool configuration
    - Define user pool with email sign-in and password policy
    - Create user pool client with auth flow configuration
    - Export user pool ID and client ID as stack outputs
    - _Requirements: 11.1_
  
  - [x] 2.2 Configure Cognito authorizer for API Gateway
    - Create CognitoUserPoolsAuthorizer construct
    - Set token validity to 24 hours
    - _Requirements: 11.1_

- [x] 3. Implement S3 bucket infrastructure
  - [x] 3.1 Create S3BucketStack for document storage
    - Create S3 bucket with CORS configuration for presigned POST
    - Configure bucket naming with account ID and region
    - Set removal policy to DESTROY for dev environment
    - _Requirements: 1.2, 1.3_
  
  - [x] 3.2 Create S3 Vector Bucket for embeddings
    - Create vector bucket using CfnBucket with type VECTORSEARCH
    - Configure vector index with 1024 dimensions and cosine similarity
    - Define filterable metadata keys: docId, pageRange, uploadTimestamp
    - Define non-filterable metadata key: textChunk
    - Export vector index ARN as stack output
    - _Requirements: 5.4, 6.1_
  
  - [x] 3.3 Configure S3 event notifications
    - Add Lambda destination for OBJECT_CREATED events
    - Add Lambda destination for OBJECT_REMOVED_DELETE events
    - Grant S3 service principal permission to invoke Lambda
    - _Requirements: 1.3, 12.2_

- [x] 4. Implement Lambda layer build infrastructure
  - [x] 4.1 Create LambdaLayerStack with CodeBuild project
    - Define buildspec.yml for layer creation
    - Create CodeBuild project with Python 3.12 environment
    - Configure environment variables for layer names
    - _Requirements: 10.4_
  
  - [x] 4.2 Create buildspec for pypdf layer
    - Install PyPDF2 and dependencies to /opt/python
    - Zip layer contents and publish to Lambda
    - Create both x86_64 and ARM64 versions
    - _Requirements: 3.1, 10.4_
  
  - [x] 4.3 Create buildspec for boto3 layer with S3 Vectors support
    - Install latest boto3 with S3 Vectors API support
    - Include botocore and dependencies
    - Publish layer for both architectures
    - _Requirements: 5.1, 6.2_

- [x] 5. Implement DynamoDB cache table
  - [x] 5.1 Create DynamoDBStack with insights cache table
    - Define table with docId partition key and extractionTimestamp sort key
    - Configure TTL attribute expiresAt
    - Set billing mode to PAY_PER_REQUEST
    - Enable point-in-time recovery
    - _Requirements: 8.1, 8.2_
  
  - [x] 5.2 Configure auto-scaling policies
    - Set read capacity auto-scaling: 5-50 units at 75% utilization
    - Set write capacity auto-scaling: 5-50 units at 75% utilization
    - _Requirements: 8.1_

- [x] 6. Implement API Gateway REST API stack
  - [x] 6.1 Create ApiGatewayStack with REST API
    - Create RestApi with regional endpoint
    - Configure deployment stage with throttling (1000 req/sec)
    - Add CORS configuration for AppRunner origin
    - _Requirements: 10.2_
  
  - [x] 6.2 Define presigned URL endpoint
    - Create POST /documents/presigned-url resource
    - Add Cognito authorizer
    - Integrate with Lambda function
    - Add CORS OPTIONS method
    - _Requirements: 1.1_
  
  - [x] 6.3 Define document list endpoint
    - Create GET /documents resource
    - Add Cognito authorizer
    - Integrate with Lambda function
    - _Requirements: 11.3_
  
  - [x] 6.4 Define insight extraction endpoint
    - Create POST /insights/extract resource
    - Add Cognito authorizer
    - Integrate with Insight Extraction Lambda
    - Configure 300 second timeout
    - _Requirements: 7.1, 7.5_
  
  - [x] 6.5 Define insight retrieval endpoint
    - Create GET /insights/{docId} resource
    - Add Cognito authorizer
    - Integrate with Insight Extraction Lambda
    - _Requirements: 9.1, 9.2_

- [x] 7. Implement API Gateway WebSocket API
  - [x] 7.1 Create WebSocket API with routes
    - Create CfnApi with WEBSOCKET protocol
    - Define $connect, $disconnect, $default, and progress routes
    - Configure route selection expression
    - _Requirements: 2.1_
  
  - [x] 7.2 Create WebSocket integrations
    - Create CfnIntegration for Lambda proxy
    - Configure IAM role for API Gateway to invoke Lambda
    - Set up deployment and stage
    - Export WebSocket URL as stack output
    - _Requirements: 2.1, 10.5_

- [x] 8. Implement Document Processing Lambda function
  - [x] 8.1 Create LambdaFunctionStack for document processor
    - Define Lambda function with Python 3.12 runtime
    - Configure x86_64 architecture for pypdf compatibility
    - Set memory to 3008 MB and timeout to 600 seconds
    - Attach pypdf and boto3 layers
    - Configure environment variables: VECTOR_BUCKET_NAME, VECTOR_INDEX_ARN, EMBED_MODEL_ID, WSS_URL, REGION
    - _Requirements: 10.2_
  
  - [x] 8.2 Grant IAM permissions to document processor
    - Grant S3 GetObject and DeleteObject permissions
    - Grant S3 Vectors PutVectors and DeleteVectors permissions
    - Grant Bedrock InvokeModel permission
    - Grant API Gateway ManageConnections permission for WebSocket
    - _Requirements: 3.1, 3.2, 5.1_
  
  - [x] 8.3 Implement PDF text extraction module
    - Create pdf_extractor.py using PyPDF2
    - Extract text from each page
    - Handle pages with no text content
    - Return list of page texts with page numbers
    - _Requirements: 3.1, 3.3_
  
  - [x] 8.4 Implement image detection and OCR module
    - Create image_detector.py to identify images in PDF pages
    - Create ocr_processor.py to call Bedrock for OCR
    - Use amazon.titan-image-generator-v1 or appropriate OCR model
    - Combine OCR text with extracted text
    - _Requirements: 3.2, 3.3_
  
  - [x] 8.5 Implement text chunking module
    - Create text_chunker.py with recursive character splitter
    - Configure chunk size to 8192 tokens
    - Configure overlap to 819 tokens (10%)
    - Preserve page range metadata for each chunk
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [x] 8.6 Implement embedding generation module
    - Create embedding_generator.py to call Titan V2
    - Use model ID: amazon.titan-embed-text-v2:0
    - Handle 8192 token input limit
    - Return 1024-dimensional vectors
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 8.7 Implement S3 Vectors storage module
    - Create vector_store.py wrapper for S3 Vectors API
    - Implement put_vector with filterable and non-filterable metadata
    - Store docId, pageRange, uploadTimestamp as filterable metadata
    - Store textChunk as non-filterable metadata
    - _Requirements: 5.4, 5.5, 6.1_
  
  - [x] 8.8 Implement WebSocket notification module
    - Create websocket_notifier.py for progress updates
    - Send processing_started message with docId and totalPages
    - Send progress messages every 10 pages
    - Send processing_complete message with docId
    - Send error messages on failures
    - _Requirements: 2.2, 2.3, 2.4, 2.5_
  
  - [x] 8.9 Implement main document processing handler
    - Create document_processor.py with handler function
    - Parse S3 event notification
    - Download PDF from S3
    - Process pages in batches of 10
    - Call chunking and embedding for each batch
    - Handle errors and send WebSocket notifications
    - _Requirements: 1.3, 1.4, 3.1, 3.2, 4.5_
  
  - [x] 8.10 Implement document deletion handler
    - Detect S3 OBJECT_REMOVED_DELETE events
    - Query S3 Vectors for all vectors with matching docId
    - Delete all associated vectors
    - Log cleanup operations
    - _Requirements: 12.2, 12.3, 12.4, 12.5_

- [x] 9. Implement Insight Extraction Lambda function
  - [x] 9.1 Create Lambda function for insight extraction
    - Define Lambda function with Python 3.12 runtime
    - Configure ARM64 architecture for cost optimization
    - Set memory to 3008 MB and timeout to 300 seconds
    - Attach boto3 layer
    - Configure environment variables: VECTOR_BUCKET_NAME, VECTOR_INDEX_ARN, EMBED_MODEL_ID, INSIGHT_MODEL_ID, DYNAMODB_TABLE_NAME, REGION
    - _Requirements: 10.2_
  
  - [x] 9.2 Grant IAM permissions to insight extractor
    - Grant S3 Vectors QueryVectors permission
    - Grant Bedrock InvokeModel permission
    - Grant DynamoDB GetItem, PutItem, Query permissions
    - _Requirements: 7.2, 8.3_
  
  - [x] 9.3 Implement DynamoDB cache manager module
    - Create cache_manager.py with check_cache function
    - Query DynamoDB by docId and filter by prompt and TTL
    - Implement store_in_cache function with 24-hour TTL
    - Return most recent cached result
    - _Requirements: 8.3, 8.4, 8.5_
  
  - [x] 9.4 Implement vector query module
    - Create vector_query.py for S3 Vectors queries
    - Generate query embedding using Titan V2
    - Query vectors with metadata filter: docId equals specified value
    - Set top_k to 5 for retrieval
    - Return text chunks from non-filterable metadata
    - _Requirements: 6.1, 6.2, 6.5, 7.2_
  
  - [x] 9.5 Implement insight generation module
    - Create insight_generator.py to call Bedrock
    - Use Claude 3 Sonnet model for insight extraction
    - Format prompt with user query and retrieved context chunks
    - Parse JSON response from model
    - Validate JSON schema
    - _Requirements: 7.3, 7.4_
  
  - [x] 9.6 Implement insight extraction handler
    - Create insight_extractor.py with handler function
    - Parse API Gateway event for docId and prompt
    - Check cache first, return if hit
    - Query S3 Vectors with metadata filtering
    - Generate insights using Bedrock
    - Store in cache with TTL
    - Return JSON response
    - _Requirements: 7.1, 7.5, 8.3, 8.4, 8.5_
  
  - [x] 9.7 Implement insight retrieval handler
    - Add GET endpoint handler to insight_extractor.py
    - Parse docId from path parameters
    - Query DynamoDB for all non-expired insights
    - Sort by extractionTimestamp descending
    - Return list of insights with timestamps
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 10. Implement React frontend application
  - [x] 10.1 Set up React project with Cloudscape Design System
    - Initialize React app with TypeScript
    - Install @cloudscape-design/components
    - Configure Vite build system
    - Set up routing with react-router-dom
    - _Requirements: 11.1, 11.2_
  
  - [x] 10.2 Implement authentication service
    - Create auth.ts with Cognito integration
    - Implement sign-up, sign-in, sign-out functions
    - Store JWT tokens in localStorage
    - Add token refresh logic
    - _Requirements: 11.1_
  
  - [x] 10.3 Implement API service module
    - Create api.ts with axios client
    - Add authentication headers to all requests
    - Implement getPresignedUrl function
    - Implement listDocuments function
    - Implement extractInsights function
    - Implement getInsights function
    - _Requirements: 11.3_
  
  - [x] 10.4 Implement WebSocket service module
    - Create websocket.ts for WebSocket connection management
    - Connect to WebSocket API with auth token
    - Handle connection lifecycle events
    - Parse and dispatch progress messages
    - Implement reconnection logic
    - _Requirements: 2.1, 11.4_
  
  - [x] 10.5 Implement DocumentUpload component
    - Create UploadButton.tsx with Cloudscape FileUpload
    - Request presigned POST URL from API
    - Upload file directly to S3 using presigned URL
    - Establish WebSocket connection on upload start
    - Display UploadProgress component
    - _Requirements: 1.1, 11.3, 11.4_
  
  - [x] 10.6 Implement UploadProgress component
    - Create UploadProgress.tsx with Cloudscape ProgressBar
    - Subscribe to WebSocket progress messages
    - Update progress bar based on pagesProcessed/totalPages
    - Display processing status messages
    - Show completion or error states
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 11.4_
  
  - [x] 10.7 Implement DocumentList component
    - Create DocumentList.tsx with Cloudscape Table
    - Fetch documents from API on mount
    - Display document name, upload date, page count, status
    - Add refresh button
    - Handle empty state
    - _Requirements: 11.3_
  
  - [x] 10.8 Implement DocumentSelector component
    - Create DocumentSelector.tsx with Cloudscape Select
    - Populate options from DocumentList
    - Filter by processing status (completed only)
    - Emit selected document to parent
    - _Requirements: 11.3_
  
  - [x] 10.9 Implement PromptInput component
    - Create PromptInput.tsx with Cloudscape Textarea
    - Add character limit of 1000
    - Create submit button with loading state
    - Add example prompts dropdown
    - Validate input before submission
    - _Requirements: 11.3_
  
  - [x] 10.10 Implement InsightDisplay component
    - Create InsightDisplay.tsx with Cloudscape Container
    - Render JSON insights in tree view format
    - Add copy to clipboard button
    - Add export as JSON button
    - Add export as CSV button
    - Display source (cache vs generated) and timestamp
    - _Requirements: 11.5_
  
  - [x] 10.11 Implement main application layout
    - Create Layout.tsx with Cloudscape AppLayout
    - Add Header component with navigation
    - Create home page with DocumentUpload and DocumentList
    - Create insights page with DocumentSelector, PromptInput, and InsightDisplay
    - Add routing between pages
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 11. Implement AppRunner hosting infrastructure
  - [x] 11.1 Create Dockerfile for React application
    - Use multi-stage build with Node.js and Nginx
    - Copy build artifacts to Nginx
    - Configure Nginx with custom nginx.conf
    - Expose port 80
    - _Requirements: 11.2_
  
  - [x] 11.2 Create AppRunnerHostingStack
    - Create ECR repository for UI Docker image
    - Define AppRunner service with ECR source
    - Configure instance: 2 vCPU, 4 GB RAM
    - Set auto-scaling: 1-10 instances
    - Configure environment variables: API_ENDPOINT, WSS_ENDPOINT, USER_POOL_ID, USER_POOL_CLIENT_ID
    - Export AppRunner service URL
    - _Requirements: 11.1, 11.2, 10.5_
  
  - [x] 11.3 Create CodeBuild project for UI build
    - Define buildspec_dockerize_ui.yml
    - Build React app with npm run build
    - Build Docker image
    - Push to ECR with timestamp tag
    - Trigger AppRunner deployment
    - _Requirements: 11.2_

- [x] 12. Implement deployment and configuration
  - [x] 12.1 Create main CDK app entry point
    - Create app.py to instantiate all stacks
    - Configure stack dependencies
    - Pass outputs between stacks
    - Add environment tags
    - _Requirements: 10.1, 10.2_
  
  - [x] 12.2 Create cdk.json with context parameters
    - Define dev environment configuration
    - Define prod environment configuration
    - Set bucket names, table names, model IDs
    - Configure Lambda memory and timeout values
    - _Requirements: 10.1_
  
  - [x] 12.3 Create deployment script
    - Create deploy.sh to orchestrate deployment
    - Build Lambda layers via CodeBuild
    - Deploy CDK stacks in correct order
    - Build and push UI Docker image
    - Output all endpoint URLs
    - _Requirements: 10.5_
  
  - [x] 12.4 Create README with setup instructions
    - Document prerequisites (AWS CLI, CDK, Node.js, Python)
    - Provide step-by-step deployment guide
    - Document environment variables
    - Include troubleshooting section
    - _Requirements: 10.1_

- [ ]* 13. Implement testing suite
  - [ ]* 13.1 Write unit tests for Lambda functions
    - Test PDF text extraction with sample PDFs
    - Test chunking algorithm with various text lengths
    - Test embedding generation with mock responses
    - Test cache hit/miss scenarios
    - Test metadata filtering queries
    - _Requirements: 3.1, 4.2, 5.1, 8.3_
  
  - [ ]* 13.2 Write integration tests for API endpoints
    - Test presigned URL generation
    - Test document upload flow
    - Test insight extraction with real Bedrock calls
    - Test insight retrieval from cache
    - Test WebSocket connection and messages
    - _Requirements: 1.1, 7.1, 9.1_
  
  - [ ]* 13.3 Write frontend component tests
    - Test file upload with mock API
    - Test WebSocket message handling
    - Test insight display rendering
    - Test error state handling
    - _Requirements: 11.3, 11.4, 11.5_
  
  - [ ]* 13.4 Create end-to-end test suite
    - Test complete upload → process → extract flow
    - Test document with images and OCR
    - Test cache expiration and refresh
    - Test document deletion and cleanup
    - _Requirements: 1.3, 3.2, 8.5, 12.2_

- [ ]* 14. Implement monitoring and observability
  - [ ]* 14.1 Configure CloudWatch alarms
    - Create alarm for Lambda error rate > 5%
    - Create alarm for API Gateway 5xx errors > 1%
    - Create alarm for DynamoDB throttling
    - Create alarm for S3 Vectors query latency > 5s
    - _Requirements: 10.2_
  
  - [ ]* 14.2 Enable X-Ray tracing
    - Enable X-Ray on all Lambda functions
    - Add X-Ray SDK to Lambda code
    - Create service map for document processing pipeline
    - _Requirements: 10.2_
  
  - [ ]* 14.3 Configure structured logging
    - Add structured logging to all Lambda functions
    - Include correlation IDs for request tracing
    - Log key metrics: processing time, chunk count, cache hits
    - _Requirements: 10.2_
