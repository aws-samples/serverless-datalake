"""
S3 Bucket Stack for Document Insight Extraction System

This module defines S3 buckets for document storage and vector embeddings,
including CORS configuration, event notifications, and vector search capabilities.
"""
from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    CfnOutput,
    RemovalPolicy,
    Duration,
)
from aws_cdk import aws_s3vectors as s3vectors
from constructs import Construct
from infrastructure.base_stack import BaseDocumentInsightStack



class S3BucketStack(BaseDocumentInsightStack):
    """
    Stack for S3 bucket resources.
    
    Creates:
    - S3 bucket for document storage with CORS configuration
    - S3 Vector bucket for embeddings with metadata filtering
    Note: Event notifications are configured in the Lambda Function stack
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
        Initialize the S3 bucket stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        # Create document storage bucket
        self.documents_bucket = self._create_documents_bucket()
        
        # Create vector storage bucket and index
        self.vector_bucket, self.vector_index = self._create_vector_bucket_and_index()
        

        
        # Export properties for other stacks
        self.vector_index_arn = self.vector_index.attr_index_arn
        
        # Export outputs
        self._create_outputs()

    def _create_documents_bucket(self) -> s3.Bucket:
        """
        Create S3 bucket for document storage with CORS configuration.
        
        Returns:
            S3 Bucket construct
        """
        # CORS configuration for presigned POST uploads
        cors_rule = s3.CorsRule(
            allowed_methods=[
                s3.HttpMethods.GET,
                s3.HttpMethods.POST,
                s3.HttpMethods.PUT,
                s3.HttpMethods.HEAD
            ],
            allowed_origins=["*"],  # Will be restricted to AppRunner URL in production
            allowed_headers=["*"],
            exposed_headers=[
                "ETag",
                "x-amz-server-side-encryption",
                "x-amz-request-id",
                "x-amz-id-2"
            ],
            max_age=3000
        )

        # Create bucket with configuration
        bucket = s3.Bucket(
            self,
            "DocumentsBucket",
            bucket_name=self.documents_bucket_name,
            # Versioning disabled for cost optimization
            versioned=False,
            # Encryption at rest
            encryption=s3.BucketEncryption.S3_MANAGED,
            # Block public access
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            # CORS configuration
            cors=[cors_rule],
            # Removal policy based on environment
            removal_policy=self.removal_policy,
            auto_delete_objects=self.removal_policy == RemovalPolicy.DESTROY,
            # Lifecycle rules for cost optimization
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="CleanupIncompleteUploads",
                    enabled=True,
                    # Clean up incomplete multipart uploads after 7 days
                    abort_incomplete_multipart_upload_after=Duration.days(7)
                )
            ],
            # Enable server access logging (optional)
            server_access_logs_prefix="access-logs/",
            # Enforce SSL
            enforce_ssl=True
        )

        return bucket

    def _create_vector_bucket_and_index(self) -> tuple[s3vectors.CfnVectorBucket, s3vectors.CfnIndex]:
        """
        Create S3 Vector bucket and index for embeddings with metadata filtering.
        
        Uses the aws-s3vectors L1 CloudFormation constructs to create a vector search 
        bucket with index configuration for semantic search capabilities.
        
        Returns:
            Tuple of (CfnVectorBucket, CfnIndex) constructs
        """
        # Get vector dimensions from config
        vector_dimensions = self.config.get("vector_dimensions", 512)
        
        # Create vector bucket using L1 CloudFormation construct
        vector_bucket = s3vectors.CfnVectorBucket(
            self,
            "VectorBucket",
            vector_bucket_name=self.vector_bucket_name,
            # Encryption configuration (optional) - uses AES256 by default
            encryption_configuration=s3vectors.CfnVectorBucket.EncryptionConfigurationProperty(
                sse_type="AES256"  # Amazon S3 managed keys (default)
            )
        )
        
        # Apply removal policy
        vector_bucket.apply_removal_policy(self.removal_policy)
        
        # Create vector index for semantic search
        vector_index = s3vectors.CfnIndex(
            self,
            "VectorIndex",
            vector_bucket_name=self.vector_bucket_name,
            index_name="docs",
            # Vector configuration
            dimension=vector_dimensions,
            data_type="float32",
            # Cosine similarity for semantic search (best for text embeddings)
            distance_metric="cosine",
            # Metadata configuration for filtering
            # Note: All metadata keys are filterable by default except those specified as non-filterable
            metadata_configuration=s3vectors.CfnIndex.MetadataConfigurationProperty(
                non_filterable_metadata_keys=[
                    "textChunk",       # Original text content (large, not for filtering)
                    "fileName",        # Original file name (for display only)
                    "processingDate"   # When chunk was processed (for display only)
                ]
                # Filterable keys (default): docId, pageRange, uploadTimestamp, chunkIndex
            )
        )
        
        # Ensure vector index waits for vector bucket to be created
        vector_index.add_dependency(vector_bucket)
        
        # Apply removal policy
        vector_index.apply_removal_policy(self.removal_policy)
        
        return vector_bucket, vector_index



    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for bucket names and ARNs."""
        # Documents bucket outputs
        self.add_stack_output(
            "DocumentsBucketName",
            value=self.documents_bucket.bucket_name,
            description="S3 bucket name for document storage",
            export_name=f"{self.stack_name}-DocumentsBucketName"
        )
        
        self.add_stack_output(
            "DocumentsBucketArn",
            value=self.documents_bucket.bucket_arn,
            description="S3 bucket ARN for document storage",
            export_name=f"{self.stack_name}-DocumentsBucketArn"
        )
        
        # Vector bucket outputs
        self.add_stack_output(
            "VectorBucketName",
            value=self.vector_bucket.ref,
            description="S3 Vector bucket name for embeddings",
            export_name=f"{self.stack_name}-VectorBucketName"
        )
        
        self.add_stack_output(
            "VectorBucketArn",
            value=self.vector_bucket.attr_vector_bucket_arn,
            description="S3 Vector bucket ARN for embeddings",
            export_name=f"{self.stack_name}-VectorBucketArn"
        )
        
        # Vector index outputs
        self.add_stack_output(
            "VectorIndexArn",
            value=self.vector_index.attr_index_arn,
            description="S3 Vector index ARN for queries",
            export_name=f"{self.stack_name}-VectorIndexArn"
        )
        
        self.add_stack_output(
            "VectorIndexName",
            value=self.vector_index.ref,
            description="S3 Vector index name",
            export_name=f"{self.stack_name}-VectorIndexName"
        )
