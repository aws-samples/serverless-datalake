"""
CloudFront + S3 Hosting Stack for Document Insight Extraction System

This module defines the CloudFront distribution and S3 bucket infrastructure
for hosting the React frontend as a static site.
"""
from aws_cdk import (
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_codebuild as codebuild,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from .base_stack import BaseDocumentInsightStack
from typing import Dict, Any


class CloudFrontHostingStack(BaseDocumentInsightStack):
    """
    Stack for CloudFront + S3 static hosting infrastructure.

    Creates:
    - S3 bucket for static website assets (private, OAC access only)
    - CloudFront distribution with SPA routing and security headers
    - CodeBuild project for building React app and deploying to S3
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
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        self.api_endpoint = api_endpoint
        self.wss_endpoint = wss_endpoint
        self.user_pool_id = user_pool_id
        self.user_pool_client_id = user_pool_client_id

        # Create S3 bucket for static assets
        self.ui_bucket = self._create_ui_bucket()

        # Create CloudFront distribution
        self.distribution = self._create_distribution()

        # Create CodeBuild project for UI build and deploy
        self.ui_build_project = self._create_ui_build_project()

        # Export outputs
        self._create_outputs()

    def _create_ui_bucket(self) -> s3.Bucket:
        ui_bucket_name = f'{self.config.get("s3_ui_bucket")}-{self.account}'

        return s3.Bucket(
            self,
            "UIBucket",
            bucket_name=ui_bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=self.removal_policy,
            auto_delete_objects=(self.env_name == "dev"),
        )

    def _create_distribution(self) -> cloudfront.Distribution:
        # Security headers response policy
        response_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeaders",
            response_headers_policy_name=self.get_resource_name("security-headers"),
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.SAMEORIGIN,
                    override=True,
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(
                    override=True,
                ),
                xss_protection=cloudfront.ResponseHeadersXSSProtection(
                    protection=True,
                    mode_block=True,
                    override=True,
                ),
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365),
                    include_subdomains=True,
                    override=True,
                ),
            ),
        )

        distribution = cloudfront.Distribution(
            self,
            "UIDistribution",
            comment="S3Vectors Datalake",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.ui_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=response_headers_policy,
                compress=True,
            ),
            default_root_object="index.html",
            error_responses=[
                # SPA routing: return index.html for 403/404
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )

        return distribution

    def _create_ui_build_project(self) -> codebuild.Project:
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
            ],
        )

        # Grant S3 write to UI bucket
        self.ui_bucket.grant_read_write(codebuild_role)

        # Grant CloudFront invalidation
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudfront:CreateInvalidation"],
                resources=[
                    f"arn:aws:cloudfront::{self.account}:distribution/{self.distribution.distribution_id}"
                ],
            )
        )

        # Grant CloudWatch Logs permissions
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/codebuild/*"
                ],
            )
        )

        # Grant SSM Parameter Store read permissions
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.project_name}/{self.env_name}/*"
                ],
            )
        )

        # Read buildspec
        import yaml
        import os

        buildspec_path = os.path.join(
            os.path.dirname(__file__), "..", "buildspecs", "buildspec_deploy_ui.yml"
        )
        with open(buildspec_path, "r") as stream:
            build_spec_yml = yaml.safe_load(stream)

        # Create S3 source bucket name
        source_bucket_name = f"codebuild-{self.env_name}-{self.region}-{self.account}-document-insight-input"

        # Create artifacts bucket for build logs
        artifacts_bucket = s3.Bucket(
            self,
            "UIBuildArtifactsBucket",
            bucket_name=f"di-ui-artifacts-{self.env_name}-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=self.removal_policy,
            auto_delete_objects=(self.env_name == "dev"),
        )
        artifacts_bucket.grant_read_write(codebuild_role)

        project = codebuild.Project(
            self,
            "UIBuildProject",
            project_name=f"{self.project_name}-ui-builder-{self.env_name}",
            description="Build React UI and deploy to S3 + CloudFront",
            role=codebuild_role,
            source=codebuild.Source.s3(
                bucket=s3.Bucket.from_bucket_name(
                    self,
                    f"SourceBucket-{self.env_name}",
                    source_bucket_name,
                ),
                path="document-insight-extraction.zip",
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.MEDIUM,
            ),
            build_spec=codebuild.BuildSpec.from_object_to_yaml(build_spec_yml),
            timeout=Duration.minutes(15),
            artifacts=codebuild.Artifacts.s3(
                bucket=artifacts_bucket,
                include_build_id=True,
                package_zip=True,
                path="ui-builds",
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
                "UI_BUCKET_NAME": codebuild.BuildEnvironmentVariable(
                    value=self.ui_bucket.bucket_name
                ),
                "DISTRIBUTION_ID": codebuild.BuildEnvironmentVariable(
                    value=self.distribution.distribution_id
                ),
                "USER_POOL_ID": codebuild.BuildEnvironmentVariable(
                    value=f"/{self.project_name}/{self.env_name}/cognito/user-pool-id",
                    type=codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
                ),
                "USER_POOL_CLIENT_ID": codebuild.BuildEnvironmentVariable(
                    value=f"/{self.project_name}/{self.env_name}/cognito/user-pool-client-id",
                    type=codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
                ),
                "REST_API_URL": codebuild.BuildEnvironmentVariable(
                    value=f"/{self.project_name}/{self.env_name}/api/rest-api-url",
                    type=codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
                ),
                "WEBSOCKET_URL": codebuild.BuildEnvironmentVariable(
                    value=f"/{self.project_name}/{self.env_name}/api/websocket-url",
                    type=codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
                ),
            },
            cache=codebuild.Cache.local(codebuild.LocalCacheMode.CUSTOM),
        )

        return project

    def _create_outputs(self) -> None:
        self.add_stack_output(
            "CloudFrontDistributionUrl",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="CloudFront distribution URL for the frontend application",
            export_name=f"{self.stack_name}-CloudFrontDistributionUrl",
        )

        self.add_stack_output(
            "CloudFrontDistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID",
            export_name=f"{self.stack_name}-CloudFrontDistributionId",
        )

        self.add_stack_output(
            "UIBucketName",
            value=self.ui_bucket.bucket_name,
            description="S3 bucket name for UI static assets",
            export_name=f"{self.stack_name}-UIBucketName",
        )

        self.add_stack_output(
            "UIBuildProjectName",
            value=self.ui_build_project.project_name,
            description="CodeBuild project name for UI builds",
            export_name=f"{self.stack_name}-UIBuildProjectName",
        )
