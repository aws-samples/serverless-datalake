"""
WebSocket Connection Manager

Manages WebSocket connections in DynamoDB, mapping user IDs to connection IDs.
"""
import logging
import time
import boto3
import json
import base64
from typing import Optional
from botocore.exceptions import ClientError
from decimal import Decimal
logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Manages WebSocket connections in DynamoDB.
    
    Table schema (reusing processing status table):
    - Partition Key: userId (String) - constant "websocket_connections"
    - Sort Key: docId (String) - actual userId
    - Attributes: connectionIds (List) - up to 3 connection IDs
    
    This allows multiple simultaneous connections per user (e.g., multiple browser tabs).
    """
    
    def __init__(self, region: str, table_name: str, max_connections: int = 3):
        """
        Initialize the connection manager.
        
        Args:
            region: AWS region
            table_name: DynamoDB table name (processing status table)
            max_connections: Maximum connections per user (default 3)
        """
        self.region = region
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        
        # Constant partition key for all WebSocket connection records
        self.partition_key = 'websocket_connections'
        
        # Maximum number of simultaneous connections per user
        self.max_connections = max_connections
    
    def decode_jwt_token(self, token: str) -> Optional[dict]:
        """
        Decode JWT token to extract user information.
        
        Args:
            token: JWT token string (with or without 'Bearer ' prefix)
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            # JWT tokens have 3 parts separated by dots
            parts = token.split('.')
            if len(parts) != 3:
                logger.error("Invalid JWT token format")
                return None
            
            # Decode the payload (second part)
            # Add padding if needed
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            decoded_bytes = base64.urlsafe_b64decode(payload)
            decoded_payload = json.loads(decoded_bytes)
            
            return decoded_payload
            
        except Exception as e:
            logger.error(f"Error decoding JWT token: {str(e)}")
            return None
    
    def store_connection(
        self, 
        user_id: str, 
        connection_id: str,
        ttl_hours: int = 24
    ) -> bool:
        """
        Store WebSocket connection for a user.
        Supports up to max_connections simultaneous connections per user.
        
        Args:
            user_id: User identifier
            connection_id: WebSocket connection ID
            ttl_hours: Time to live in hours (default 24)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = int(time.time())
            
            # Try to get existing record
            response = self.table.get_item(
                Key={
                    'userId': self.partition_key,
                    'docId': user_id
                }
            )
            
            if 'Item' in response:
                # Update existing record - add new connection to list
                existing_connections = response['Item'].get('connectionIds', [])
                
                # Remove the new connection if it already exists (reconnection)
                existing_connections = [c for c in existing_connections if c != connection_id]
                
                # Add new connection at the beginning
                existing_connections.insert(0, connection_id)
                
                # Keep only the most recent max_connections
                existing_connections = existing_connections[:self.max_connections]
                
                self.table.update_item(
                    Key={
                        'userId': self.partition_key,
                        'docId': user_id
                    },
                    UpdateExpression="SET connectionIds = :connections, lastUpdated = :timestamp, expiresAt = :expires",
                    ExpressionAttributeValues={
                        ':connections': existing_connections,
                        ':timestamp': timestamp,
                        ':expires': timestamp + (ttl_hours * 60 * 60)
                    }
                )
                logger.info(f"Updated connections for user {user_id}: {existing_connections}")
            else:
                # Create new record
                item = {
                    'userId': self.partition_key,
                    'docId': user_id,
                    'connectionIds': [connection_id],
                    'connectedAt': timestamp,
                    'lastUpdated': timestamp,
                    'expiresAt': timestamp + (ttl_hours * 60 * 60)
                }
                
                self.table.put_item(Item=item)
                logger.info(f"Created new connection record for user {user_id}: {connection_id}")
            
            return True
            
        except ClientError as e:
            logger.error(f"Error storing connection: {str(e)}")
            return False
    
    def get_connections(self, user_id: str) -> list:
        """
        Get all WebSocket connection IDs for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of connection IDs (empty list if none found)
        """
        try:
            response = self.table.get_item(
                Key={
                    'userId': self.partition_key,
                    'docId': user_id
                }
            )
            
            if 'Item' in response:
                connection_ids = response['Item'].get('connectionIds', [])
                logger.info(f"Found {len(connection_ids)} connection(s) for user {user_id}")
                return connection_ids
            
            logger.info(f"No connections found for user {user_id}")
            return []
            
        except ClientError as e:
            logger.error(f"Error getting connections: {str(e)}")
            return []
    
    def remove_connection(self, user_id: str, connection_id: str) -> bool:
        """
        Remove a specific WebSocket connection for a user.
        
        Args:
            user_id: User identifier
            connection_id: Connection ID to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing connections
            response = self.table.get_item(
                Key={
                    'userId': self.partition_key,
                    'docId': user_id
                }
            )
            
            if 'Item' not in response:
                logger.info(f"No connections found for user {user_id}")
                return True
            
            existing_connections = response['Item'].get('connectionIds', [])
            
            # Remove the specific connection
            updated_connections = [c for c in existing_connections if c != connection_id]
            
            if len(updated_connections) == 0:
                # No connections left, delete the record
                self.table.delete_item(
                    Key={
                        'userId': self.partition_key,
                        'docId': user_id
                    }
                )
                logger.info(f"Removed all connections for user {user_id}")
            else:
                # Update with remaining connections
                timestamp = int(time.time())
                self.table.update_item(
                    Key={
                        'userId': self.partition_key,
                        'docId': user_id
                    },
                    UpdateExpression="SET connectionIds = :connections, lastUpdated = :timestamp",
                    ExpressionAttributeValues={
                        ':connections': updated_connections,
                        ':timestamp': timestamp
                    }
                )
                logger.info(f"Removed connection {connection_id} for user {user_id}, {len(updated_connections)} remaining")
            
            return True
            
        except ClientError as e:
            logger.error(f"Error removing connection: {str(e)}")
            return False
    
    def update_connection_timestamp(self, user_id: str) -> bool:
        """
        Update the last activity timestamp for connections.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = int(time.time())
            
            self.table.update_item(
                Key={
                    'userId': self.partition_key,
                    'docId': user_id
                },
                UpdateExpression="SET lastUpdated = :timestamp",
                ExpressionAttributeValues={
                    ':timestamp': timestamp
                }
            )
            
            return True
            
        except ClientError as e:
            logger.error(f"Error updating connection timestamp: {str(e)}")
            return False
    
    def get_all_user_connections(self) -> list:
        """
        Get all user connection records (for debugging/monitoring).
        
        Returns:
            List of connection records
        """
        try:
            response = self.table.query(
                KeyConditionExpression='userId = :partition_key',
                ExpressionAttributeValues={
                    ':partition_key': self.partition_key
                }
            )
            
            return response.get('Items', [])
            
        except ClientError as e:
            logger.error(f"Error getting all connections: {str(e)}")
            return []
