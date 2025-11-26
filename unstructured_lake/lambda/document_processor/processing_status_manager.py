"""
Processing Status Manager

Manages document processing status in a dedicated DynamoDB table.
Uses userId as partition key and docId as sort key for efficient queries.
"""
import logging
import time
import boto3
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
from decimal import Decimal
logger = logging.getLogger(__name__)


class ProcessingStatusManager:
    """
    Manages document processing status in DynamoDB.
    
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
    
    def create_processing_record(
        self, 
        user_id: str, 
        doc_id: str, 
        total_pages: int, 
        filename: str
    ) -> None:
        """
        Create initial processing record when processing starts.
        
        Args:
            user_id: User identifier
            doc_id: Document identifier
            total_pages: Total number of pages in document
            filename: Original filename
        """
        try:
            timestamp = int(time.time())
            
            item = {
                'userId': user_id,
                'docId': doc_id,
                'expiresAt': timestamp + (7 * 24 * 60 * 60),  # 7 days TTL
                'status': 'in-progress',
                'filename': filename,
                'totalPages': total_pages,
                'currentPage': 0,
                'totalChunks': 0,
                'startTime': timestamp,
                'lastUpdated': timestamp,
                'errorCount': 0
            }
            
            self.table.put_item(Item=item)
            logger.info(f"Created processing record for user {user_id}, doc {doc_id}")
            
        except ClientError as e:
            logger.error(f"Error creating processing record: {str(e)}")
            raise
    
    def update_progress(
        self, 
        user_id: str, 
        doc_id: str, 
        current_page: int, 
        message: str = None
    ) -> None:
        """
        Update processing progress.
        
        Args:
            user_id: User identifier
            doc_id: Document identifier
            current_page: Current page being processed
            message: Optional progress message
        """
        try:
            timestamp = int(time.time())
            
            update_expression = "SET currentPage = :current_page, lastUpdated = :timestamp"
            expression_values = {
                ':current_page': current_page,
                ':timestamp': timestamp
            }
            
            if message:
                update_expression += ", progressMessage = :message"
                expression_values[':message'] = message
            
            self.table.update_item(
                Key={
                    'userId': user_id,
                    'docId': doc_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            logger.debug(f"Updated progress for doc {doc_id}: page {current_page}")
            
        except ClientError as e:
            logger.error(f"Error updating progress: {str(e)}")
    
    def mark_completed(
        self, 
        user_id: str, 
        doc_id: str, 
        total_chunks: int
    ) -> None:
        """
        Mark processing as completed.
        
        Args:
            user_id: User identifier
            doc_id: Document identifier
            total_chunks: Total number of chunks created
        """
        try:
            timestamp = int(time.time())
            
            self.table.update_item(
                Key={
                    'userId': user_id,
                    'docId': doc_id
                },
                UpdateExpression="""
                    SET #status = :status,
                        lastUpdated = :timestamp,
                        completedAt = :timestamp,
                        totalChunks = :total_chunks
                """,
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': 'completed',
                    ':timestamp': timestamp,
                    ':total_chunks': total_chunks
                }
            )
            
            logger.info(f"Marked processing completed for doc {doc_id}")
            
        except ClientError as e:
            logger.error(f"Error marking completed: {str(e)}")
    
    def mark_failed(
        self, 
        user_id: str, 
        doc_id: str, 
        error_message: str
    ) -> None:
        """
        Mark processing as failed.
        
        Args:
            user_id: User identifier
            doc_id: Document identifier
            error_message: Error description
        """
        try:
            timestamp = int(time.time())
            
            self.table.update_item(
                Key={
                    'userId': user_id,
                    'docId': doc_id
                },
                UpdateExpression="""
                    SET #status = :status,
                        lastUpdated = :timestamp,
                        failedAt = :timestamp,
                        errorMessage = :error_message
                """,
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': 'failed',
                    ':timestamp': timestamp,
                    ':error_message': error_message
                }
            )
            
            logger.info(f"Marked processing failed for doc {doc_id}")
            
        except ClientError as e:
            logger.error(f"Error marking failed: {str(e)}")
    
    def add_error(
        self, 
        user_id: str, 
        doc_id: str, 
        page_num: int, 
        error_message: str
    ) -> None:
        """
        Add an error to the processing record.
        
        Stores errors as a flat string list for simplicity.
        Format: "Page {page_num}: {error_message}"
        
        Args:
            user_id: User identifier
            doc_id: Document identifier
            page_num: Page number where error occurred
            error_message: Error description
        """
        try:
            timestamp = int(time.time())
            error_entry = f"Page {page_num}: {error_message}"
            
            self.table.update_item(
                Key={
                    'userId': user_id,
                    'docId': doc_id
                },
                UpdateExpression="""
                    SET errors = list_append(if_not_exists(errors, :empty_list), :error),
                        lastUpdated = :timestamp,
                        errorCount = if_not_exists(errorCount, :zero) + :one
                """,
                ExpressionAttributeValues={
                    ':error': [error_entry],
                    ':empty_list': [],
                    ':timestamp': timestamp,
                    ':zero': 0,
                    ':one': 1
                }
            )
            
            logger.info(f"Added error for doc {doc_id}, page {page_num}")
            
        except ClientError as e:
            logger.error(f"Error adding error to record: {str(e)}")
    
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
    
    def get_user_processing_statuses(
        self, 
        user_id: str, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all processing statuses for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of records to return
            
        Returns:
            List of processing status dictionaries
        """
        try:
            response = self.table.query(
                KeyConditionExpression='userId = :user_id',
                ExpressionAttributeValues={
                    ':user_id': user_id
                },
                Limit=limit
            )
            
            return [dict(item) for item in response.get('Items', [])]
            
        except ClientError as e:
            logger.error(f"Error getting user processing statuses: {str(e)}")
            return []
    
    def cleanup_old_records(
        self, 
        user_id: str, 
        doc_id: str
    ) -> None:
        """
        Clean up processing record (called when document is deleted).
        
        Args:
            user_id: User identifier
            doc_id: Document identifier
        """
        try:
            self.table.delete_item(
                Key={
                    'userId': user_id,
                    'docId': doc_id
                }
            )
            
            logger.info(f"Cleaned up processing record for doc {doc_id}")
            
        except ClientError as e:
            logger.error(f"Error cleaning up processing record: {str(e)}")
