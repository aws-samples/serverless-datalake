"""
S3 Vectors Storage Module

This module provides a wrapper for the S3 Vectors API to store and manage
vector embeddings with metadata using the boto3 s3vectors client.
"""
import logging
import boto3
from typing import List, Dict, Any
from decimal import Decimal
logger = logging.getLogger(__name__)


class VectorStore:
    """Wrapper for S3 Vectors API operations using boto3 s3vectors client."""
    
    def __init__(self, region: str, bucket_name: str, index_arn: str):
        """
        Initialize vector store.
        
        Args:
            region: AWS region
            bucket_name: S3 Vector bucket name
            index_arn: S3 Vector index ARN
        """
        self.logger = logging.getLogger(__name__)
        self.s3vectors_client = boto3.client('s3vectors', region_name=region)
        self.bucket_name = bucket_name
        self.index_arn = index_arn
        self.region = region
    
    def put_vector(
        self,
        key: str,
        vector: List[float],
        filterable_metadata: Dict[str, Any],
        non_filterable_metadata: Dict[str, Any]
    ) -> bool:
        """
        Store a vector with metadata in S3 Vectors.
        
        Args:
            key: Unique key for the vector (e.g., "doc-id#chunk-0")
            vector: Embedding vector (1024 dimensions)
            filterable_metadata: Metadata that can be used in queries
                - docId: Document identifier
                - pageRange: Page range (e.g., "1-10")
                - uploadTimestamp: Unix timestamp
            non_filterable_metadata: Metadata for context retrieval
                - textChunk: Original text content
                
        Returns:
            True if successful, False otherwise
        """
        try:
            # Combine filterable and non-filterable metadata
            metadata = {**filterable_metadata, **non_filterable_metadata}
            
            # Store vector using S3 Vectors API
            self.s3vectors_client.put_vectors(
                indexArn=self.index_arn,
                vectors=[
                    {
                        'key': key,
                        'data': {'float32': vector},
                        'metadata': metadata
                    }
                ]
            )
            
            self.logger.debug(f"Stored vector with key: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing vector {key}: {str(e)}")
            return False
    
    def put_vectors_batch(
        self,
        vectors: List[Dict[str, Any]]
    ) -> int:
        """
        Store multiple vectors in batch.
        
        Args:
            vectors: List of vector dictionaries with keys:
                - key: Unique identifier
                - vector: Embedding vector
                - filterable_metadata: Filterable metadata dict
                - non_filterable_metadata: Non-filterable metadata dict
                
        Returns:
            Number of successfully stored vectors
        """
        if not vectors:
            return 0
        
        try:
            # Prepare vectors for batch insert (max 500 per request)
            batch_size = 500
            total_success = 0
            
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                
                # Format vectors for S3 Vectors API
                formatted_vectors = []
                for vector_data in batch:
                    metadata = {
                        **vector_data['filterable_metadata'],
                        **vector_data['non_filterable_metadata']
                    }
                    
                    formatted_vectors.append({
                        'key': vector_data['key'],
                        'data': {'float32': vector_data['vector']},
                        'metadata': metadata
                    })
                
                # Store batch using S3 Vectors API
                self.s3vectors_client.put_vectors(
                    indexArn=self.index_arn,
                    vectors=formatted_vectors
                )
                
                total_success += len(batch)
                self.logger.debug(f"Stored batch of {len(batch)} vectors")
            
            print(
                f"Stored {total_success}/{len(vectors)} vectors successfully"
            )
            
            return total_success
            
        except Exception as e:
            self.logger.error(f"Error storing vector batch: {str(e)}")
            return 0
    
    def delete_vector(self, key: str) -> bool:
        """
        Delete a vector from S3 Vectors.
        
        Args:
            key: Vector key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3vectors_client.delete_vectors(
                indexArn=self.index_arn,
                keys=[key]
            )
            
            self.logger.debug(f"Deleted vector with key: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting vector {key}: {str(e)}")
            return False
    
    def delete_vectors_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all vectors associated with a document ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Number of vectors deleted
        """
        try:
            # List all vectors with the doc_id prefix
            # Assuming vector keys follow pattern: {doc_id}#chunk-{index}
            prefix = f"{doc_id}#"
            
            # Use S3 Vectors ListVectors API to find all vectors for this doc
            keys_to_delete = []
            next_token = None
            
            while True:
                list_params = {
                    'indexArn': self.index_arn,
                    'maxResults': 1000,
                    'returnData': False,
                    'returnMetadata': False
                }
                
                if next_token:
                    list_params['nextToken'] = next_token
                
                response = self.s3vectors_client.list_vectors(**list_params)
                
                # Filter vectors by prefix
                for vector in response.get('vectors', []):
                    key = vector.get('key', '')
                    if key.startswith(prefix):
                        keys_to_delete.append(key)
                
                # Check for more results
                next_token = response.get('nextToken')
                if not next_token:
                    break
            
            if not keys_to_delete:
                print(f"No vectors found for doc_id: {doc_id}")
                return 0
            
            # Delete vectors in batches (max 500 per request)
            batch_size = 500
            delete_count = 0
            
            for i in range(0, len(keys_to_delete), batch_size):
                batch = keys_to_delete[i:i + batch_size]
                
                self.s3vectors_client.delete_vectors(
                    indexArn=self.index_arn,
                    keys=batch
                )
                
                delete_count += len(batch)
                self.logger.debug(f"Deleted batch of {len(batch)} vectors")
            
            print(
                f"Deleted {delete_count} vectors for doc_id: {doc_id}"
            )
            
            return delete_count
            
        except Exception as e:
            self.logger.error(
                f"Error deleting vectors for doc_id {doc_id}: {str(e)}"
            )
            return 0
    
    def create_vector_key(self, doc_id: str, chunk_index: int) -> str:
        """
        Create a standardized vector key.
        
        Args:
            doc_id: Document identifier
            chunk_index: Chunk index
            
        Returns:
            Vector key in format: {doc_id}#chunk-{index}
        """
        return f"{doc_id}#chunk-{chunk_index}"
