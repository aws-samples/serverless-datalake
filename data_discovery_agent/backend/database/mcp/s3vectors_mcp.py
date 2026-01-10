"""
AWS S3 Vectors Database Tools for Strands Agents MCP Server
"""

import json
import logging
import boto3
import time
import os
from typing import Optional, Dict, Any, List
from fastmcp import FastMCP
from botocore.exceptions import ClientError, BotoCoreError

# Get logger for this module
logger = logging.getLogger(__name__)

# Log startup information
logger.info("Initializing S3 Vectors MCP Server")

mcp = FastMCP(
    "s3vectors-mcp-server",
    instructions="""
    # AWS S3 Vectors MCP Server (Read-Only)
    This server provides read-only tools to interact with AWS S3 Vectors for querying vector data.
    It supports listing vector buckets, indexes, and performing similarity searches with automatic
    text-to-vector embedding generation using Amazon Bedrock.
""")

logger.info("FastMCP server instance created")

# Initialize S3 Vectors and Bedrock clients
try:
    logger.info("Initializing AWS S3 Vectors client...")
    s3vectors_client = boto3.client('s3vectors')
    logger.info("AWS S3 Vectors client initialized successfully")
    
    logger.info("Initializing AWS Bedrock Runtime client...")
    bedrock_runtime = boto3.client('bedrock-runtime')
    logger.info("AWS Bedrock Runtime client initialized successfully")
        
except Exception as e:
    logger.error(f"Failed to initialize AWS clients: {e}")
    s3vectors_client = None
    bedrock_runtime = None

# Default embedding model configuration
DEFAULT_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
MAX_INPUT_TOKENS = 8192
EMBEDDING_DIMENSIONS = 1024


# @mcp.tool()
# async def test_s3vectors_connection() -> str:
#     """
#     Test the AWS S3 Vectors connection.

#     Returns:
#         str: Connection status message
#     """
#     print("🔌 TEST_S3VECTORS_CONNECTION called")
#     logger.info("TEST_S3VECTORS_CONNECTION called")
#     try:
#         if not s3vectors_client:
#             print("❌ S3 Vectors client not initialized")
#             return "❌ S3 Vectors client not initialized"
        
#         # Test connection by listing vector buckets
#         response = s3vectors_client.list_vector_buckets(maxResults=1)
#         print("✅ S3 Vectors connection successful")
#         return "✅ S3 Vectors connection successful"
#     except Exception as e:
#         print(f"❌ S3 Vectors connection error: {str(e)}")
#         return f"❌ S3 Vectors connection error: {str(e)}"


def generate_query_embedding(query_text: str, embed_model_id: str = DEFAULT_EMBED_MODEL_ID) -> List[float]:
    """
    Generate embedding vector for query text using Amazon Bedrock.
    
    Args:
        query_text: Query text to embed
        embed_model_id: Bedrock embedding model ID (default: Titan V2)
        
    Returns:
        Embedding vector as list of floats
    """
    try:
        if not bedrock_runtime:
            raise ValueError("Bedrock Runtime client not initialized")
            
        # Truncate if too long
        max_chars = MAX_INPUT_TOKENS * 4
        if len(query_text) > max_chars:
            logger.warning(f"Query text too long ({len(query_text)} chars), truncating")
            query_text = query_text[:max_chars]
        
        # Prepare request for Titan V2
        request_body = {
            "inputText": query_text,
            "dimensions": EMBEDDING_DIMENSIONS,
            "normalize": True
        }
        
        # Invoke Bedrock model
        response = bedrock_runtime.invoke_model(
            modelId=embed_model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json"
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        
        if 'embedding' in response_body:
            embedding = response_body['embedding']
            logger.debug(f"Generated query embedding: {len(embedding)} dimensions")
            return embedding
        else:
            raise ValueError("No embedding in response")
            
    except Exception as e:
        logger.error(f"Error generating query embedding: {str(e)}")
        raise


# @mcp.tool()
# async def get_s3vectors_config() -> str:
#     """
#     Get the current S3 Vectors MCP server configuration.

#     Returns:
#         str: JSON formatted configuration information
#     """
#     print("⚙️ GET_S3VECTORS_CONFIG called")
#     logger.info("GET_S3VECTORS_CONFIG called")
#     try:
#         config = {
#             "s3vectors_client_initialized": s3vectors_client is not None,
#             "bedrock_runtime_initialized": bedrock_runtime is not None,
#             "default_embed_model": DEFAULT_EMBED_MODEL_ID,
#             "embedding_dimensions": EMBEDDING_DIMENSIONS,
#             "max_input_tokens": MAX_INPUT_TOKENS,
#             "environment_variables": {
#                 "AWS_REGION": os.getenv('AWS_REGION', 'Not set'),
#                 "AWS_DEFAULT_REGION": os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
#             },
#             "service_info": {
#                 "description": "AWS S3 Vectors - Read-only access for querying vector embeddings",
#                 "supported_operations": [
#                     "List vector buckets and indexes",
#                     "Query vectors with automatic text-to-embedding conversion", 
#                     "Similarity search with metadata filtering",
#                     "Retrieve specific vectors by keys"
#                 ],
#                 "mode": "read-only"
#             }
#         }
        
#         print(f"✅ Configuration retrieved successfully")
#         return json.dumps(config, indent=2)
#     except Exception as e:
#         logger.error(f"Error getting configuration: {e}")
#         print(f"❌ Error getting configuration: {str(e)}")
#         return f"❌ Error getting configuration: {str(e)}"


@mcp.tool()
async def list_vector_buckets(max_results: int = 50) -> str:
    """
    List all vector buckets in the account.

    Args:
        max_results (int): Maximum number of buckets to return (default: 50, max: 500)

    Returns:
        str: JSON formatted list of vector buckets
    """
    print(f"📋 LIST_VECTOR_BUCKETS called with max_results: {max_results}")
    logger.info(f"LIST_VECTOR_BUCKETS called with max_results: {max_results}")
    try:
        if not s3vectors_client:
            return "❌ S3 Vectors client not initialized"
        
        max_results = min(max_results, 100)  # Cap at API limit
        response = s3vectors_client.list_vector_buckets(maxResults=max_results)
        buckets = response.get('vectorBuckets', [])
        
        result = {
            "vector_buckets": [
                {
                    "name": bucket.get('vectorBucketName'),
                    "arn": bucket.get('vectorBucketArn'),
                    "creation_date": bucket.get('creationTime')
                }
                for bucket in buckets
            ],
            "count": len(buckets),
            "next_token": response.get('NextToken')
        }
        
        print(f"✅ Found {len(buckets)} vector buckets")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error listing vector buckets: {e}")
        print(f"❌ Error listing vector buckets: {str(e)}")
        return f"❌ Error listing vector buckets: {str(e)}"


@mcp.tool()
async def get_vector_bucket(bucket_name: str) -> str:
    """
    Get details about a specific vector bucket.

    Args:
        bucket_name (str): Name of the vector bucket

    Returns:
        str: JSON formatted bucket details
    """
    print(f"📊 GET_VECTOR_BUCKET called for bucket: {bucket_name}")
    logger.info(f"GET_VECTOR_BUCKET called for bucket: {bucket_name}")
    try:
        if not s3vectors_client:
            return "❌ S3 Vectors client not initialized"
        
        response = s3vectors_client.get_vector_bucket(vectorBucketName=bucket_name)
        
        result = {
            "bucket_name": response.get('vectorBucketName'),
            "bucket_arn": response.get('vectorBucketArn'),
            "creation_date": response.get('creationTime'),
            "encryption_configuration": response.get('encryptionConfiguration', {}),
            "tags": response.get('tags', [])
        }
        
        print(f"✅ Retrieved details for vector bucket '{bucket_name}' {result}")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error getting vector bucket: {e}")
        print(f"❌ Error getting vector bucket '{bucket_name}': {str(e)}")
        return f"❌ Error getting vector bucket '{bucket_name}': {str(e)}"


@mcp.tool()
async def list_indexes(bucket_name: str, max_results: int = 50) -> str:
    """
    List all vector indexes in a vector bucket.

    Args:
        bucket_name (str): Name of the vector bucket
        max_results (int): Maximum number of indexes to return (default: 50, max: 500)

    Returns:
        str: JSON formatted list of vector indexes
    """
    print(f"📋 LIST_INDEXES called for bucket: {bucket_name}")
    logger.info(f"LIST_INDEXES called for bucket: {bucket_name}")
    try:
        if not s3vectors_client:
            return "❌ S3 Vectors client not initialized"
        
        max_results = min(max_results, 500)  # Cap at API limit
        response = s3vectors_client.list_indexes(
            vectorBucketName=bucket_name,
            maxResults=max_results
        )
        indexes = response.get('indexes', [])
        
        result = {
            "bucket_name": bucket_name,
            "indexes": [
                {
                    "name": index.get('indexName'),
                    "arn": index.get('indexArn'),
                    "dimension": index.get('dimension'),
                    "distance_metric": index.get('distanceMetric'),
                    "data_type": index.get('dataType'),
                    "creation_date": index.get('creationTime'),
                    "status": index.get('status')
                }
                for index in indexes
            ],
            "count": len(indexes),
            "next_token": response.get('NextToken')
        }
        
        print(f"✅ Found {len(indexes)} vector indexes in bucket '{bucket_name}'")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error listing indexes: {e}")
        print(f"❌ Error listing indexes in bucket '{bucket_name}': {str(e)}")
        return f"❌ Error listing indexes in bucket '{bucket_name}': {str(e)}"


@mcp.tool()
async def get_index(bucket_name: str, index_name: str) -> str:
    """
    Get details about a specific vector index.

    Args:
        bucket_name (str): Name of the vector bucket
        index_name (str): Name of the vector index

    Returns:
        str: JSON formatted index details
    """
    print(f"📊 GET_INDEX called for index: {index_name} in bucket: {bucket_name}")
    logger.info(f"GET_INDEX called for index: {index_name} in bucket: {bucket_name}")
    try:
        if not s3vectors_client:
            return "❌ S3 Vectors client not initialized"
        
        response = s3vectors_client.get_index(
            vectorBucketName=bucket_name,
            indexName=index_name
        )
        
        result = {
            "bucket_name": bucket_name,
            "index_name": response.get('indexName'),
            "index_arn": response.get('indexArn'),
            "dimension": response.get('dimension'),
            "distance_metric": response.get('distanceMetric'),
            "data_type": response.get('dataType'),
            "creation_date": response.get('creationTime'),
            "status": response.get('status'),
            "metadata_configuration": response.get('metadataConfiguration', {}),
            "encryption_configuration": response.get('encryptionConfiguration', {}),
            "tags": response.get('tags', [])
        }
        
        print(f"✅ Retrieved details for index '{index_name}' in bucket '{bucket_name}'")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error getting index: {e}")
        print(f"❌ Error getting index '{index_name}': {str(e)}")
        return f"❌ Error getting index '{index_name}': {str(e)}"


# @mcp.tool()
# async def query_vectors(
#     bucket_name: str,
#     index_name: str,
#     query_vector: List[float],
#     top_k: int = 10,
#     return_data: bool = False,
#     return_metadata: bool = True,
#     return_distance: bool = True,
#     metadata_filter: Optional[Dict[str, Any]] = None
# ) -> str:
#     """
#     Perform similarity search on vectors in an index.

#     Args:
#         bucket_name (str): Name of the vector bucket
#         index_name (str): Name of the vector index
#         query_vector (list): Query vector as list of float values
#         top_k (int): Number of nearest neighbors to return (default: 10, max: 100)
#         return_data (bool): Whether to return vector data (default: False)
#         return_metadata (bool): Whether to return metadata (default: True)
#         return_distance (bool): Whether to return distances (default: True)
#         metadata_filter (dict, optional): Metadata filter conditions

#     Returns:
#         str: JSON formatted query results
#     """
#     print(f"🔍 QUERY_VECTORS called for index: {index_name} with top_k: {top_k}")
#     logger.info(f"QUERY_VECTORS called for index: {index_name} with top_k: {top_k}")
#     try:
#         if not s3vectors_client:
#             return "❌ S3 Vectors client not initialized"
        
#         # Validate top_k
#         if not (1 <= top_k <= 100):
#             return "❌ top_k must be between 1 and 100"
        
#         if not isinstance(query_vector, list) or not query_vector:
#             return "❌ query_vector must be a non-empty list of numbers"
        
#         # Prepare request parameters
#         request_params = {
#             'VectorBucketName': bucket_name,
#             'IndexName': index_name,
#             'QueryVector': query_vector,
#             'TopK': top_k,
#             'ReturnData': return_data,
#             'ReturnMetadata': return_metadata,
#             'ReturnDistance': return_distance
#         }
        
#         # Add metadata filter if provided
#         if metadata_filter:
#             request_params['Filter'] = metadata_filter
        
#         response = s3vectors_client.query_vectors(**request_params)
        
#         result = {
#             "bucket_name": bucket_name,
#             "index_name": index_name,
#             "query_vector_dimension": len(query_vector),
#             "top_k": top_k,
#             "distance_metric": response.get('DistanceMetric'),
#             "results": response.get('Vectors', []),
#             "result_count": len(response.get('Vectors', []))
#         }
        
#         print(f"✅ Query returned {len(response.get('Vectors', []))} results")
#         return json.dumps(result, indent=2, default=str)
#     except Exception as e:
#         logger.error(f"Error querying vectors: {e}")
#         print(f"❌ Error querying vectors: {str(e)}")
#         return f"❌ Error querying vectors: {str(e)}"


@mcp.tool()
async def query_vectors(
    bucket_name: str,
    index_name: str,
    query_text: str,
    top_k: int = 5,
    return_metadata: bool = True,
    return_distance: bool = True
) -> str:
    """
    Query vectors using natural language text (automatically converts a query string to embeddings).
    
    This tool automatically generates embeddings from your query text using Amazon Bedrock
    and then performs similarity search on the vector index.

    Args:
        bucket_name (str): Name of the vector bucket
        index_name (str): Name of the vector index
        query_text (str): Natural language query text to search for
        top_k (int): Number of nearest neighbors to return (default: 5, max: 30)
        return_metadata (bool): Whether to return metadata (default: True)
        return_distance (bool): Whether to return distances (default: True)
        embed_model_id (str): Bedrock embedding model ID (default: Titan V2)

    Returns:
        str: JSON formatted query results with similarity scores and metadata
    """
    print(f"🔍 QUERY_VECTORS_WITH_TEXT called for query: '{query_text[:50]}...'")
    logger.info(f"QUERY_VECTORS_WITH_TEXT called for index: {index_name}")
    try:
        if not query_text or not query_text.strip():
            return "❌ query_text cannot be empty"
        
        # Generate embedding from query text
        print(f"🧠 Generating embedding for query text...")
        try:
            query_embedding = generate_query_embedding(query_text, DEFAULT_EMBED_MODEL_ID)
        except Exception as e:
            return f"❌ Error generating embedding: {str(e)}"
        
        # Prepare request parameters
        request_params = {
            'vectorBucketName': bucket_name,
            'indexName': index_name,
            'queryVector': {'float32': query_embedding},
            'topK': min(top_k, 30),
            'returnMetadata': return_metadata,
            'returnDistance': return_distance
        }
        
        print(f"🔍 Querying S3 Vectors with {len(query_embedding)}-dimensional embedding...")
        response = s3vectors_client.query_vectors(**request_params)
        
        # Process results to add similarity scores
        vectors = response.get('vectors', [])
        
        if not vectors:
            self.logger.warning(f"No vectors found for docId={doc_id}")
            return []
        
        processed_results = []
        
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
            
            processed_results.append({
                'key': vector.get('key', ''),
                'similarity': max(0.0, min(1.0, similarity)),  # Clamp to [0, 1]
                'distance': distance,
                'textChunk': metadata.get('textChunk', ''),
                'pageRange': metadata.get('pageRange', ''),
                'docId': metadata.get('docId', ''),
                'uploadTimestamp': metadata.get('uploadTimestamp', 0)
            })
            
        return json.dumps(processed_results, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error querying vectors with text: {e}")
        print(f"❌ Error querying vectors with text: {str(e)}")
        return f"❌ Error querying vectors with text: {str(e)}"


# @mcp.tool()
# async def list_vectors(
#     bucket_name: str,
#     index_name: str,
#     max_results: int = 100,
#     return_data: bool = False,
#     return_metadata: bool = True,
#     next_token: Optional[str] = None
# ) -> str:
#     """
#     List vectors in a vector index.

#     Args:
#         bucket_name (str): Name of the vector bucket
#         index_name (str): Name of the vector index
#         max_results (int): Maximum number of vectors to return (default: 100, max: 1000)
#         return_data (bool): Whether to return vector data (default: False)
#         return_metadata (bool): Whether to return metadata (default: True)
#         next_token (str, optional): Token for pagination

#     Returns:
#         str: JSON formatted list of vectors
#     """
#     print(f"📋 LIST_VECTORS called for index: {index_name} with max_results: {max_results}")
#     logger.info(f"LIST_VECTORS called for index: {index_name} with max_results: {max_results}")
#     try:
#         if not s3vectors_client:
#             return "❌ S3 Vectors client not initialized"
        
#         # Validate max_results
#         max_results = min(max_results, 1000)  # Cap at API limit
        
#         # Prepare request parameters
#         request_params = {
#             'vectorBucketName': bucket_name,
#             'indexName': index_name,
#             'maxResults': max_results,
#             'returnData': return_data,
#             'returnMetadata': return_metadata
#         }
        
#         if next_token:
#             request_params['nextToken'] = next_token
        
#         response = s3vectors_client.list_vectors(**request_params)
#         vectors = response.get('vectors', [])
        
#         result = {
#             "bucket_name": bucket_name,
#             "index_name": index_name,
#             "vectors": vectors,
#             "count": len(vectors),
#             "next_token": response.get('nextToken')
#         }
        
#         print(f"✅ Listed {len(vectors)} vectors from index '{index_name}'")
#         return json.dumps(result, indent=2, default=str)
#     except Exception as e:
#         logger.error(f"Error listing vectors: {e}")
#         print(f"❌ Error listing vectors: {str(e)}")
#         return f"❌ Error listing vectors: {str(e)}"


# @mcp.tool()
# async def get_vectors(
#     bucket_name: str,
#     index_name: str,
#     vector_keys: List[str],
#     return_metadata: bool = True
# ) -> str:
#     """
#     Get specific vectors by their keys.

#     Args:
#         bucket_name (str): Name of the vector bucket
#         index_name (str): Name of the vector index
#         vector_keys (list): List of vector keys to retrieve (max 100)
#         return_metadata (bool): Whether to return metadata (default: True)

#     Returns:
#         str: JSON formatted vector data
#     """
#     print(f"📊 GET_VECTORS called for {len(vector_keys)} vectors in index: {index_name}")
#     logger.info(f"GET_VECTORS called for {len(vector_keys)} vectors in index: {index_name}")
#     try:
#         if not s3vectors_client:
#             return "❌ S3 Vectors client not initialized"
        
#         # Validate vector keys count
#         if len(vector_keys) > 100:
#             return "❌ Maximum 100 vector keys per request"
        
#         if not vector_keys:
#             return "❌ At least one vector key is required"
        
#         response = s3vectors_client.get_vectors(
#             vectorBucketName=bucket_name,
#             indexName=index_name,
#             keys=vector_keys,
#             returnMetadata=return_metadata
#         )
        
#         vectors = response.get('vectors', [])
        
#         result = {
#             "bucket_name": bucket_name,
#             "index_name": index_name,
#             "requested_keys": vector_keys,
#             "vectors": vectors,
#             "found_count": len(vectors),
#             "requested_count": len(vector_keys)
#         }
        
#         print(f"✅ Retrieved {len(vectors)} out of {len(vector_keys)} requested vectors")
#         return json.dumps(result, indent=2, default=str)
#     except Exception as e:
#         logger.error(f"Error getting vectors: {e}")
#         print(f"❌ Error getting vectors: {str(e)}")
#         return f"❌ Error getting vectors: {str(e)}"

# @mcp.tool()
# async def get_s3vectors_summary() -> str:
#     """
#     Get a comprehensive summary of all vector buckets and indexes in the account.

#     Returns:
#         str: JSON formatted summary of the entire S3 Vectors setup
#     """
#     print("📋 GET_S3VECTORS_SUMMARY called")
#     logger.info("GET_S3VECTORS_SUMMARY called")
#     try:
#         if not s3vectors_client:
#             return "❌ S3 Vectors client not initialized"
        
#         # Get all vector buckets
#         buckets_response = s3vectors_client.list_vector_buckets(maxResults=500)
#         buckets = buckets_response.get('vectorBuckets', [])
        
#         summary = {
#             "bucket_count": len(buckets),
#             "buckets": [],
#             "total_indexes": 0
#         }
        
#         for bucket in buckets:
#             bucket_name = bucket.get('vectorBucketName')
#             bucket_info = {
#                 "name": bucket_name,
#                 "arn": bucket.get('vectorBucketArn'),
#                 "creation_date": bucket.get('creationTime'),
#                 "indexes": [],
#                 "index_count": 0
#             }
            
#             try:
#                 # Get indexes for this bucket
#                 indexes_response = s3vectors_client.list_indexes(
#                     vectorBucketName=bucket_name,
#                     maxResults=500
#                 )
#                 indexes = indexes_response.get('indexes', [])
                
#                 for index in indexes:
#                     index_info = {
#                         "name": index.get('indexName'),
#                         "arn": index.get('indexArn'),
#                         "dimension": index.get('dimension'),
#                         "distance_metric": index.get('distanceMetric'),
#                         "data_type": index.get('dataType'),
#                         "status": index.get('status'),
#                         "creation_date": index.get('creationTime')
#                     }
#                     bucket_info["indexes"].append(index_info)
                
#                 bucket_info["index_count"] = len(indexes)
#                 summary["total_indexes"] += len(indexes)
                
#             except Exception as e:
#                 logger.warning(f"Error getting indexes for bucket {bucket_name}: {e}")
#                 bucket_info["error"] = f"Could not retrieve indexes: {str(e)}"
            
#             summary["buckets"].append(bucket_info)
        
#         print(f"✅ Generated summary with {len(buckets)} buckets and {summary['total_indexes']} total indexes")
#         return json.dumps(summary, indent=2, default=str)
#     except Exception as e:
#         logger.error(f"Error getting S3 Vectors summary: {e}")
#         print(f"❌ Error getting S3 Vectors summary: {str(e)}")
#         return f"❌ Error getting S3 Vectors summary: {str(e)}"


def main():
    logger.info("Starting S3 Vectors MCP Server with Streamable HTTP transport")
    logger.info("Server will be available at http://localhost:8002/mcp")
    try:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8002)
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        raise


if __name__ == "__main__":
    main()