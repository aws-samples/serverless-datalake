"""
Base Stack for Document Insight Extraction System

This module defines the base stack class with common tags, naming conventions,
and configuration management for all infrastructure components.
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
)
from constructs import Construct
from typing import Dict, Any


class BaseDocumentInsightStack(Stack):
    """
    Base stack class for Document Insight Extraction System.
    
    Provides common functionality including:
    - Standardized naming conventions
    - Common tags and metadata
    - Configuration management
    - Resource naming helpers
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
        Initialize the base stack.
        
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
        
        # Store common configuration
        self._setup_common_config()

    def _setup_common_config(self) -> None:
        """Set up common configuration values used across the stack."""
        self.documents_bucket_name = f'{self.config.get("s3_documents_bucket")}-{self.account}'
        self.vector_bucket_name = f'{self.config.get("s3_vector_bucket")}-{self.account}'
        
        # DynamoDB configuration
        self.cache_table_name = self.config.get("dynamodb_cache_table")
        # Lambda configuration
        self.lambda_memory = self.config.get("lambda_memory", 3008)
        self.lambda_timeout = self.config.get("lambda_timeout", 600)
        
        # Bedrock model configuration
        self.embed_model_id = self.config.get(
            "embed_model_id",
            "amazon.titan-embed-text-v2:0"
        )
        self.insight_model_id = self.config.get(
            "insight_model_id",
            "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        
        # Removal policy based on environment
        self.removal_policy = (
            RemovalPolicy.DESTROY if self.env_name == "dev" 
            else RemovalPolicy.RETAIN
        )

    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """
        Generate a standardized resource name.
        
        Args:
            resource_type: Type of resource (e.g., 'lambda', 's3', 'dynamodb')
            suffix: Optional suffix to append to the name
            
        Returns:
            Formatted resource name following naming convention
        """
        base_name = f"{self.project_name}-{resource_type}-{self.env_name}"
        if suffix:
            return f"{base_name}-{suffix}"
        return base_name

    def add_stack_output(
        self,
        output_id: str,
        value: str,
        description: str = "",
        export_name: str = None
    ) -> CfnOutput:
        """
        Add a CloudFormation output with standardized naming.
        
        Args:
            output_id: Unique identifier for the output
            value: Output value
            description: Human-readable description
            export_name: Optional export name for cross-stack references
            
        Returns:
            CfnOutput construct
        """
        if not export_name:
            export_name = f"{self.stack_name}-{output_id}"
            
        return CfnOutput(
            self,
            output_id,
            value=value,
            description=description,
            export_name=export_name
        )

    def get_common_tags(self) -> Dict[str, str]:
        """
        Get common tags to apply to resources.
        
        Returns:
            Dictionary of tag key-value pairs
        """
        return {
            "Project": "DocumentInsightExtraction",
            "Environment": self.env_name,
            "ManagedBy": "CDK",
            "Application": "DocumentProcessing"
        }
