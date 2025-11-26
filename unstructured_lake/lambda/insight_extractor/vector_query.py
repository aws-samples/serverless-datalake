"""
Vector Query Module

This module provides functionality to query S3 Vectors with metadata filtering
and retrieve relevant text chunks for insight extraction.
"""
import logging
import json
import boto3
from typing import List, Dict, Any
from decimal import Decimal
logger = logging.getLogger(__name__)


class VectorQuery:
    """Query S3 Vectors for document retrieval."""
    
    def __init__(
        self,
        region: str,
        bucket_name: str,
        index_arn: str,
        embed_model_id: str
    ):
        """
        Initialize vector query.
        
        Args:
            region: AWS region
            bucket_name: S3 Vector bucket name
            index_arn: S3 Vector index ARN
            embed_model_id: Bedrock embedding model ID
        """
        self.logger = logging.getLogger(__name__)
        self.s3vectors_client = boto3.client('s3vectors', region_name=region)
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        self.bucket_name = bucket_name
        self.index_arn = index_arn
        self.embed_model_id = embed_model_id
        self.region = region
        
        # Titan V2 specifications
        self.max_input_tokens = 8192
        self.embedding_dimensions = 1024
    
    def generate_query_embedding(self, query_text: str) -> List[float]:
        """
        Generate embedding vector for query text using Titan V2.
        
        Args:
            query_text: Query text to embed
            
        Returns:
            1024-dimensional embedding vector
        """
        try:
            # Truncate if too long
            max_chars = self.max_input_tokens * 4
            if len(query_text) > max_chars:
                self.logger.warning(
                    f"Query text too long ({len(query_text)} chars), truncating"
                )
                query_text = query_text[:max_chars]
            
            # Prepare request for Titan V2
            request_body = {
                "inputText": query_text,
                "dimensions": self.embedding_dimensions,
                "normalize": True
            }
            
            # Invoke Bedrock model
            response = self.bedrock_runtime.invoke_model(
                modelId=self.embed_model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            if 'embedding' in response_body:
                embedding = response_body['embedding']
                self.logger.debug(
                    f"Generated query embedding: {len(embedding)} dimensions"
                )
                return embedding
            else:
                raise ValueError("No embedding in response")
                
        except Exception as e:
            self.logger.error(f"Error generating query embedding: {str(e)}")
            raise
    
    def query_vectors(
        self,
        query_text: str,
        doc_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query vectors with metadata filter for specific document.
        
        Args:
            query_text: User's query text
            doc_id: Document identifier to filter by
            top_k: Number of results to return (default: 5)
            
        Returns:
            List of result dictionaries with text chunks and metadata
        """
        try:
            # Generate query embedding
            print(f"Generating embedding for query: '{query_text[:50]}...'")
            query_embedding = self.generate_query_embedding(query_text)
            
            # Query S3 Vectors with metadata filter
            print(
                f"Querying vectors for docId={doc_id}, top_k={top_k}"
            )
            
            results = self._query_s3_vectors(
                query_vector=query_embedding,
                doc_id=doc_id,
                top_k=top_k
            )
            
            print(f"Retrieved {len(results)} results")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error querying vectors: {str(e)}")
            raise
    
    def _query_s3_vectors(
        self,
        query_vector: List[float],
        doc_id: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Query S3 Vectors API with metadata filtering.
        
        Args:
            query_vector: Query embedding vector
            doc_id: Document ID to filter by
            top_k: Number of results
            
        Returns:
            List of results with text chunks and metadata
        """
        try:
            # Query S3 Vectors using boto3 API
            # Apply metadata filter to search only vectors matching the docId
            response = self.s3vectors_client.query_vectors(
                indexArn=self.index_arn,
                queryVector={'float32': query_vector},
                topK=min(top_k, 30),  # S3 Vectors limit is 30
                filter={'docId': doc_id},  # Metadata filter
                returnDistance=True,
                returnMetadata=True
            )
            
            # Extract results
            vectors = response.get('vectors', [])
            
            if not vectors:
                self.logger.warning(f"No vectors found for docId={doc_id}")
                return []
            
            # Format results
            results = []
            for vector in vectors:
                # Extract metadata
                metadata = vector.get('metadata', {})
                
                # Calculate similarity from distance
                # S3 Vectors returns distance, convert to similarity
                distance = vector.get('distance', 0.0)
                distance_metric = response.get('distanceMetric', 'cosine')
                
                if distance_metric == 'cosine':
                    # Cosine distance: 0 = identical, 2 = opposite
                    # Convert to similarity: 1 = identical, 0 = opposite
                    similarity = 1.0 - (distance / 2.0)
                elif distance_metric == 'euclidean':
                    # Euclidean distance: smaller is better
                    # Convert to similarity (approximate)
                    similarity = 1.0 / (1.0 + distance)
                else:
                    similarity = 1.0 - distance
                
                results.append({
                    'key': vector.get('key', ''),
                    'similarity': max(0.0, min(1.0, similarity)),  # Clamp to [0, 1]
                    'distance': distance,
                    'textChunk': metadata.get('textChunk', ''),
                    'pageRange': metadata.get('pageRange', ''),
                    'docId': metadata.get('docId', ''),
                    'uploadTimestamp': metadata.get('uploadTimestamp', 0)
                })
            
            print(
                f"Retrieved {len(results)} results with distances: "
                f"{[f'{r['distance']:.3f}' for r in results]}"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error querying S3 Vectors: {str(e)}")
            raise
    
    def get_text_chunks(
        self,
        query_text: str,
        doc_id: str,
        top_k: int = 5
    ) -> List[str]:
        """
        Query vectors and return only text chunks.
        
        Convenience method that returns just the text content.
        
        Args:
            query_text: User's query text
            doc_id: Document identifier
            top_k: Number of results (default: 5)
            
        Returns:
            List of text chunks
        """
        results = self.query_vectors(query_text, doc_id, top_k)
        return [r['textChunk'] for r in results if r.get('textChunk')]
