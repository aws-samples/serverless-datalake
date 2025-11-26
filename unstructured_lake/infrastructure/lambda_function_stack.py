"""
Lambda Function Stack for Document Insight Extraction System

This module defines Lambda functions for document processing and insight extraction,
including IAM permissions, environment configuration, and layer attachments.
"""
from aws_cdk import (
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    aws_logs as logs,
    aws_apigatewayv2 as apigatewayv2,
    aws_ssm as ssm,
    CfnOutput,
)
from constructs import Construct
from infrastructure.base_stack import BaseDocumentInsightStack
from typing import Optional


class LambdaFunctionStack(BaseDocumentInsightStack):
    """
    Stack for Lambda function resources.
    
    Creates:
    - Document Processing Lambda function
    - Insight Extraction Lambda function (future)
    - IAM roles and permissions
    - CloudWatch log groups
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        config: dict,
        **kwargs
    ) -> None:
        """
        Initialize the Lambda Function stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        # Store references to be set later
        self.documents_bucket_name: Optional[str] = None
        self.vector_bucket_name: Optional[str] = None
        self.vector_index_arn: Optional[str] = None
        self.websocket_url: Optional[str] = None
        
        # Lambda functions (created later after dependencies are set)
        self.document_processor_lambda: Optional[lambda_.Function] = None
        self.insight_extractor_lambda: Optional[lambda_.Function] = None
        self.image_insights_lambda: Optional[lambda_.Function] = None
        
    def create_document_processor_lambda(
        self,
        documents_bucket_name: str,
        vector_bucket_name: str,
        vector_index_arn: str,
        websocket_url: str,
        processing_status_table_name: str,
        pypdf_layer_arn: str,
        boto3_layer_arn: str,
        langchain_layer_arn: str
    ) -> lambda_.Function:
        """
        Create the Document Processing Lambda function.
        
        Args:
            documents_bucket_name: S3 bucket name for document storage
            vector_bucket_name: S3 Vector bucket name
            vector_index_arn: S3 Vector index ARN
            websocket_url: WebSocket API URL for progress updates
            processing_status_table_name: DynamoDB table name for processing status tracking
            pypdf_layer_arn: ARN of pypdf Lambda layer
            boto3_layer_arn: ARN of boto3 Lambda layer
            langchain_layer_arn: ARN of LangChain Lambda layer
            
        Returns:
            Lambda Function construct
        """
        # Store references
        self.documents_bucket_name = documents_bucket_name
        self.vector_bucket_name = vector_bucket_name
        self.vector_index_arn = vector_index_arn
        self.websocket_url = websocket_url
        
        # Create CloudWatch log group
        log_group = logs.LogGroup(
            self,
            "DocumentProcessorLogGroup",
            log_group_name=f"/aws/lambda/{self.get_resource_name('document-processor')}",
            removal_policy=self.removal_policy,
            retention=logs.RetentionDays.ONE_MONTH
        )
        
        # Create Lambda execution role
        execution_role = self._create_document_processor_role()
        
        # Create Lambda layers from ARNs
        pypdf_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PypdfLayer",
            layer_version_arn=pypdf_layer_arn
        )
        
        boto3_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "Boto3Layer",
            layer_version_arn=boto3_layer_arn
        )
        
        langchain_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "LangChainLayer",
            layer_version_arn=langchain_layer_arn
        )
        
        # Create Lambda function
        self.document_processor_lambda = lambda_.Function(
            self,
            "DocumentProcessorLambda",
            function_name=self.get_resource_name("document-processor"),
            description="Process PDF documents: extract text, generate embeddings, store in S3 Vectors",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # x86_64 architecture for pypdf compatibility
            architecture=lambda_.Architecture.X86_64,
            handler="document_processor.handler",
            code=lambda_.Code.from_asset("lambda/document_processor"),
            # Memory and timeout configuration
            memory_size=self.lambda_memory,
            timeout=Duration.seconds(self.lambda_timeout),
            # Attach layers
            layers=[pypdf_layer, boto3_layer, langchain_layer],
            # IAM role
            role=execution_role,
            # Environment variables
            environment={
                "DOCUMENTS_BUCKET_NAME": documents_bucket_name,
                "VECTOR_BUCKET_NAME": vector_bucket_name,
                "VECTOR_INDEX_ARN": vector_index_arn,
                "EMBED_MODEL_ID": self.embed_model_id,
                "WSS_URL": websocket_url,
                "DYNAMODB_TABLE_NAME": processing_status_table_name,
                "REGION": self.region,
                "LOG_LEVEL": self.config.get("log_level", "INFO"),
                "OCR_MODEL_ID": self.config.get("ocr_model_id", "INFO"),
                "CHUNK_SIZE": str(self.config.get("chunk_size", 2048)),
                "CHUNK_OVERLAP": str(self.config.get("chunk_overlap", 204)),
            },
            # CloudWatch Logs
            log_group=log_group,
            # Reserved concurrent executions (optional)
            reserved_concurrent_executions=self.config.get(
                "document_processor_concurrency",
                None
            ),
        )
        
        # Grant S3 permissions
        self._grant_s3_permissions()
        
        # Grant Bedrock permissions
        self._grant_bedrock_permissions()
        
        # Grant DynamoDB permissions
        self._grant_document_processor_dynamodb_permissions(processing_status_table_name)
        
        # Add outputs
        self._add_document_processor_outputs()
        
        return self.document_processor_lambda

    def _create_document_processor_role(self) -> iam.Role:
        """
        Create IAM role for Document Processing Lambda.
        
        Returns:
            IAM Role with necessary permissions
        """
        role = iam.Role(
            self,
            "DocumentProcessorRole",
            role_name=self.get_resource_name("document-processor-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Document Processing Lambda function",
            managed_policies=[
                # Basic Lambda execution permissions
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )
        
        return role

    def _grant_s3_permissions(self) -> None:
        """Grant S3 permissions to Document Processing Lambda."""
        if not self.document_processor_lambda or not self.documents_bucket_name:
            raise ValueError("Lambda function and documents bucket name must be set first")
        
        # Grant read and delete permissions on documents bucket
        self.document_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::{self.documents_bucket_name}",
                    f"arn:aws:s3:::{self.documents_bucket_name}/*"
                ]
            )
        )
        
        # Grant S3 Vectors permissions (PutVectors, DeleteVectors, QueryVectors)
        self.document_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::{self.vector_bucket_name}",
                    f"arn:aws:s3:::{self.vector_bucket_name}/*"
                ]
            )
        )
        
        # Grant S3 Vectors API permissions
        self.document_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:PutVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:QueryVectors",
                ],
                resources=[
                    self.vector_index_arn
                ]
            )
        )

    def _grant_bedrock_permissions(self) -> None:
        """Grant Bedrock permissions to Document Processing Lambda."""
        if not self.document_processor_lambda:
            raise ValueError("Lambda function must be set first")
        
        # Grant permission to invoke Bedrock models
        self.document_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    # Titan V2 embedding model
                    f"arn:aws:bedrock:*::foundation-model/{self.embed_model_id}",
                    # Allow any Bedrock model for OCR (flexible)
                    f"arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:*:inference-profile/*",
                    f"arn:aws:bedrock:*:*:application-inference-profile/*"
                ]
            )
        )

    def grant_websocket_permissions(self, websocket_api_arn: str) -> None:
        """
        Grant API Gateway ManageConnections permission for WebSocket.
        
        Args:
            websocket_api_arn: ARN pattern for WebSocket API connections
        """
        if not self.document_processor_lambda:
            raise ValueError("Lambda function must be set first")
        
        self.document_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:ManageConnections",
                    "execute-api:Invoke",
                ],
                resources=[
                    websocket_api_arn
                ]
            )
        )

    def create_document_api_lambda(
        self,
        documents_bucket_name: str,
        processing_status_table_name: str,
        boto3_layer_arn: str
    ) -> lambda_.Function:
        """
        Create the Document API Lambda function.
        
        Args:
            documents_bucket_name: S3 bucket name for document storage
            processing_status_table_name: DynamoDB table name for processing status tracking
            boto3_layer_arn: ARN of boto3 Lambda layer
            
        Returns:
            Lambda Function construct
        """
        # Create CloudWatch log group
        log_group = logs.LogGroup(
            self,
            "DocumentApiLogGroup",
            log_group_name=f"/aws/lambda/{self.get_resource_name('document-api')}",
            removal_policy=self.removal_policy,
            retention=logs.RetentionDays.ONE_MONTH
        )
        
        # Create Lambda execution role
        execution_role = self._create_document_api_role()
        
        # Create Lambda layer from ARN
        boto3_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "DocumentApiBoto3Layer",
            layer_version_arn=boto3_layer_arn
        )
        
        # Create Lambda function
        self.document_api_lambda = lambda_.Function(
            self,
            "DocumentApiLambda",
            function_name=self.get_resource_name("document-api"),
            description="Handle HTTP API requests for document management",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # ARM64 architecture for cost optimization
            architecture=lambda_.Architecture.ARM_64,
            handler="document_api.handler",
            code=lambda_.Code.from_asset("lambda/document_api"),
            # Memory and timeout configuration
            memory_size=512,  # Lower memory for API operations
            timeout=Duration.seconds(30),  # Shorter timeout for API operations
            # Attach layer
            layers=[boto3_layer],
            # IAM role
            role=execution_role,
            # Environment variables
            environment={
                "DOCUMENTS_BUCKET_NAME": documents_bucket_name,
                "DYNAMODB_TABLE_NAME": processing_status_table_name,
                "REGION": self.region,
                "LOG_LEVEL": self.config.get("log_level", "INFO"),
            },
            # CloudWatch Logs
            log_group=log_group,
        )
        
        # Grant S3 permissions
        self._grant_document_api_s3_permissions(documents_bucket_name)
        
        # Grant DynamoDB permissions
        self._grant_document_api_dynamodb_permissions(processing_status_table_name)
        
        # Add outputs
        self._add_document_api_outputs()
        
        return self.document_api_lambda

    def _create_document_api_role(self) -> iam.Role:
        """
        Create IAM role for Document API Lambda.
        
        Returns:
            IAM Role with necessary permissions
        """
        role = iam.Role(
            self,
            "DocumentApiRole",
            role_name=self.get_resource_name("document-api-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Document API Lambda function",
            managed_policies=[
                # Basic Lambda execution permissions
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )
        
        return role

    def _grant_document_api_s3_permissions(self, documents_bucket_name: str) -> None:
        """
        Grant S3 permissions to Document API Lambda.
        
        Args:
            documents_bucket_name: S3 bucket name for document storage
        """
        if not self.document_api_lambda:
            raise ValueError("Document API Lambda function must be set first")
        
        # Grant read, write, and delete permissions on documents bucket
        self.document_api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetObjectMetadata",
                    "s3:HeadObject"
                ],
                resources=[
                    f"arn:aws:s3:::{documents_bucket_name}",
                    f"arn:aws:s3:::{documents_bucket_name}/*"
                ]
            )
        )

    def _add_document_api_outputs(self) -> None:
        """Add CloudFormation outputs for Document API Lambda."""
        if not self.document_api_lambda:
            return
        
        self.add_stack_output(
            "DocumentApiLambdaArn",
            value=self.document_api_lambda.function_arn,
            description="ARN of Document API Lambda function",
            export_name=f"{self.stack_name}-DocumentApiArn"
        )
        
        self.add_stack_output(
            "DocumentApiLambdaName",
            value=self.document_api_lambda.function_name,
            description="Name of Document API Lambda function",
            export_name=f"{self.stack_name}-DocumentApiName"
        )

    def create_insight_extractor_lambda(
        self,
        vector_bucket_name: str,
        vector_index_arn: str,
        dynamodb_table_name: str,
        boto3_layer_arn: str
    ) -> lambda_.Function:
        """
        Create the Insight Extraction Lambda function.
        
        Args:
            vector_bucket_name: S3 Vector bucket name
            vector_index_arn: S3 Vector index ARN
            dynamodb_table_name: DynamoDB cache table name
            boto3_layer_arn: ARN of boto3 Lambda layer
            
        Returns:
            Lambda Function construct
        """
        # Create CloudWatch log group
        log_group = logs.LogGroup(
            self,
            "InsightExtractorLogGroup",
            log_group_name=f"/aws/lambda/{self.get_resource_name('insight-extractor')}",
            removal_policy=self.removal_policy,
            retention=logs.RetentionDays.ONE_MONTH
        )
        
        # Create Lambda execution role
        execution_role = self._create_insight_extractor_role()
        
        # Create Lambda layer from ARN
        boto3_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "InsightBoto3Layer",
            layer_version_arn=boto3_layer_arn
        )
        
        # Create Lambda function
        self.insight_extractor_lambda = lambda_.Function(
            self,
            "InsightExtractorLambda",
            function_name=self.get_resource_name("insight-extractor"),
            description="Extract structured insights from documents using vector search and Bedrock",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # ARM64 architecture for cost optimization
            architecture=lambda_.Architecture.ARM_64,
            handler="insight_extractor.handler",
            code=lambda_.Code.from_asset("lambda/insight_extractor"),
            # Memory and timeout configuration
            memory_size=self.lambda_memory,
            timeout=Duration.seconds(600),  # 5 minutes for insight extraction
            # Attach layer
            layers=[boto3_layer],
            # IAM role
            role=execution_role,
            # Environment variables
            environment={
                "VECTOR_BUCKET_NAME": vector_bucket_name,
                "VECTOR_INDEX_ARN": vector_index_arn,
                "EMBED_MODEL_ID": self.embed_model_id,
                "INSIGHT_MODEL_ID": self.config.get("insight_model_id", "anthropic.claude-3-sonnet-20240229-v1:0"),
                "DYNAMODB_TABLE_NAME": dynamodb_table_name,
                "REGION": self.region,
                "LOG_LEVEL": self.config.get("log_level", "INFO"),
                "MAX_TOKENS": self.config.get("max_tokens", "50000"),  # Max output tokens for Claude 3.5 Sonnet
                "TOP_K_RESULTS": str(self.config.get("top_k_results", 5)),
            },
            # CloudWatch Logs
            log_group=log_group,
            # Reserved concurrent executions (optional)
            reserved_concurrent_executions=self.config.get(
                "insight_extractor_concurrency",
                None
            ),
        )
        
        # Add outputs
        self._add_insight_extractor_outputs()
        
        return self.insight_extractor_lambda

    def _create_insight_extractor_role(self) -> iam.Role:
        """
        Create IAM role for Insight Extraction Lambda.
        
        Returns:
            IAM Role with necessary permissions
        """
        role = iam.Role(
            self,
            "InsightExtractorRole",
            role_name=self.get_resource_name("insight-extractor-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Insight Extraction Lambda function",
            managed_policies=[
                # Basic Lambda execution permissions
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )
        
        return role

    def grant_insight_extractor_s3_permissions(
        self,
        vector_bucket_name: str,
        vector_index_arn: str
    ) -> None:
        """
        Grant S3 Vectors permissions to Insight Extraction Lambda.
        
        Args:
            vector_bucket_name: S3 Vector bucket name
            vector_index_arn: S3 Vector index ARN
        """
        if not self.insight_extractor_lambda:
            raise ValueError("Insight extractor Lambda function must be set first")
        
        # Grant S3 Vectors read permissions
        self.insight_extractor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::{vector_bucket_name}",
                    f"arn:aws:s3:::{vector_bucket_name}/*"
                ]
            )
        )
        
        # Grant S3 Vectors API permissions
        self.insight_extractor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:GetVectors",
                    "s3vectors:QueryVectors",
                ],
                resources=[
                    vector_index_arn
                ]
            )
        )

    def grant_insight_extractor_bedrock_permissions(self) -> None:
        """Grant Bedrock permissions to Insight Extraction Lambda."""
        if not self.insight_extractor_lambda:
            raise ValueError("Insight extractor Lambda function must be set first")
        
        insight_model_id = self.config.get("insight_model_id", "anthropic.claude-3-sonnet-20240229-v1:0")
        
        # Grant permission to invoke Bedrock models
        self.insight_extractor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    # Titan V2 embedding model
                    f"arn:aws:bedrock:{self.region}::foundation-model/{self.embed_model_id}",
                    # Insight model (Claude or other)
                    f"arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:*:inference-profile/*",
                    f"arn:aws:bedrock:*:*:application-inference-profile/*"
                ]
            )
        )

    def grant_insight_extractor_dynamodb_permissions(
        self,
        dynamodb_table_arn: str
    ) -> None:
        """
        Grant DynamoDB permissions to Insight Extraction Lambda.
        
        Args:
            dynamodb_table_arn: DynamoDB table ARN
        """
        if not self.insight_extractor_lambda:
            raise ValueError("Insight extractor Lambda function must be set first")
        
        # Grant DynamoDB permissions
        self.insight_extractor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:Query",
                ],
                resources=[
                    dynamodb_table_arn,
                    f"{dynamodb_table_arn}/index/*"  # For any GSIs
                ]
            )
        )

    def _add_insight_extractor_outputs(self) -> None:
        """Add CloudFormation outputs for Insight Extraction Lambda."""
        if not self.insight_extractor_lambda:
            return
        
        self.add_stack_output(
            "InsightExtractorLambdaArn",
            value=self.insight_extractor_lambda.function_arn,
            description="ARN of Insight Extraction Lambda function",
            export_name=f"{self.stack_name}-InsightExtractorArn"
        )
        
        self.add_stack_output(
            "InsightExtractorLambdaName",
            value=self.insight_extractor_lambda.function_name,
            description="Name of Insight Extraction Lambda function",
            export_name=f"{self.stack_name}-InsightExtractorName"
        )

    def configure_s3_event_notifications(self, documents_bucket: s3.IBucket) -> None:
        """
        Configure S3 event notifications to trigger Document Processing Lambda.
        
        This method is called from the Lambda stack to avoid cyclic dependencies.
        The S3 stack creates the bucket, and the Lambda stack configures the notifications.
        
        Args:
            documents_bucket: S3 bucket for document storage
        """
        if not self.document_processor_lambda:
            raise ValueError("Document processor Lambda function must be created first")
        
        # Import S3 notifications
        from aws_cdk import aws_s3_notifications as s3n
        
        # Add Lambda destination for OBJECT_CREATED events
        documents_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.document_processor_lambda),
            s3.NotificationKeyFilter(
                prefix="",
                suffix=".pdf"
            )
        )
        
        # Add Lambda destination for OBJECT_REMOVED_DELETE events
        documents_bucket.add_event_notification(
            s3.EventType.OBJECT_REMOVED_DELETE,
            s3n.LambdaDestination(self.document_processor_lambda),
            s3.NotificationKeyFilter(
                prefix="",
                suffix=".pdf"
            )
        )
        
        # Grant S3 service principal permission to invoke Lambda
        self.document_processor_lambda.add_permission(
            "AllowS3Invocation",
            principal=iam.ServicePrincipal("s3.amazonaws.com"),
            source_arn=documents_bucket.bucket_arn,
            action="lambda:InvokeFunction"
        )

    def _grant_document_processor_dynamodb_permissions(self, dynamodb_table_name: str) -> None:
        """
        Grant DynamoDB permissions to Document Processing Lambda.
        
        Args:
            dynamodb_table_name: DynamoDB table name
        """
        if not self.document_processor_lambda:
            raise ValueError("Document processor Lambda function must be set first")
        
        # Grant DynamoDB permissions for processing status management
        self.document_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/{dynamodb_table_name}",
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/{dynamodb_table_name}/index/*"
                ]
            )
        )

    def _grant_document_api_dynamodb_permissions(self, dynamodb_table_name: str) -> None:
        """
        Grant DynamoDB permissions to Document API Lambda.
        
        Args:
            dynamodb_table_name: DynamoDB table name
        """
        if not self.document_api_lambda:
            raise ValueError("Document API Lambda function must be set first")
        
        # Grant DynamoDB read permissions for processing status queries
        self.document_api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                ],
                resources=[
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/{dynamodb_table_name}",
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/{dynamodb_table_name}/index/*"
                ]
            )
        )

    def _add_document_processor_outputs(self) -> None:
        """Add CloudFormation outputs for Document Processing Lambda."""
        if not self.document_processor_lambda:
            return
        
        self.add_stack_output(
            "DocumentProcessorLambdaArn",
            value=self.document_processor_lambda.function_arn,
            description="ARN of Document Processing Lambda function",
            export_name=f"{self.stack_name}-DocumentProcessorArn"
        )
        
        self.add_stack_output(
            "DocumentProcessorLambdaName",
            value=self.document_processor_lambda.function_name,
            description="Name of Document Processing Lambda function",
            export_name=f"{self.stack_name}-DocumentProcessorName"
        )

    def create_websocket_api(self) -> apigatewayv2.CfnApi:
        """
        Create WebSocket API for real-time progress updates.
        
        This method creates the WebSocket API within the Lambda stack to avoid
        cyclic dependencies between Lambda and WebSocket stacks.
        
        Returns:
            WebSocket API construct
        """
        # Create CloudWatch log group for WebSocket API
        log_group = logs.LogGroup(
            self,
            "WebSocketApiLogGroup",
            log_group_name=f"/aws/apigateway/{self.get_resource_name('websocket-api')}",
            removal_policy=self.removal_policy,
            retention=logs.RetentionDays.ONE_MONTH
        )

        # Create WebSocket API
        websocket_api = apigatewayv2.CfnApi(
            self,
            "WebSocketApi",
            name=self.get_resource_name("websocket-api"),
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
            description=f"WebSocket API for Document Insight Extraction - {self.env_name}",
            # Disable execute API endpoint for security
            disable_execute_api_endpoint=False
        )

        return websocket_api

    def configure_websocket_routes(
        self, 
        document_processor_lambda: lambda_.IFunction,
        websocket_api: apigatewayv2.CfnApi
    ) -> str:
        """
        Configure WebSocket routes with Document Processing Lambda.
        
        Args:
            document_processor_lambda: Lambda function to handle WebSocket connections
            websocket_api: WebSocket API to configure routes for
            
        Returns:
            WebSocket URL
        """
        # Create IAM role for API Gateway to invoke Lambda
        integration_role = iam.Role(
            self,
            "WebSocketIntegrationRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            inline_policies={
                "LambdaInvokePolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["lambda:InvokeFunction"],
                            resources=[document_processor_lambda.function_arn]
                        )
                    ]
                )
            }
        )

        # Create Lambda integration
        integration = apigatewayv2.CfnIntegration(
            self,
            "WebSocketLambdaIntegration",
            api_id=websocket_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{document_processor_lambda.function_arn}/invocations",
            credentials_arn=integration_role.role_arn,
            content_handling_strategy="CONVERT_TO_TEXT"
        )

        # Create routes
        connect_route = apigatewayv2.CfnRoute(
            self,
            "WebSocketConnectRoute",
            api_id=websocket_api.ref,
            route_key="$connect",
            target=f"integrations/{integration.ref}",
            authorization_type="NONE"
        )

        disconnect_route = apigatewayv2.CfnRoute(
            self,
            "WebSocketDisconnectRoute",
            api_id=websocket_api.ref,
            route_key="$disconnect",
            target=f"integrations/{integration.ref}",
            authorization_type="NONE"
        )

        default_route = apigatewayv2.CfnRoute(
            self,
            "WebSocketDefaultRoute",
            api_id=websocket_api.ref,
            route_key="$default",
            target=f"integrations/{integration.ref}",
            authorization_type="NONE"
        )

        progress_route = apigatewayv2.CfnRoute(
            self,
            "WebSocketProgressRoute",
            api_id=websocket_api.ref,
            route_key="progress",
            target=f"integrations/{integration.ref}",
            authorization_type="NONE"
        )

        # Create deployment
        deployment = apigatewayv2.CfnDeployment(
            self,
            "WebSocketApiDeployment",
            api_id=websocket_api.ref,
            description=f"Deployment for {self.env_name} environment"
        )

        # Add dependencies on all routes
        deployment.add_dependency(connect_route)
        deployment.add_dependency(disconnect_route)
        deployment.add_dependency(default_route)
        deployment.add_dependency(progress_route)

        # Create stage
        stage = apigatewayv2.CfnStage(
            self,
            "WebSocketApiStage",
            api_id=websocket_api.ref,
            stage_name=self.env_name,
            deployment_id=deployment.ref,
            description=f"WebSocket API stage for {self.env_name} environment",
            default_route_settings=apigatewayv2.CfnStage.RouteSettingsProperty(
                throttling_burst_limit=self.config.get("api_throttle_burst", 2000),
                throttling_rate_limit=self.config.get("api_throttle_rate", 1000),
                logging_level="INFO",
                data_trace_enabled=True,
                detailed_metrics_enabled=True,
            )
        )

        # Add Lambda permissions for WebSocket API
        self._add_websocket_lambda_permissions(document_processor_lambda, websocket_api)

        # Create WebSocket URL
        websocket_url = f"wss://{websocket_api.ref}.execute-api.{self.region}.amazonaws.com/{self.env_name}"

        # Store WebSocket URL in SSM Parameter Store for cross-stack access
        ssm.StringParameter(
            self,
            "WebSocketUrlParameter",
            parameter_name=f"/{self.project_name}/{self.env_name}/api/websocket-url",
            string_value=websocket_url,
            description="WebSocket API Gateway URL"
        )

        # Create outputs
        CfnOutput(
            self,
            "WebSocketApiUrl",
            value=websocket_url,
            description="WebSocket API Gateway URL",
            export_name=f"{self.stack_name}-WebSocketApiUrl"
        )

        return websocket_url

    def _add_websocket_lambda_permissions(
        self, 
        lambda_function: lambda_.IFunction,
        websocket_api: apigatewayv2.CfnApi
    ) -> None:
        """
        Add Lambda permissions for WebSocket API routes.
        
        Args:
            lambda_function: Lambda function to grant permissions to
            websocket_api: WebSocket API
        """
        import os
        account_id = os.getenv('CDK_DEFAULT_ACCOUNT')
        region = os.getenv('CDK_DEFAULT_REGION')
        
        # Permission for $connect route
        lambda_.CfnPermission(
            self,
            "WebSocketConnectLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=lambda_function.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{websocket_api.ref}/*/$connect",
            source_account=account_id,
        )
        
        # Permission for $disconnect route
        lambda_.CfnPermission(
            self,
            "WebSocketDisconnectLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=lambda_function.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{websocket_api.ref}/*/$disconnect",
            source_account=account_id,
        )
        
        # Permission for $default route
        lambda_.CfnPermission(
            self,
            "WebSocketDefaultLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=lambda_function.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{websocket_api.ref}/*/$default",
            source_account=account_id,
        )
        
        # Permission for progress route
        lambda_.CfnPermission(
            self,
            "WebSocketProgressLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=lambda_function.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{websocket_api.ref}/*/progress",
            source_account=account_id,
        )
        
        # Permission for any route (wildcard)
        lambda_.CfnPermission(
            self,
            "WebSocketAllRoutesLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=lambda_function.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{websocket_api.ref}/*/*",
            source_account=account_id,
        )

    def create_image_insights_lambda(
        self,
        pypdf_layer_arn: str,
        boto3_layer_arn: str
    ) -> lambda_.Function:
        """
        Create the Image Insights Lambda function.
        
        Args:
            pypdf_layer_arn: ARN of pypdf Lambda layer (includes Pillow)
            boto3_layer_arn: ARN of boto3 Lambda layer
            
        Returns:
            Lambda Function construct
        """
        # Create CloudWatch log group
        log_group = logs.LogGroup(
            self,
            "ImageInsightsLogGroup",
            log_group_name=f"/aws/lambda/{self.get_resource_name('image-insights')}",
            removal_policy=self.removal_policy,
            retention=logs.RetentionDays.ONE_MONTH
        )
        
        # Create Lambda execution role
        execution_role = self._create_image_insights_role()
        
        # Create Lambda layers from ARNs
        pypdf_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "ImageInsightsPypdfLayer",
            layer_version_arn=pypdf_layer_arn
        )
        
        boto3_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "ImageInsightsBoto3Layer",
            layer_version_arn=boto3_layer_arn
        )
        
        # Create Lambda function
        self.image_insights_lambda = lambda_.Function(
            self,
            "ImageInsightsLambda",
            function_name=self.get_resource_name("image-insights"),
            description="Analyze images using Claude vision model for content moderation and insights",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # x86_64 architecture for Pillow/OpenCV compatibility
            architecture=lambda_.Architecture.X86_64,
            handler="image_insights.handler",
            code=lambda_.Code.from_asset("lambda/image_insights"),
            # Memory and timeout configuration
            memory_size=2048,
            timeout=Duration.seconds(120),  # 2 minutes for image analysis
            # Attach layers
            layers=[pypdf_layer, boto3_layer],
            # IAM role
            role=execution_role,
            # Environment variables
            environment={
                "REGION": self.region,
                "VISION_MODEL_ID": self.config.get("vision_model_id", "anthropic.claude-3-sonnet-20240229-v1:0"),
                "LOG_LEVEL": self.config.get("log_level", "INFO"),
            },
            # CloudWatch Logs
            log_group=log_group,
        )
        
        # Grant Bedrock permissions
        self._grant_image_insights_bedrock_permissions()
        
        # Add outputs
        self._add_image_insights_outputs()
        
        return self.image_insights_lambda

    def _create_image_insights_role(self) -> iam.Role:
        """
        Create IAM role for Image Insights Lambda.
        
        Returns:
            IAM Role with necessary permissions
        """
        role = iam.Role(
            self,
            "ImageInsightsRole",
            role_name=self.get_resource_name("image-insights-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Image Insights Lambda function",
            managed_policies=[
                # Basic Lambda execution permissions
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )
        
        return role

    def _grant_image_insights_bedrock_permissions(self) -> None:
        """Grant Bedrock permissions to Image Insights Lambda."""
        if not self.image_insights_lambda:
            raise ValueError("Image insights Lambda function must be set first")
        
        vision_model_id = self.config.get("vision_model_id", "anthropic.claude-3-sonnet-20240229-v1:0")
        
        # Grant permission to invoke Bedrock vision models
        self.image_insights_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    # Allow any Bedrock model for vision analysis
                    f"arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:*:inference-profile/*",
                    f"arn:aws:bedrock:*:*:application-inference-profile/*"
                ]
            )
        )

    def _add_image_insights_outputs(self) -> None:
        """Add CloudFormation outputs for Image Insights Lambda."""
        if not self.image_insights_lambda:
            return
        
        self.add_stack_output(
            "ImageInsightsLambdaArn",
            value=self.image_insights_lambda.function_arn,
            description="ARN of Image Insights Lambda function",
            export_name=f"{self.stack_name}-ImageInsightsArn"
        )
        
        self.add_stack_output(
            "ImageInsightsLambdaName",
            value=self.image_insights_lambda.function_name,
            description="Name of Image Insights Lambda function",
            export_name=f"{self.stack_name}-ImageInsightsName"
        )
