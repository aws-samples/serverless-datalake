"""
Insight Extraction Lambda Handler

Main handler for extracting structured insights from documents using
vector search and Amazon Bedrock.
"""
import os
import logging
import json
import time
from typing import Dict, Any
from decimal import Decimal
# Import local modules
from cache_manager import CacheManager
from vector_query import VectorQuery
from insight_generator import InsightGenerator

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
VECTOR_BUCKET_NAME = os.environ.get('VECTOR_BUCKET_NAME')
VECTOR_INDEX_ARN = os.environ.get('VECTOR_INDEX_ARN')
EMBED_MODEL_ID = os.environ.get('EMBED_MODEL_ID')
INSIGHT_MODEL_ID = os.environ.get('INSIGHT_MODEL_ID')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
REGION = os.environ.get('REGION', 'us-east-1')
MAX_TOKENS = int(os.environ.get('MAX_TOKENS', '8192'))  # Configurable max tokens for responses
TOP_K_RESULTS = int(os.environ.get('TOP_K_RESULTS', '5'))  # Number of chunks to retrieve from vector search

# Initialize components (reused across invocations)
cache_manager = CacheManager(region=REGION, table_name=DYNAMODB_TABLE_NAME)
vector_query = VectorQuery(
    region=REGION,
    bucket_name=VECTOR_BUCKET_NAME,
    index_arn=VECTOR_INDEX_ARN,
    embed_model_id=EMBED_MODEL_ID
)
insight_generator = InsightGenerator(
    region=REGION, 
    model_id=INSIGHT_MODEL_ID,
    max_tokens=MAX_TOKENS
)

class CustomJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if float(obj).is_integer():
                return int(float(obj))
            else:
                return float(obj)
        return super(CustomJsonEncoder, self).default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for insight extraction.
    
    Handles two types of requests:
    1. POST /insights/extract - Extract insights from document
    2. GET /insights/{docId} - Retrieve cached insights
    
    Args:
        event: Lambda event (API Gateway proxy event)
        context: Lambda context
        
    Returns:
        API Gateway response dictionary
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Determine HTTP method and path
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'POST'))
        path = event.get('path', event.get('rawPath', ''))
        
        logger.info(f"Processing {http_method} {path}")
        
        # Route to appropriate handler
        if path.startswith('/insights'):
            if http_method == 'POST':
                return handle_extract_insights(event)
            elif http_method == 'GET':
                return handle_get_insights(event)
        
        return {
            'statusCode': 405,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Method not allowed'})
        }
            
    except Exception as e:
        logger.error(f"Error in handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_extract_insights(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /insights/extract request.
    
    Args:
        event: API Gateway event
        
    Returns:
        API Gateway response
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        doc_id = body.get('docId')
        prompt = body.get('prompt')
        
        # Validate input
        if not doc_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'docId is required'})
            }
        
        if not prompt:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'prompt is required'})
            }
        
        logger.info(f"Extracting insights for docId={doc_id}, prompt='{prompt[:50]}...'")
        
        # Check cache first
        cached_insights = cache_manager.check_cache(doc_id, prompt)
        
        if cached_insights:
            logger.info("Cache hit - returning cached insights")
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'insights': cached_insights['insights'],
                    'source': 'cache',
                    'timestamp': cached_insights['extractionTimestamp'],
                    'modelId': cached_insights.get('modelId', ''),
                    'chunkCount': cached_insights.get('chunkCount', 0),
                    'expiresAt': cached_insights.get('expiresAt', 0)
                }, cls=CustomJsonEncoder)
            }
        
        # Cache miss - generate insights
        logger.info("Cache miss - generating new insights")
        
        start_time = time.time()
        
        # Query vectors with metadata filtering
        logger.info("Querying vectors...")
        context_chunks = vector_query.get_text_chunks(
            query_text=prompt,
            doc_id=doc_id,
            top_k=TOP_K_RESULTS
        )
        
        if not context_chunks:
            logger.warning(f"No vectors found for docId={doc_id}")
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'No content found for this document',
                    'message': 'The document may not have been processed yet or may not exist'
                })
            }
        
        logger.info(f"Retrieved {len(context_chunks)} context chunks")
        
        # Generate insights using Bedrock
        logger.info("Generating insights with Bedrock...")
        insights = insight_generator.generate_insights(
            user_query=prompt,
            context_chunks=context_chunks
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Insights generated in {processing_time:.2f} seconds")
        
        # Store in cache
        logger.info("Storing insights in cache...")
        cache_manager.store_in_cache(
            doc_id=doc_id,
            prompt=prompt,
            insights=insights,
            model_id=INSIGHT_MODEL_ID,
            chunk_count=len(context_chunks)
        )
        
        # Return response
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'insights': insights,
                'source': 'generated',
                'chunkCount': len(context_chunks),
                'processingTime': round(processing_time, 2),
                'modelId': INSIGHT_MODEL_ID,
                'timestamp': int(time.time())
            }, cls=CustomJsonEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error extracting insights: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Failed to extract insights',
                'message': str(e)
            })
        }


def handle_get_insights(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /insights/{docId} request.
    
    Retrieves all non-expired cached insights for a document.
    
    Args:
        event: API Gateway event
        
    Returns:
        API Gateway response
    """
    try:
        # Extract docId from path parameters
        path_parameters = event.get('pathParameters', {})
        doc_id = path_parameters.get('docId')
        
        if not doc_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'docId is required'})
            }
        
        logger.info(f"Retrieving cached insights for docId={doc_id}")
        
        # Query DynamoDB for all non-expired insights
        insights_list = cache_manager.get_all_insights(doc_id)
        
        if not insights_list:
            logger.info(f"No cached insights found for docId={doc_id}")
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'docId': doc_id,
                    'insights': [],
                    'count': 0
                })
            }
        
        # Format response
        formatted_insights = []
        for item in insights_list:
            formatted_insights.append({
                'prompt': item.get('prompt', ''),
                'insights': item.get('insights', {}),
                'extractionTimestamp': item.get('extractionTimestamp', 0),
                'expiresAt': item.get('expiresAt', 0),
                'modelId': item.get('modelId', ''),
                'chunkCount': item.get('chunkCount', 0)
            })
        
        logger.info(f"Retrieved {len(formatted_insights)} cached insights")
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'docId': doc_id,
                'insights': formatted_insights,
                'count': len(formatted_insights)
            }, cls=CustomJsonEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving insights: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Failed to retrieve insights',
                'message': str(e)
            })
        }


def get_cors_headers() -> Dict[str, str]:
    """
    Get CORS headers for API Gateway response.
    
    Returns:
        Dictionary of CORS headers
    """
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
