"""
ECR Stack for Document Insight Extraction System

This module defines the ECR repository and CodeBuild project for building and pushing
the React frontend Docker image. This stack is deployed before the AppRunner stack
to ensure the Docker image exists before AppRunner tries to deploy it.
"""
from aws_cdk import (
    Duration,
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    CfnOutput,
)
from constructs import Construct
from infrastructure.base_stack import BaseDocumentInsightStack
from typing import Dict, Any


class ECRStack(BaseDocumentInsightStack):
    """
    Stack for ECR repository and UI Docker image building.
    
    Creates:
    - ECR repository for UI Docker images
    - CodeBuild project for building and pushing Docker images
    - S3 bucket for build artifacts
    - IAM roles for CodeBuild
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
        Initialize the ECR stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        # Create S3 bucket for build artifacts
        self.artifacts_bucket = self._create_artifacts_bucket()

        # Create ECR repository
        self.ecr_repository = self._create_ecr_repository()

        # Create CodeBuild project for UI build
        self.ui_build_project = self._create_ui_build_project()
        
        # Ensure CodeBuild project waits for ECR repository to be created
        # This is necessary because the build project needs to push images to the repository
        self.ui_build_project.node.add_dependency(self.ecr_repository)

        # Export outputs
        self._create_outputs()

    def _create_artifacts_bucket(self) -> s3.Bucket:
        """
        Create S3 bucket for CodeBuild artifacts.
        
        Returns:
            S3 Bucket construct
        """
        bucket = s3.Bucket(
            self,
            "UIBuildArtifactsBucket",
            bucket_name=f"di-ui-artifacts-{self.env_name}-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=self.removal_policy,
            auto_delete_objects=(self.env_name == "dev")
        )
        
        return bucket

    def _create_ecr_repository(self) -> ecr.Repository:
        """
        Create ECR repository for UI Docker images.
        
        Returns:
            ECR Repository construct
        """
        repository = ecr.Repository(
            self,
            "UIRepository",
            repository_name=self.get_resource_name("ui-repo"),
            removal_policy=self.removal_policy,
            image_scan_on_push=True,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep last 10 images",
                    max_image_count=10,
                    rule_priority=1
                )
            ]
        )

        return repository

    def _create_ui_build_project(self) -> codebuild.Project:
        """
        Create CodeBuild project for building and pushing the React UI Docker image.
        
        Returns:
            CodeBuild Project construct
        """
        # Create IAM role for CodeBuild
        codebuild_role = iam.Role(
            self,
            "UIBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            description="Role for UI build CodeBuild project",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSCodeBuildDeveloperAccess"
                )
            ]
        )
        
        # Grant ECR permissions
        self.ecr_repository.grant_pull_push(codebuild_role)
        
        # Grant S3 permissions for artifacts
        self.artifacts_bucket.grant_read_write(codebuild_role)
        
        # Grant CloudWatch Logs permissions
        codebuild_role.add_to_policy(
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
        
        # Grant SSM Parameter Store read permissions
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters"
                ],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.project_name}/{self.env_name}/*"
                ]
            )
        )
        
        # Read buildspec from YAML file
        import yaml
        import os
        
        buildspec_path = os.path.join(os.path.dirname(__file__), "..", "buildspecs", "buildspec_dockerize_ui.yml")
        with open(buildspec_path, "r") as stream:
            build_spec_yml = yaml.safe_load(stream)

        # Create S3 source bucket name (following the pattern from reference implementation)
        source_bucket_name = f"codebuild-{self.env_name}-{self.region}-{self.account}-document-insight-input"
        
        project = codebuild.Project(
            self,
            "UIBuildProject",
            project_name=f"{self.project_name}-ui-builder-{self.env_name}",
            description="Build and push React UI Docker image to ECR",
            role=codebuild_role,
            source=codebuild.Source.s3(
                bucket=s3.Bucket.from_bucket_name(
                    self, 
                    f"SourceBucket-{self.env_name}", 
                    source_bucket_name
                ),
                path="document-insight-extraction.zip"
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.MEDIUM,
                privileged=True  # Required for Docker builds
            ),
            build_spec=codebuild.BuildSpec.from_object_to_yaml(build_spec_yml),
            timeout=Duration.minutes(30),
            artifacts=codebuild.Artifacts.s3(
                bucket=self.artifacts_bucket,
                include_build_id=True,
                package_zip=True,
                path="ui-builds"
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
                "ECR_REPOSITORY_URI": codebuild.BuildEnvironmentVariable(
                    value=self.ecr_repository.repository_uri
                ),
                # Import Cognito configuration from other stacks
                "USER_POOL_ID": codebuild.BuildEnvironmentVariable(
                    value=f"${{resolve:ssm:/{self.project_name}/{self.env_name}/cognito/user-pool-id}}"
                ),
                "USER_POOL_CLIENT_ID": codebuild.BuildEnvironmentVariable(
                    value=f"${{resolve:ssm:/{self.project_name}/{self.env_name}/cognito/user-pool-client-id}}"
                ),
                "REST_API_URL": codebuild.BuildEnvironmentVariable(
                    value=f"${{resolve:ssm:/{self.project_name}/{self.env_name}/api/rest-api-url}}"
                ),
                "WEBSOCKET_URL": codebuild.BuildEnvironmentVariable(
                    value=f"${{resolve:ssm:/{self.project_name}/{self.env_name}/api/websocket-url}}"
                )
            },
            cache=codebuild.Cache.local(
                codebuild.LocalCacheMode.CUSTOM,
                codebuild.LocalCacheMode.DOCKER_LAYER
            )
        )
        
        return project

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for the stack."""
        # ECR repository URI
        self.add_stack_output(
            "ECRRepositoryUri",
            value=self.ecr_repository.repository_uri,
            description="ECR repository URI for UI Docker images",
            export_name=f"{self.stack_name}-ECRRepositoryUri"
        )

        # ECR repository name
        self.add_stack_output(
            "ECRRepositoryName",
            value=self.ecr_repository.repository_name,
            description="ECR repository name",
            export_name=f"{self.stack_name}-ECRRepositoryName"
        )

        # CodeBuild project name
        self.add_stack_output(
            "UIBuildProjectName",
            value=self.ui_build_project.project_name,
            description="CodeBuild project name for UI builds",
            export_name=f"{self.stack_name}-UIBuildProjectName"
        )

        # Artifacts bucket name
        self.add_stack_output(
            "ArtifactsBucketName",
            value=self.artifacts_bucket.bucket_name,
            description="S3 bucket for UI build artifacts",
            export_name=f"{self.stack_name}-ArtifactsBucketName"
        )

        # Source bucket name (for uploading source code)
        source_bucket_name = f"codebuild-{self.env_name}-{self.region}-{self.account}-input-bucket"
        self.add_stack_output(
            "SourceBucketName",
            value=source_bucket_name,
            description="S3 bucket for CodeBuild source code",
            export_name=f"{self.stack_name}-SourceBucketName"
        )