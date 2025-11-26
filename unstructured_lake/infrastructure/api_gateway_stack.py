"""
API Gateway Stack for Document Insight Extraction System

This module defines the REST API Gateway with endpoints for document management
and insight extraction, including Cognito authorization and CORS configuration.

Note: WebSocket API for real-time progress updates is now defined in lambda_function_stack.py
"""
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_cognito as cognito,
    aws_ssm as ssm,
    Duration,
)
from constructs import Construct
from infrastructure.base_stack import BaseDocumentInsightStack
from typing import Optional


class ApiGatewayStack(BaseDocumentInsightStack):
    """
    Stack for API Gateway REST API resources.
    
    Creates:
    - REST API with regional endpoint
    - Cognito authorizer for authentication
    - Document management endpoints
    - Insight extraction endpoints
    - CORS configuration
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        config: dict,
        cognito_user_pool: cognito.IUserPool,
        insight_extractor_arn: str,
        document_processor_arn: str,
        document_api_arn: str,
        image_insights_arn: str,
        **kwargs
    ) -> None:
        """
        Initialize the API Gateway stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            cognito_user_pool: Cognito User Pool for authorization
            insight_extractor_arn: ARN of the insight extractor Lambda function
            document_processor_arn: ARN of the document processor Lambda function
            document_api_arn: ARN of the document api Lambda function
            image_insights_arn: ARN of the image insights Lambda function
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        self.cognito_user_pool = cognito_user_pool
        
        # Get throttling configuration from config
        self.throttle_rate = config.get("api_throttle_rate", 1000)
        self.throttle_burst = config.get("api_throttle_burst", 2000)
        
        # Create REST API
        self.rest_api = self._create_rest_api()
        
        # Create Cognito authorizer
        self.authorizer = self._create_cognito_authorizer()
        
        # Import Lambda functions from ARNs (following reference project pattern)
        self.insight_extraction_lambda = lambda_.Function.from_function_attributes(
            self, 
            f"{env_name}_insight_extractor_lambda", 
            function_arn=insight_extractor_arn, 
            same_environment=True
        )

        # Import Document API Lambda from ARN
        self.document_api_lambda = lambda_.Function.from_function_attributes(
            self, 
            f"{env_name}_document_api_lambda", 
            function_arn=document_api_arn, 
            same_environment=True
        )

        # Import Image Insights Lambda from ARN
        self.image_insights_lambda = lambda_.Function.from_function_attributes(
            self, 
            f"{env_name}_image_insights_lambda", 
            function_arn=image_insights_arn, 
            same_environment=True
        )
                
        # Configure API endpoints with imported Lambda functions
        self._configure_all_endpoints()
        
        # Export outputs
        self._create_outputs()

    def _create_rest_api(self) -> apigateway.RestApi:
        """
        Create REST API with regional endpoint and CORS configuration.
        
        Returns:
            RestApi construct
        """
        # CORS configuration handled manually per resource to avoid conflicts

        # Create REST API
        rest_api = apigateway.RestApi(
            self,
            "DocumentInsightRestApi",
            rest_api_name=self.get_resource_name("rest-api"),
            description=f"Document Insight Extraction System REST API - {self.env_name}",
            # Regional endpoint for better performance and lower cost
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            # CORS configuration handled manually per resource
            # Deployment configuration
            deploy=True,
            deploy_options=apigateway.StageOptions(
                stage_name=self.env_name,
                # Throttling configuration
                throttling_rate_limit=self.throttle_rate,
                throttling_burst_limit=self.throttle_burst,
                # Logging configuration
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
                # Tracing
                tracing_enabled=True
            ),
            # CloudWatch role for logging
            cloud_watch_role=True,
            # API key configuration (optional)
            api_key_source_type=apigateway.ApiKeySourceType.HEADER
        )

        return rest_api

    def _create_cognito_authorizer(self) -> apigateway.CognitoUserPoolsAuthorizer:
        """
        Create Cognito User Pools Authorizer for API Gateway.
        
        Returns:
            CognitoUserPoolsAuthorizer construct
        """
        authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "DocumentInsightApiAuthorizer",
            cognito_user_pools=[self.cognito_user_pool],
            authorizer_name=self.get_resource_name("api-authorizer"),
            # Token validity - 24 hours
            results_cache_ttl=Duration.hours(24),
            # Identity source - Authorization header
            identity_source="method.request.header.Authorization"
        )

        return authorizer

    def _configure_all_endpoints(self) -> None:
        """
        Configure all API Gateway endpoints with imported Lambda functions.
        
        This method configures all endpoints and adds the required CfnPermissions
        for imported Lambda functions, following the reference project pattern.
        """
        # Store resources for CORS configuration
        self.api_resources_for_cors = []
        
        # Configure insight extraction endpoints
        self.configure_insight_extraction_endpoint(self.insight_extraction_lambda)
        self.configure_insight_retrieval_endpoint(self.insight_extraction_lambda)
        
        # Configure document management endpoints
        self.configure_presigned_url_endpoint(self.document_api_lambda)
        self.configure_document_list_endpoint(self.document_api_lambda)
        self.configure_document_status_endpoint(self.document_api_lambda)
        
        # Configure image insights endpoint
        self.configure_image_insights_endpoint(self.image_insights_lambda)
        
        # Add CORS to all collected resources
        self._add_cors_to_collected_resources()
        
        # Add Lambda permissions for imported functions (required)
        self._add_all_lambda_permissions()

    def _add_cors_to_collected_resources(self) -> None:
        """
        Add CORS OPTIONS method to all collected API Gateway resources.
        
        This method adds CORS to resources that were collected during endpoint configuration,
        ensuring no duplicates and proper CORS coverage.
        """
        # Use a set to avoid duplicates
        unique_resources = set(self.api_resources_for_cors)
        
        for resource in unique_resources:
            try:
                self.add_cors_options(resource)
            except Exception as e:
                # Log the error but continue with other resources
                print(f"Warning: Failed to add CORS to resource {resource}: {e}")
                continue

    def _add_all_lambda_permissions(self) -> None:
        """
        Add all required Lambda permissions for imported functions.
        
        Following the reference project pattern, imported Lambda functions
        don't retain resource policies, so we need to create CfnPermissions manually.
        """
        import os
        account_id = os.getenv('CDK_DEFAULT_ACCOUNT')
        region = os.getenv('CDK_DEFAULT_REGION')
        
        # Insight Extractor Lambda permissions
        lambda_.CfnPermission(
            self,
            "InsightExtractLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=self.insight_extraction_lambda.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{self.rest_api.rest_api_id}/*/POST/insights/extract",
            source_account=account_id,
        )
        
        lambda_.CfnPermission(
            self,
            "InsightRetrievalLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=self.insight_extraction_lambda.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{self.rest_api.rest_api_id}/*/GET/insights/*",
            source_account=account_id,
        )
        
        # Document API Lambda permissions
        lambda_.CfnPermission(
            self,
            "PresignedUrlLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=self.document_api_lambda.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{self.rest_api.rest_api_id}/*/POST/documents/presigned-url",
            source_account=account_id,
        )
        
        lambda_.CfnPermission(
            self,
            "DocumentListLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=self.document_api_lambda.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{self.rest_api.rest_api_id}/*/GET/documents",
            source_account=account_id,
        )
        
        lambda_.CfnPermission(
            self,
            "DocumentStatusLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=self.document_api_lambda.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{self.rest_api.rest_api_id}/*/GET/documents/*/status",
            source_account=account_id,
        )
        
        # Image Insights Lambda permissions
        lambda_.CfnPermission(
            self,
            "ImageInsightsLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=self.image_insights_lambda.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{region}:{account_id}:{self.rest_api.rest_api_id}/*/POST/image-insights/analyze",
            source_account=account_id,
        )

    def configure_presigned_url_endpoint(
        self,
        presigned_url_lambda: lambda_.IFunction
    ) -> None:
        """
        Configure POST /documents/presigned-url endpoint.
        
        This endpoint generates presigned POST URLs for direct S3 uploads.
        
        Args:
            presigned_url_lambda: Lambda function to generate presigned URLs
        """
        self.presigned_url_lambda = presigned_url_lambda
        
        # Create /documents resource
        documents_resource = self.rest_api.root.add_resource("documents")
        
        # Create /documents/presigned-url resource
        presigned_url_resource = documents_resource.add_resource("presigned-url")
        
        # Collect resources for CORS configuration
        self.api_resources_for_cors.extend([documents_resource, presigned_url_resource])
        
        # Create Lambda integration
        presigned_url_integration = apigateway.LambdaIntegration(
            presigned_url_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Add POST method with Cognito authorizer
        presigned_url_resource.add_method(
            "POST",
            presigned_url_integration,
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )
        


    def configure_document_list_endpoint(
        self,
        document_list_lambda: lambda_.IFunction
    ) -> None:
        """
        Configure GET /documents endpoint.
        
        This endpoint lists all documents for the authenticated user.
        
        Args:
            document_list_lambda: Lambda function to list documents
        """
        self.document_list_lambda = document_list_lambda
        
        # Get or create /documents resource
        documents_resource = self.rest_api.root.get_resource("documents")
        if not documents_resource:
            documents_resource = self.rest_api.root.add_resource("documents")
            # Only add to CORS list if we created it (not if it already existed)
            self.api_resources_for_cors.append(documents_resource)
        
        # Create Lambda integration
        document_list_integration = apigateway.LambdaIntegration(
            document_list_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Add GET method with Cognito authorizer
        documents_resource.add_method(
            "GET",
            document_list_integration,
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )
        


    def configure_document_status_endpoint(
        self,
        document_api_lambda: lambda_.IFunction
    ) -> None:
        """
        Configure GET /documents/{docId}/status endpoint.
        
        This endpoint retrieves the processing status for a document.
        
        Args:
            document_api_lambda: Lambda function to get document status
        """
        # Get or create /documents resource
        documents_resource = self.rest_api.root.get_resource("documents")
        if not documents_resource:
            documents_resource = self.rest_api.root.add_resource("documents")
            self.api_resources_for_cors.append(documents_resource)
        
        # Create /documents/{docId} resource with path parameter
        doc_id_resource = documents_resource.add_resource("{docId}")
        
        # Create /documents/{docId}/status resource
        status_resource = doc_id_resource.add_resource("status")
        
        # Add resources to CORS list
        self.api_resources_for_cors.extend([doc_id_resource, status_resource])
        
        # Create Lambda integration
        status_integration = apigateway.LambdaIntegration(
            document_api_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Add GET method with Cognito authorizer
        status_resource.add_method(
            "GET",
            status_integration,
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ],
            request_parameters={
                "method.request.path.docId": True  # Required path parameter
            }
        )

    def configure_insight_extraction_endpoint(
        self,
        insight_extraction_lambda: lambda_.IFunction
    ) -> None:
        """
        Configure POST /insights/extract endpoint.
        
        This endpoint extracts insights from a document using natural language prompts.
        Configured with 300 second timeout for long-running insight generation.
        
        Args:
            insight_extraction_lambda: Lambda function to extract insights
        """
        self.insight_extraction_lambda = insight_extraction_lambda
        
        # Create /insights resource
        insights_resource = self.rest_api.root.add_resource("insights")
        
        # Create /insights/extract resource
        extract_resource = insights_resource.add_resource("extract")
        
        # Collect resources for CORS configuration
        self.api_resources_for_cors.extend([insights_resource, extract_resource])
        
        # Create Lambda integration with extended timeout
        insight_extraction_integration = apigateway.LambdaIntegration(
            insight_extraction_lambda,
            proxy=True,
            # timeout=Duration.seconds(300),  # 5 minutes for insight generation
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Add POST method with Cognito authorizer
        extract_resource.add_method(
            "POST",
            insight_extraction_integration,
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )
        


    def configure_insight_retrieval_endpoint(
        self,
        insight_extraction_lambda: lambda_.IFunction
    ) -> None:
        """
        Configure GET /insights/{docId} endpoint.
        
        This endpoint retrieves previously extracted insights from cache.
        
        Args:
            insight_extraction_lambda: Lambda function to retrieve insights
        """
        # Get or create /insights resource
        insights_resource = self.rest_api.root.get_resource("insights")
        if not insights_resource:
            insights_resource = self.rest_api.root.add_resource("insights")
            # Only add to CORS list if we created it (not if it already existed)
            self.api_resources_for_cors.append(insights_resource)
        
        # Create /insights/{docId} resource with path parameter
        doc_id_resource = insights_resource.add_resource("{docId}")
        
        # Add doc_id_resource to CORS list
        self.api_resources_for_cors.append(doc_id_resource)
        
        # Create Lambda integration
        insight_retrieval_integration = apigateway.LambdaIntegration(
            insight_extraction_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Add GET method with Cognito authorizer
        doc_id_resource.add_method(
            "GET",
            insight_retrieval_integration,
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ],
            request_parameters={
                "method.request.path.docId": True  # Required path parameter
            }
        )
        


    def configure_image_insights_endpoint(
        self,
        image_insights_lambda: lambda_.IFunction
    ) -> None:
        """
        Configure POST /image-insights/analyze endpoint.
        
        This endpoint analyzes images using Claude vision model for content moderation.
        
        Args:
            image_insights_lambda: Lambda function to analyze images
        """
        self.image_insights_lambda = image_insights_lambda
        
        # Create /image-insights resource
        image_insights_resource = self.rest_api.root.add_resource("image-insights")
        
        # Create /image-insights/analyze resource
        analyze_resource = image_insights_resource.add_resource("analyze")
        
        # Collect resources for CORS configuration
        self.api_resources_for_cors.extend([image_insights_resource, analyze_resource])
        
        # Create Lambda integration
        image_insights_integration = apigateway.LambdaIntegration(
            image_insights_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Add POST method with Cognito authorizer
        analyze_resource.add_method(
            "POST",
            image_insights_integration,
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )

    def add_cors_options(self, api_resource: apigateway.IResource) -> None:
        """
        Add CORS OPTIONS method to an API Gateway resource.
        
        This method adds a mock integration that responds to preflight CORS requests
        with appropriate headers, following the same pattern as the reference project.
        
        The OPTIONS method is not protected by Cognito authorization to allow
        preflight requests from browsers before authentication.
        
        Args:
            api_resource: The API Gateway resource to add CORS to
        """
        api_resource.add_method(
            "OPTIONS",
            apigateway.MockIntegration(
                integration_responses=[
                    {
                        "statusCode": "200",
                        "responseParameters": {
                            "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent'",
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                            "method.response.header.Access-Control-Allow-Credentials": "'false'",
                            "method.response.header.Access-Control-Allow-Methods": "'OPTIONS,GET,PUT,POST,DELETE'",
                        },
                    }
                ],
                passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                request_templates={"application/json": '{"statusCode": 200}'},
            ),
            method_responses=[
                {
                    "statusCode": "200",
                    "responseParameters": {
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Allow-Credentials": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                }
            ],
            authorization_type=apigateway.AuthorizationType.NONE
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs and SSM parameters for API endpoints."""
        # Store in SSM Parameter Store for cross-stack access
        ssm.StringParameter(
            self,
            "RestApiUrlParameter",
            parameter_name=f"/{self.project_name}/{self.env_name}/api/rest-api-url",
            string_value=self.rest_api.url,
            description="REST API Gateway URL"
        )
        
        # CloudFormation outputs
        # API Gateway URL
        self.add_stack_output(
            "RestApiUrl",
            value=self.rest_api.url,
            description="REST API Gateway URL",
            export_name=f"{self.stack_name}-RestApiUrl"
        )
        
        # API Gateway ID
        self.add_stack_output(
            "RestApiId",
            value=self.rest_api.rest_api_id,
            description="REST API Gateway ID",
            export_name=f"{self.stack_name}-RestApiId"
        )
        
        # API Gateway ARN
        self.add_stack_output(
            "RestApiArn",
            value=self.rest_api.arn_for_execute_api(),
            description="REST API Gateway ARN",
            export_name=f"{self.stack_name}-RestApiArn"
        )
        
        # Stage name
        self.add_stack_output(
            "RestApiStage",
            value=self.env_name,
            description="REST API Gateway stage name",
            export_name=f"{self.stack_name}-RestApiStage"
        )
