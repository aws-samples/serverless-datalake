"""
Embedding Generation Module

This module provides functionality to generate vector embeddings using
Amazon Titan V2 embedding model.
"""
import logging
import json
import boto3
from typing import List
from decimal import Decimal
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate vector embeddings using Amazon Titan V2."""
    
    def __init__(self, region: str, model_id: str = "amazon.titan-embed-text-v2:0"):
        """
        Initialize embedding generator.
        
        Args:
            region: AWS region for Bedrock service
            model_id: Bedrock model ID for embeddings (default: Titan V2)
        """
        self.logger = logging.getLogger(__name__)
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        self.model_id = model_id
        
        # Titan V2 specifications
        self.max_input_tokens = 8192
        self.embedding_dimensions = 1024
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Text to embed (max 8192 tokens)
            
        Returns:
            1024-dimensional embedding vector
            
        Raises:
            ValueError: If text exceeds token limit
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Truncate text if too long (rough estimate: 1 token ≈ 4 characters)
        max_chars = self.max_input_tokens * 4
        if len(text) > max_chars:
            self.logger.warning(
                f"Text length ({len(text)} chars) exceeds limit, truncating to {max_chars} chars"
            )
            text = text[:max_chars]
        
        try:
            # Prepare request for Titan V2
            request_body = {
                "inputText": text,
                "dimensions": self.embedding_dimensions,
                "normalize": True  # Normalize vectors for cosine similarity
            }
            
            # Invoke Bedrock model
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract embedding vector
            if 'embedding' in response_body:
                embedding = response_body['embedding']
                
                # Validate embedding dimensions
                if len(embedding) != self.embedding_dimensions:
                    raise ValueError(
                        f"Expected {self.embedding_dimensions} dimensions, "
                        f"got {len(embedding)}"
                    )
                
                self.logger.debug(
                    f"Generated {len(embedding)}-dimensional embedding for "
                    f"{len(text)} characters"
                )
                
                return embedding
            else:
                raise ValueError("No embedding in response")
                
        except Exception as e:
            self.logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Note: This processes texts sequentially. For production use,
        consider implementing batch processing if Bedrock supports it.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for idx, text in enumerate(texts):
            try:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
                self.logger.debug(f"Generated embedding {idx + 1}/{len(texts)}")
            except Exception as e:
                self.logger.error(f"Error generating embedding for text {idx}: {str(e)}")
                # Re-raise to fail fast
                raise
        
        print(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def validate_embedding(self, embedding: List[float]) -> bool:
        """
        Validate an embedding vector.
        
        Args:
            embedding: Embedding vector to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not embedding:
            return False
        
        if len(embedding) != self.embedding_dimensions:
            self.logger.error(
                f"Invalid embedding dimensions: expected {self.embedding_dimensions}, "
                f"got {len(embedding)}"
            )
            return False
        
        # Check if all values are floats
        if not all(isinstance(x, (int, float)) for x in embedding):
            self.logger.error("Embedding contains non-numeric values")
            return False
        
        return True
