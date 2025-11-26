"""
WebSocket Notification Module

This module provides functionality to send real-time progress updates
to connected WebSocket clients via API Gateway.
"""
import logging
import json
import boto3
from typing import Dict, Any
from urllib.parse import urlparse
from decimal import Decimal
logger = logging.getLogger(__name__)

class CustomJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if float(obj).is_integer():
                return int(float(obj))
            else:
                return float(obj)
        return super(CustomJsonEncoder, self).default(obj)

class WebSocketNotifier:
    """Send progress updates via WebSocket API Gateway."""
    
    def __init__(self, websocket_url: str, region: str):
        """
        Initialize WebSocket notifier.
        
        Args:
            websocket_url: WebSocket API URL (wss://...)
            region: AWS region
        """
        self.logger = logging.getLogger(__name__)
        self.websocket_url = websocket_url
        self.region = region
        
        # Parse WebSocket URL to get API Gateway endpoint
        # Format: wss://{api-id}.execute-api.{region}.amazonaws.com/{stage}
        parsed = urlparse(websocket_url)
        self.api_endpoint = parsed.netloc
        self.stage = parsed.path.strip('/')
        
        # Extract API ID from endpoint
        self.api_id = self.api_endpoint.split('.')[0]
        
        # Create API Gateway Management API client
        # This is used to post messages to WebSocket connections
        self.apigw_management = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=f"https://{self.api_endpoint}/{self.stage}",
            region_name=region
        )
        
        print(f"WebSocket notifier initialized for API: {self.api_id}")
    
    def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a WebSocket connection.
        
        Args:
            connection_id: WebSocket connection ID
            message: Message dictionary to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert message to JSON
            message_json = json.dumps(message, cls=CustomJsonEncoder)
            
            # Post to connection
            self.apigw_management.post_to_connection(
                ConnectionId=connection_id,
                Data=message_json.encode('utf-8')
            )
            
            self.logger.debug(
                f"Sent message to connection {connection_id}: {message.get('status', 'unknown')}"
            )
            return True
            
        except self.apigw_management.exceptions.GoneException:
            self.logger.warning(f"Connection {connection_id} is gone")
            return False
        except Exception as e:
            self.logger.error(
                f"Error sending message to connection {connection_id}: {str(e)}"
            )
            return False
    
    def send_processing_started(
        self,
        connection_id: str,
        doc_id: str,
        total_pages: int
    ) -> bool:
        """
        Send processing started notification.
        
        Args:
            connection_id: WebSocket connection ID
            doc_id: Document identifier
            total_pages: Total number of pages in document
            
        Returns:
            True if successful, False otherwise
        """
        message = {
            "status": "processing_started",
            "docId": doc_id,
            "totalPages": total_pages,
            "timestamp": self._get_timestamp()
        }
        
        return self.send_message(connection_id, message)
    
    def send_progress(
        self,
        connection_id: str,
        doc_id: str,
        pages_processed: int,
        total_pages: int,
        message_text: str = None
    ) -> bool:
        """
        Send progress update notification.
        
        Args:
            connection_id: WebSocket connection ID
            doc_id: Document identifier
            pages_processed: Number of pages processed so far
            total_pages: Total number of pages
            message_text: Optional progress message
            
        Returns:
            True if successful, False otherwise
        """
        message = {
            "status": "progress",
            "docId": doc_id,
            "pagesProcessed": pages_processed,
            "totalPages": total_pages,
            "percentComplete": round((pages_processed / total_pages) * 100, 1),
            "timestamp": self._get_timestamp()
        }
        
        if message_text:
            message["message"] = message_text
        
        return self.send_message(connection_id, message)
    
    def send_processing_complete(
        self,
        connection_id: str,
        doc_id: str,
        total_chunks: int = None
    ) -> bool:
        """
        Send processing complete notification.
        
        Args:
            connection_id: WebSocket connection ID
            doc_id: Document identifier
            total_chunks: Optional total number of chunks created
            
        Returns:
            True if successful, False otherwise
        """
        message = {
            "status": "processing_complete",
            "docId": doc_id,
            "timestamp": self._get_timestamp()
        }
        
        if total_chunks is not None:
            message["totalChunks"] = total_chunks
        
        return self.send_message(connection_id, message)
    
    def send_error(
        self,
        connection_id: str,
        doc_id: str,
        error_code: str,
        error_message: str,
        recoverable: bool = False
    ) -> bool:
        """
        Send error notification.
        
        Args:
            connection_id: WebSocket connection ID
            doc_id: Document identifier
            error_code: Error code (e.g., "PROCESSING_FAILED")
            error_message: Human-readable error message
            recoverable: Whether the error is recoverable
            
        Returns:
            True if successful, False otherwise
        """
        message = {
            "status": "error",
            "docId": doc_id,
            "errorCode": error_code,
            "message": error_message,
            "recoverable": recoverable,
            "timestamp": self._get_timestamp()
        }
        
        return self.send_message(connection_id, message)
    
    def _get_timestamp(self) -> int:
        """
        Get current Unix timestamp.
        
        Returns:
            Unix timestamp in seconds
        """
        import time
        return int(time.time())
    
    def get_connection_id_from_event(self, event: Dict[str, Any]) -> str:
        """
        Extract connection ID from S3 event or Lambda context.
        
        Note: In practice, the connection ID should be stored in DynamoDB
        or passed through S3 object metadata when the upload is initiated.
        
        Args:
            event: Lambda event
            
        Returns:
            Connection ID or None if not found
        """
        # Try to get from S3 object metadata
        try:
            if 'Records' in event:
                for record in event['Records']:
                    if 's3' in record:
                        # Get object metadata
                        bucket = record['s3']['bucket']['name']
                        key = record['s3']['object']['key']
                        
                        # Retrieve object metadata
                        s3_client = boto3.client('s3', region_name=self.region)
                        response = s3_client.head_object(Bucket=bucket, Key=key)
                        
                        # Check for connection ID in metadata
                        metadata = response.get('Metadata', {})
                        connection_id = metadata.get('connection-id')
                        
                        if connection_id:
                            print(f"Found connection ID: {connection_id}")
                            return connection_id
        except Exception as e:
            self.logger.warning(f"Error extracting connection ID: {str(e)}")
        
        return None
