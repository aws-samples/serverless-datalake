"""
AppRunner Hosting Stack for Document Insight Extraction System

This module defines the AppRunner service infrastructure for hosting the React frontend.
The ECR repository and Docker image building is handled by the ECR stack.
"""
from aws_cdk import (
    aws_apprunner as apprunner,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct
from .base_stack import BaseDocumentInsightStack
from typing import Dict, Any


class AppRunnerHostingStack(BaseDocumentInsightStack):
    """
    Stack for AppRunner hosting infrastructure.
    
    Creates:
    - AppRunner service with auto-scaling
    - IAM roles for AppRunner
    
    Note: ECR repository and Docker image building is handled by the ECR stack
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        config: Dict[str, Any],
        api_endpoint: str,
        wss_endpoint: str,
        user_pool_id: str,
        user_pool_client_id: str,
        ecr_repository_uri: str,
        **kwargs
    ) -> None:
        """
        Initialize the AppRunner hosting stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration
            api_endpoint: API Gateway REST endpoint URL
            wss_endpoint: WebSocket API endpoint URL
            user_pool_id: Cognito User Pool ID
            user_pool_client_id: Cognito User Pool Client ID
            ecr_repository_uri: ECR repository URI from ECR stack
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        self.api_endpoint = api_endpoint
        self.wss_endpoint = wss_endpoint
        self.user_pool_id = user_pool_id
        self.user_pool_client_id = user_pool_client_id
        self.ecr_repository_uri = ecr_repository_uri

        # Create AppRunner service
        self.apprunner_service = self._create_apprunner_service()

        # Export outputs
        self._create_outputs()



    def _create_apprunner_service(self) -> apprunner.CfnService:
        """
        Create AppRunner service for hosting the React frontend.
        
        Returns:
            AppRunner Service construct
        """
        # Create IAM role for AppRunner instance
        instance_role = iam.Role(
            self,
            "AppRunnerInstanceRole",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
            description="IAM role for AppRunner instance"
        )

        # Create IAM role for AppRunner to access ECR
        access_role = iam.Role(
            self,
            "AppRunnerAccessRole",
            assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"),
            description="IAM role for AppRunner to access ECR",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSAppRunnerServicePolicyForECRAccess"
                )
            ]
        )

        # Get configuration values
        cpu = self.config.get("apprunner_cpu", "2048")  # 2 vCPU
        memory = self.config.get("apprunner_memory", "4096")  # 4 GB
        min_instances = self.config.get("apprunner_min_instances", 1)
        max_instances = self.config.get("apprunner_max_instances", 10)

        # Create AppRunner service
        service = apprunner.CfnService(
            self,
            "UIService",
            service_name=self.get_resource_name("ui-service"),
            source_configuration=apprunner.CfnService.SourceConfigurationProperty(
                authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=access_role.role_arn
                ),
                image_repository=apprunner.CfnService.ImageRepositoryProperty(
                    image_identifier=f"{self.ecr_repository_uri}:latest",
                    image_repository_type="ECR",
                    image_configuration=apprunner.CfnService.ImageConfigurationProperty(
                        port="80",
                        runtime_environment_variables=[
                            apprunner.CfnService.KeyValuePairProperty(
                                name="REACT_APP_API_ENDPOINT",
                                value=self.api_endpoint
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="REACT_APP_WSS_ENDPOINT",
                                value=self.wss_endpoint
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="REACT_APP_USER_POOL_ID",
                                value=self.user_pool_id
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="REACT_APP_USER_POOL_CLIENT_ID",
                                value=self.user_pool_client_id
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="REACT_APP_REGION",
                                value=self.region
                            )
                        ]
                    )
                )
            ),
            instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(
                cpu=cpu,
                memory=memory,
                instance_role_arn=instance_role.role_arn
            ),
            auto_scaling_configuration_arn=None,  # Use default auto-scaling
            health_check_configuration=apprunner.CfnService.HealthCheckConfigurationProperty(
                protocol="HTTP",
                path="/health",
                interval=10,
                timeout=5,
                healthy_threshold=1,
                unhealthy_threshold=5
            )
        )

        return service



    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for the stack."""
        # AppRunner service URL
        self.add_stack_output(
            "AppRunnerServiceUrl",
            value=f"https://{self.apprunner_service.attr_service_url}",
            description="AppRunner service URL for the frontend application",
            export_name=f"{self.stack_name}-AppRunnerServiceUrl"
        )

        # AppRunner service ARN
        self.add_stack_output(
            "AppRunnerServiceArn",
            value=self.apprunner_service.attr_service_arn,
            description="AppRunner service ARN",
            export_name=f"{self.stack_name}-AppRunnerServiceArn"
        )
