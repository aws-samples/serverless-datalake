"""
DynamoDB Cache Manager Module

This module provides functionality to check and store insights in DynamoDB cache
with 24-hour TTL for cost optimization.
"""
import logging
import time
import hashlib
import json
import boto3
from typing import Dict, Any, Optional, Union
from boto3.dynamodb.conditions import Key, Attr
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

def convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility.
    
    Args:
        obj: Object to convert (dict, list, or primitive)
        
    Returns:
        Converted object with Decimals instead of floats
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj


class CacheManager:
    """Manage DynamoDB cache for document insights."""
    
    def __init__(self, region: str, table_name: str):
        """
        Initialize cache manager.
        
        Args:
            region: AWS region for DynamoDB
            table_name: DynamoDB table name
        """
        self.logger = logging.getLogger(__name__)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
        
        # TTL configuration
        self.ttl_hours = 24
        
        # DynamoDB item size limit (400KB with safety margin)
        self.max_item_size_bytes = 380 * 1024  # 380KB to leave margin
    
    def _hash_prompt(self, prompt: str) -> str:
        """
        Create a hash of the prompt for consistent cache lookups.
        
        Converts prompt to lowercase, strips whitespace, and creates SHA-256 hash.
        This ensures cache hits for semantically identical prompts regardless of
        casing or whitespace variations.
        
        Args:
            prompt: Raw prompt string
            
        Returns:
            SHA-256 hash of the normalized prompt
        """
        # Normalize: lowercase, strip whitespace, collapse multiple spaces
        normalized = ' '.join(prompt.strip().lower().split())
        # Create SHA-256 hash
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def _estimate_item_size(self, item: Dict[str, Any]) -> int:
        """
        Estimate the size of a DynamoDB item in bytes.
        
        Handles Decimal and float types properly during serialization.
        
        Args:
            item: DynamoDB item dictionary
            
        Returns:
            Estimated size in bytes
        """
        # Convert to JSON and measure byte size
        # Use custom encoder to handle Decimal types
        json_str = json.dumps(item, cls=CustomJsonEncoder)
        return len(json_str.encode('utf-8'))
    
    def check_cache(self, doc_id: str, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Check cache for existing insights.
        
        Queries DynamoDB by docId and filters by prompt hash and TTL.
        Returns the most recent cached result if found.
        
        Args:
            doc_id: Document identifier
            prompt: User's query prompt
            
        Returns:
            Cached insights dictionary or None if not found
        """
        try:
            current_time = int(time.time())
            prompt_hash = self._hash_prompt(prompt)
            
            self.logger.info(f"Checking cache for docId={doc_id}, promptHash={prompt_hash}, prompt='{prompt[:50]}...'")
            
            # Query by docId (partition key)
            response = self.table.query(
                KeyConditionExpression=Key('docId').eq(doc_id),
                FilterExpression=(
                    Attr('promptHash').eq(prompt_hash) & 
                    Attr('expiresAt').gt(current_time)
                ),
                ScanIndexForward=False,  # Sort by extractionTimestamp descending
                Limit=1  # Get most recent only
            )
            
            if response['Items']:
                cached_item = response['Items'][0]
                self.logger.info(
                    f"Cache hit for docId={doc_id}, promptHash={prompt_hash}, prompt='{prompt[:50]}...'"
                )
                return cached_item
            else:
                self.logger.info(
                    f"Cache miss for docId={doc_id}, promptHash={prompt_hash}, prompt='{prompt[:50]}...'"
                )
                return None
                
        except Exception as e:
            self.logger.error(f"Error checking cache: {str(e)}", exc_info=True)
            # Return None on error to allow fallback to generation
            return None
    
    def store_in_cache(
        self,
        doc_id: str,
        prompt: str,
        insights: Dict[str, Any],
        model_id: str,
        chunk_count: int
    ) -> bool:
        """
        Store insights in cache with 24-hour TTL.
        
        Skips caching if the item size exceeds DynamoDB's 400KB limit.
        
        Args:
            doc_id: Document identifier
            prompt: User's query prompt
            insights: Extracted insights dictionary
            model_id: Bedrock model ID used for extraction
            chunk_count: Number of chunks retrieved
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            timestamp = int(time.time())
            expires_at = timestamp + (self.ttl_hours * 3600)
            prompt_hash = self._hash_prompt(prompt)
            
            # Prepare item - convert floats to Decimal for DynamoDB
            item = {
                'docId': doc_id,
                'extractionTimestamp': timestamp,
                'prompt': prompt,
                'promptHash': prompt_hash,  # Add hash for efficient filtering
                'insights': convert_floats_to_decimal(insights),
                'modelId': model_id,
                'chunkCount': chunk_count,
                'expiresAt': expires_at
            }
            
            # Check item size before storing
            item_size = self._estimate_item_size(item)
            
            if item_size > self.max_item_size_bytes:
                self.logger.warning(
                    f"Skipping cache storage - item too large: {item_size} bytes "
                    f"(max: {self.max_item_size_bytes} bytes). "
                    f"docId={doc_id}, promptHash={prompt_hash}"
                )
                return False
            
            # Store in DynamoDB
            self.table.put_item(Item=item)
            
            self.logger.info(
                f"Stored insights in cache: docId={doc_id}, "
                f"promptHash={prompt_hash}, prompt='{prompt[:50]}...', "
                f"size={item_size} bytes, expires in {self.ttl_hours}h"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing in cache: {str(e)}", exc_info=True)
            return False
    
    def get_all_insights(self, doc_id: str) -> list:
        """
        Retrieve all non-expired insights for a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            List of insight items sorted by timestamp descending
        """
        try:
            current_time = int(time.time())
            
            # Query by docId
            response = self.table.query(
                KeyConditionExpression=Key('docId').eq(doc_id),
                FilterExpression=Attr('expiresAt').gt(current_time),
                ScanIndexForward=False  # Sort by extractionTimestamp descending
            )
            
            items = response['Items']
            
            print(
                f"Retrieved {len(items)} non-expired insights for docId={doc_id}"
            )
            
            return items
            
        except Exception as e:
            self.logger.error(f"Error retrieving insights: {str(e)}")
            return []
    
    def invalidate_cache(self, doc_id: str) -> int:
        """
        Invalidate all cache entries for a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Number of items deleted
        """
        try:
            # Query all items for this document
            response = self.table.query(
                KeyConditionExpression=Key('docId').eq(doc_id)
            )
            
            items = response['Items']
            deleted_count = 0
            
            # Delete each item
            for item in items:
                self.table.delete_item(
                    Key={
                        'docId': item['docId'],
                        'extractionTimestamp': item['extractionTimestamp']
                    }
                )
                deleted_count += 1
            
            print(
                f"Invalidated {deleted_count} cache entries for docId={doc_id}"
            )
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error invalidating cache: {str(e)}")
            return 0
