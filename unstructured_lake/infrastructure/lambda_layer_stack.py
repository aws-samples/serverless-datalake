"""
Lambda Layer Stack for Document Insight Extraction System

This module defines the Lambda layer build infrastructure using AWS CodeBuild
to create layers for pypdf and boto3 with S3 Vectors support.
"""
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct
from typing import Dict, Any


class LambdaLayerStack(Stack):
    """
    Stack for building Lambda layers using CodeBuild.
    
    Creates a single CodeBuild project that builds and publishes Lambda layers for:
    - pypdf: PDF text extraction library
    - boto3: AWS SDK with S3 Vectors API support
    
    Both layers are built for x86_64 and ARM64 architectures in one execution.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        config: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Initialize the Lambda Layer Stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.config = config
        self.project_name = "document-insight"
        
        # Create S3 bucket for build artifacts
        self.artifacts_bucket = s3.Bucket(
            self,
            "LayerArtifactsBucket",
            bucket_name=f"{self.project_name}-layer-artifacts-{env_name}-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=self._get_removal_policy(),
            auto_delete_objects=(env_name == "dev")
        )
        
        # Create IAM role for CodeBuild
        self.codebuild_role = self._create_codebuild_role()
        
        # Create single CodeBuild project for all layers
        self.layers_build_project = self._create_layers_build_project()
        
        # Set layer ARNs (will be populated after CodeBuild runs)
        # Using x86_64 layers as default for Lambda functions
        self.pypdf_layer_arn = f"arn:aws:lambda:{self.region}:{self.account}:layer:{self.project_name}-pypdf-layer-{self.env_name}-x86-64:1"
        self.boto3_layer_arn = f"arn:aws:lambda:{self.region}:{self.account}:layer:{self.project_name}-boto3-layer-{self.env_name}-x86-64:1"
        self.langchain_layer_arn = f"arn:aws:lambda:{self.region}:{self.account}:layer:{self.project_name}-langchain-layer-{self.env_name}-x86-64:1"
        
        # Add stack outputs
        self._add_outputs()

    def _get_removal_policy(self):
        """Get removal policy based on environment."""
        from aws_cdk import RemovalPolicy
        return RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN

    def _create_codebuild_role(self) -> iam.Role:
        """
        Create IAM role for CodeBuild with necessary permissions.
        
        Returns:
            IAM Role for CodeBuild projects
        """
        role = iam.Role(
            self,
            "CodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            description="Role for Lambda layer build CodeBuild projects",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSCodeBuildDeveloperAccess"
                )
            ]
        )
        
        # Grant permissions to publish Lambda layers
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:PublishLayerVersion",
                    "lambda:GetLayerVersion",
                    "lambda:DeleteLayerVersion",
                    "lambda:ListLayerVersions"
                ],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account}:layer:*"
                ]
            )
        )
        
        # Grant S3 permissions for artifacts
        self.artifacts_bucket.grant_read_write(role)
        
        # Grant CloudWatch Logs permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/codebuild/*"
                ]
            )
        )
        
        return role

    def _create_layers_build_project(self) -> codebuild.Project:
        """
        Create CodeBuild project for all Lambda layers.
        
        This single project builds both pypdf and boto3 layers for both
        x86_64 and ARM64 architectures in one execution.
        
        Returns:
            CodeBuild Project for all layers
        """
        # Read buildspec from YAML file
        import yaml
        import os
        
        buildspec_path = os.path.join(os.path.dirname(__file__), "..", "buildspecs", "buildspec_layers.yml")
        with open(buildspec_path, "r") as stream:
            build_spec_yml = yaml.safe_load(stream)

        project = codebuild.Project(
            self,
            f"lambda_layer_build_{self.env_name}",
            project_name=f"{self.project_name}-lambda-layer-builder-{self.env_name}",
            description="Build all Lambda layers (pypdf, boto3, and langchain) for x86_64",
            role=self.codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.SMALL,
                privileged=False
            ),
            build_spec=codebuild.BuildSpec.from_object_to_yaml(build_spec_yml),
            timeout=Duration.minutes(45),
            artifacts=codebuild.Artifacts.s3(
                bucket=self.artifacts_bucket,
                include_build_id=True,
                package_zip=True,
                path="lambda-layers"
            ),
            environment_variables={
                "PROJECT_NAME": codebuild.BuildEnvironmentVariable(
                    value=self.project_name
                ),
                "ENV_NAME": codebuild.BuildEnvironmentVariable(
                    value=self.env_name
                ),
                "AWS_REGION": codebuild.BuildEnvironmentVariable(
                    value=self.region
                ),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(
                    value=self.account
                )
            }
        )
        
        return project

    def _add_outputs(self) -> None:
        """Add CloudFormation outputs for the stack."""
        CfnOutput(
            self,
            "LayersBuildProjectName",
            value=self.layers_build_project.project_name,
            description="CodeBuild project name for all Lambda layers",
            export_name=f"{self.stack_name}-LayersBuildProject"
        )
        
        CfnOutput(
            self,
            "ArtifactsBucketName",
            value=self.artifacts_bucket.bucket_name,
            description="S3 bucket for layer build artifacts",
            export_name=f"{self.stack_name}-ArtifactsBucket"
        )
        
        CfnOutput(
            self,
            "PypdfLayerArn",
            value=self.pypdf_layer_arn,
            description="ARN of pypdf Lambda layer (version 1)",
            export_name=f"{self.stack_name}-PypdfLayerArn"
        )
        
        CfnOutput(
            self,
            "Boto3LayerArn", 
            value=self.boto3_layer_arn,
            description="ARN of boto3 Lambda layer (version 1)",
            export_name=f"{self.stack_name}-Boto3LayerArn"
        )
        
        CfnOutput(
            self,
            "LangChainLayerArn",
            value=self.langchain_layer_arn,
            description="ARN of LangChain Lambda layer (version 1)",
            export_name=f"{self.stack_name}-LangChainLayerArn"
        )
