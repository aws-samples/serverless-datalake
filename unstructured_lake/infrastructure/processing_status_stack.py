"""
Processing Status DynamoDB Stack

This module defines a separate DynamoDB table for tracking document processing status.
Separate from the insights cache table for cleaner data organization.
"""
from aws_cdk import (
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct
from infrastructure.base_stack import BaseDocumentInsightStack


class ProcessingStatusStack(BaseDocumentInsightStack):
    """
    Stack for document processing status tracking.
    
    Creates a DynamoDB table with:
    - Partition Key: userId (String) - User identifier
    - Sort Key: docId (String) - Document identifier
    - Flat JSON structure for easy querying
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
        Initialize the processing status stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        # Create processing status table
        self.processing_status_table = self._create_processing_status_table()
        
        # Configure auto-scaling if needed
        self._configure_auto_scaling()
        
        # Export outputs
        self._create_outputs()

    def _create_processing_status_table(self) -> dynamodb.Table:
        """
        Create DynamoDB table for document processing status.
        
        Table schema:
        - Partition Key: userId (String) - User identifier
        - Sort Key: docId (String) - Document identifier
        - TTL Attribute: expiresAt - Automatic deletion after 7 days
        
        Flat JSON structure with attributes:
        - status: 'in-progress' | 'completed' | 'failed'
        - filename: Original filename
        - totalPages: Total number of pages
        - currentPage: Current page being processed
        - totalChunks: Total chunks created
        - startTime: Unix timestamp when processing started
        - lastUpdated: Unix timestamp of last update
        - completedAt: Unix timestamp when completed (if applicable)
        - failedAt: Unix timestamp when failed (if applicable)
        - errorMessage: Error message (if failed)
        - errors: List of page-level errors [{page, message, timestamp}]
        
        Returns:
            DynamoDB Table construct
        """
        # Get billing mode from config (default to PAY_PER_REQUEST)
        use_provisioned = self.config.get("dynamodb_use_provisioned", False)
        
        # Table name
        table_name = f"{self.project_name}-processing-status-{self.env_name}"
        
        # Base table configuration
        table_config = {
            "table_name": table_name,
            # Partition key: user identifier
            "partition_key": dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            # Sort key: document identifier
            "sort_key": dynamodb.Attribute(
                name="docId",
                type=dynamodb.AttributeType.STRING
            ),
            # TTL attribute for automatic expiration (7 days)
            "time_to_live_attribute": "expiresAt",
            # Point-in-time recovery for data protection
            "point_in_time_recovery": True,
            # Removal policy based on environment
            "removal_policy": self.removal_policy,
            # Encryption at rest with AWS managed keys
            "encryption": dynamodb.TableEncryption.AWS_MANAGED,
        }
        
        # Add billing mode configuration
        if use_provisioned:
            # Provisioned billing with auto-scaling
            table_config["billing_mode"] = dynamodb.BillingMode.PROVISIONED
            table_config["read_capacity"] = 5
            table_config["write_capacity"] = 5
        else:
            # Pay-per-request billing for unpredictable workloads
            table_config["billing_mode"] = dynamodb.BillingMode.PAY_PER_REQUEST
        
        table = dynamodb.Table(
            self,
            "ProcessingStatusTable",
            **table_config
        )

        return table

    def _configure_auto_scaling(self) -> None:
        """
        Configure auto-scaling policies for read and write capacity.
        
        Only applicable when using PROVISIONED billing mode.
        """
        use_provisioned = self.config.get("dynamodb_use_provisioned", False)
        
        if use_provisioned:
            # Configure read capacity auto-scaling
            read_scaling = self.processing_status_table.auto_scale_read_capacity(
                min_capacity=5,
                max_capacity=50
            )
            read_scaling.scale_on_utilization(
                target_utilization_percent=75
            )
            
            # Configure write capacity auto-scaling
            write_scaling = self.processing_status_table.auto_scale_write_capacity(
                min_capacity=5,
                max_capacity=50
            )
            write_scaling.scale_on_utilization(
                target_utilization_percent=75
            )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for table name and ARN."""
        self.add_stack_output(
            "ProcessingStatusTableName",
            value=self.processing_status_table.table_name,
            description="DynamoDB table name for processing status",
            export_name=f"{self.stack_name}-ProcessingStatusTableName"
        )
        
        self.add_stack_output(
            "ProcessingStatusTableArn",
            value=self.processing_status_table.table_arn,
            description="DynamoDB table ARN for processing status",
            export_name=f"{self.stack_name}-ProcessingStatusTableArn"
        )
