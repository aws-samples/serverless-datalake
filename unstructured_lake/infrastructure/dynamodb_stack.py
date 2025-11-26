"""
DynamoDB Stack for Document Insight Extraction System

This module defines the DynamoDB table for caching extracted insights
with TTL-based automatic expiration and auto-scaling configuration.

Billing Modes:
- PAY_PER_REQUEST (default): Automatically scales, no capacity planning needed
- PROVISIONED: Manual capacity with auto-scaling (5-50 units at 75% utilization)

To enable provisioned mode with auto-scaling, set 'dynamodb_use_provisioned': true
in cdk.json configuration.
"""
from aws_cdk import (
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct
from infrastructure.base_stack import BaseDocumentInsightStack


class DynamoDBStack(BaseDocumentInsightStack):
    """
    Stack for DynamoDB resources.
    
    Creates:
    - Insights cache table with TTL
    - Auto-scaling policies for read/write capacity
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
        Initialize the DynamoDB stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        # Create insights cache table
        self.insights_cache_table = self._create_insights_cache_table()
        
        # Configure auto-scaling policies
        self._configure_auto_scaling()
        
        # Export outputs
        self._create_outputs()

    def _create_insights_cache_table(self) -> dynamodb.Table:
        """
        Create DynamoDB table for insights cache with TTL.
        
        Table schema:
        - Partition Key: docId (String) - Document identifier
        - Sort Key: extractionTimestamp (Number) - Unix timestamp
        - TTL Attribute: expiresAt - Automatic deletion after 24 hours
        
        Returns:
            DynamoDB Table construct
        """
        # Get billing mode from config (default to PAY_PER_REQUEST)
        use_provisioned = self.config.get("dynamodb_use_provisioned", False)
        
        # Base table configuration
        table_config = {
            "table_name": self.cache_table_name,
            # Partition key: document identifier
            "partition_key": dynamodb.Attribute(
                name="docId",
                type=dynamodb.AttributeType.STRING
            ),
            # Sort key: extraction timestamp for versioning
            "sort_key": dynamodb.Attribute(
                name="extractionTimestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            # TTL attribute for automatic expiration
            "time_to_live_attribute": "expiresAt",
            # Point-in-time recovery for data protection
            "point_in_time_recovery": True,
            # Removal policy based on environment
            "removal_policy": self.removal_policy,
            # Encryption at rest with AWS managed keys
            "encryption": dynamodb.TableEncryption.AWS_MANAGED,
            # Stream specification for change data capture (optional)
            "stream": dynamodb.StreamViewType.NEW_AND_OLD_IMAGES if self.env_name == "prod" else None,
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
            "InsightsCacheTable",
            **table_config
        )

        return table

    def _configure_auto_scaling(self) -> None:
        """
        Configure auto-scaling policies for read and write capacity.
        
        Auto-scaling is only applicable when using PROVISIONED billing mode.
        
        For PROVISIONED mode:
        - Read capacity: 5-50 units, scales at 75% utilization
        - Write capacity: 5-50 units, scales at 75% utilization
        
        For PAY_PER_REQUEST mode:
        - Read capacity: Automatically scales to handle up to 40,000 RCUs
        - Write capacity: Automatically scales to handle up to 40,000 WCUs
        - No manual configuration needed
        """
        # Check if using provisioned billing mode
        use_provisioned = self.config.get("dynamodb_use_provisioned", False)
        
        if use_provisioned:
            # Configure read capacity auto-scaling
            read_scaling = self.insights_cache_table.auto_scale_read_capacity(
                min_capacity=5,
                max_capacity=50
            )
            read_scaling.scale_on_utilization(
                target_utilization_percent=75
            )
            
            # Configure write capacity auto-scaling
            write_scaling = self.insights_cache_table.auto_scale_write_capacity(
                min_capacity=5,
                max_capacity=50
            )
            write_scaling.scale_on_utilization(
                target_utilization_percent=75
            )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for table name and ARN."""
        self.add_stack_output(
            "InsightsCacheTableName",
            value=self.insights_cache_table.table_name,
            description="DynamoDB table name for insights cache",
            export_name=f"{self.stack_name}-InsightsCacheTableName"
        )
        
        self.add_stack_output(
            "InsightsCacheTableArn",
            value=self.insights_cache_table.table_arn,
            description="DynamoDB table ARN for insights cache",
            export_name=f"{self.stack_name}-InsightsCacheTableArn"
        )
        
        self.add_stack_output(
            "InsightsCacheTableStreamArn",
            value=self.insights_cache_table.table_stream_arn or "N/A",
            description="DynamoDB table stream ARN (if enabled)",
            export_name=f"{self.stack_name}-InsightsCacheTableStreamArn"
        )

