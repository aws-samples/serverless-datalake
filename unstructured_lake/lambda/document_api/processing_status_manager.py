"""
Processing Status Manager for Document API

Manages document processing status queries from DynamoDB.
This is a separate implementation for the document API Lambda.
"""
import logging
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ProcessingStatusManager:
    """
    Manages document processing status queries in DynamoDB.
    
    Table schema:
    - Partition Key: userId (String)
    - Sort Key: docId (String)
    - Flat JSON structure (no nested objects)
    """
    
    def __init__(self, region: str, table_name: str):
        """
        Initialize the processing status manager.
        
        Args:
            region: AWS region
            table_name: DynamoDB table name
        """
        self.region = region
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
    
    def get_processing_status(
        self, 
        user_id: str, 
        doc_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get current processing status for a document.
        
        Args:
            user_id: User identifier
            doc_id: Document identifier
            
        Returns:
            Processing status dictionary or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'userId': user_id,
                    'docId': doc_id
                }
            )
            
            if 'Item' in response:
                return dict(response['Item'])
            
            return None
            
        except ClientError as e:
            logger.error(f"Error getting processing status: {str(e)}")
            return None
