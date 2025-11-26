"""
Document API Lambda Handler

Handles HTTP API requests for document management:
- GET /documents - List user documents
- POST /documents/presigned-url - Generate presigned upload URLs
- DELETE /documents/{docId} - Delete documents
"""
import os
import logging
import json
import time
import uuid
import boto3
from typing import Dict, Any, List
from botocore.exceptions import ClientError
from decimal import Decimal

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
DOCUMENTS_BUCKET_NAME = os.environ.get('DOCUMENTS_BUCKET_NAME')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
REGION = os.environ.get('REGION', 'us-east-1')

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=REGION)

# Initialize processing status manager if DynamoDB table is configured
processing_status_manager = None
if DYNAMODB_TABLE_NAME:
    try:
        from processing_status_manager import ProcessingStatusManager
        processing_status_manager = ProcessingStatusManager(region=REGION, table_name=DYNAMODB_TABLE_NAME)
        logger.info(f"Processing status manager initialized with table: {DYNAMODB_TABLE_NAME}")
    except ImportError as e:
        logger.warning(f"ProcessingStatusManager not available: {str(e)}")
else:
    logger.warning("DYNAMODB_TABLE_NAME not set - processing status queries will be limited")

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
    Lambda handler for document API requests.
    
    Handles:
    - GET /documents - List user documents
    - POST /documents/presigned-url - Generate presigned upload URLs
    - DELETE /documents/{docId} - Delete documents
    
    Args:
        event: API Gateway proxy event
        context: Lambda context
        
    Returns:
        API Gateway response dictionary
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Extract HTTP method and path
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
        path = event.get('path', event.get('rawPath', ''))
        
        logger.info(f"Processing {http_method} {path}")
        
        # Route to appropriate handler
        if http_method == 'GET' and path == '/documents':
            return handle_list_documents(event)
        elif http_method == 'POST' and path == '/documents/presigned-url':
            return handle_presigned_url(event)
        elif http_method == 'GET' and path.startswith('/documents/') and path.endswith('/status'):
            return handle_get_processing_status(event)
        elif http_method == 'DELETE' and path.startswith('/documents/'):
            return handle_delete_document(event)
        else:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Endpoint not found'})
            }
            
    except Exception as e:
        logger.error(f"Error in handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_list_documents(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /documents request.
    
    Lists all documents for the authenticated user.
    
    Args:
        event: API Gateway event
        
    Returns:
        API Gateway response
    """
    try:
        # Get user ID from Cognito claims
        user_id = get_user_id_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        logger.info(f"Listing documents for user: {user_id}")
        
        # List objects in S3 bucket with user prefix
        user_prefix = f"users/{user_id}/"
        
        try:
            response = s3_client.list_objects_v2(
                Bucket=DOCUMENTS_BUCKET_NAME,
                Prefix=user_prefix
            )
        except ClientError as e:
            logger.error(f"Error listing S3 objects: {str(e)}")
            return {
                'statusCode': 500,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Failed to list documents'})
            }
        
        documents = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                
                # Skip directories and non-PDF files
                if key.endswith('/') or not key.lower().endswith('.pdf'):
                    continue
                
                # Extract filename from key
                filename = key.split('/')[-1]
                
                # Generate document ID from key
                doc_id = generate_doc_id_from_key(key)
                
                # Get processing status from DynamoDB
                status_data = None
                if processing_status_manager:
                    try:
                        status_data = processing_status_manager.get_processing_status(user_id, doc_id)
                    except Exception as e:
                        logger.warning(f"Error getting status from DynamoDB for {doc_id}: {str(e)}")
                
                # Build document object from DynamoDB data if available
                if status_data:
                    document = {
                        'docId': doc_id,
                        'fileName': status_data.get('filename', filename),
                        'uploadDate': obj['LastModified'].isoformat(),
                        'fileSize': obj['Size'],
                        'status': status_data.get('status', 'processing'),
                        'pageCount': status_data.get('totalPages'),
                        'currentPage': status_data.get('currentPage'),
                        'totalChunks': status_data.get('totalChunks'),
                        'errorCount': status_data.get('errorCount', 0)
                    }
                else:
                    # Fallback: minimal info if no DynamoDB record
                    document = {
                        'docId': doc_id,
                        'fileName': filename,
                        'uploadDate': obj['LastModified'].isoformat(),
                        'fileSize': obj['Size'],
                        'status': 'processing',
                        'pageCount': None
                    }
                
                documents.append(document)
        
        logger.info(f"Found {len(documents)} documents for user {user_id}")
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(documents, cls=CustomJsonEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to list documents'})
        }


def handle_presigned_url(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /documents/presigned-url request.
    
    Generates a presigned POST URL for direct S3 upload.
    
    Args:
        event: API Gateway event
        
    Returns:
        API Gateway response
    """
    try:
        # Get user ID from Cognito claims
        user_id = get_user_id_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        filename = body.get('fileName')
        file_size = body.get('fileSize')
        content_type = body.get('contentType', 'application/pdf')
        connection_id = body.get('connectionId')  # Optional WebSocket connection ID
        
        # Validate input
        if not filename:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'fileName is required'})
            }
        
        if not file_size or file_size <= 0:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'fileSize is required and must be positive'})
            }
        
        # Validate file type
        if not filename.lower().endswith('.pdf'):
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Only PDF files are supported'})
            }
        
        # Check file size limit (50MB)
        max_file_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_file_size:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': f'File size exceeds maximum limit of {max_file_size // (1024*1024)}MB'})
            }
        
        logger.info(f"Generating presigned URL for user {user_id}, file: {filename}")
        
        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        
        # Create S3 key with user prefix
        s3_key = f"users/{user_id}/{doc_id}_{filename}"
        
        # Generate presigned POST URL
        try:
            # Create timestamp for consistent use in fields and conditions
            upload_timestamp = str(int(time.time()))
            
            # Prepare metadata fields
            fields = {
                'Content-Type': content_type,
                'x-amz-meta-user-id': user_id,
                'x-amz-meta-doc-id': doc_id,
                'x-amz-meta-filename': filename,
                'x-amz-meta-timestamp': upload_timestamp
            }
            
            # Prepare conditions
            conditions = [
                {'Content-Type': content_type},
                ['content-length-range', 1, max_file_size],
                {'x-amz-meta-user-id': user_id},
                {'x-amz-meta-doc-id': doc_id},
                {'x-amz-meta-filename': filename},
                {'x-amz-meta-timestamp': upload_timestamp}
            ]
            
            # Add connection ID if provided
            if connection_id:
                fields['x-amz-meta-connection-id'] = connection_id
                conditions.append({'x-amz-meta-connection-id': connection_id})
                logger.info(f"Including connection ID in presigned URL: {connection_id}")
            
            presigned_post = s3_client.generate_presigned_post(
                Bucket=DOCUMENTS_BUCKET_NAME,
                Key=s3_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=3600  # 1 hour
            )
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return {
                'statusCode': 500,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Failed to generate upload URL'})
            }
        
        response_data = {
            'url': presigned_post['url'],
            'fields': presigned_post['fields'],
            'docId': doc_id,
            'expiresIn': 3600
        }
        
        logger.info(f"Generated presigned URL for docId: {doc_id}")
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to generate upload URL'})
        }


def handle_delete_document(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle DELETE /documents/{docId} request.
    
    Deletes a document from S3.
    
    Args:
        event: API Gateway event
        
    Returns:
        API Gateway response
    """
    try:
        # Get user ID from Cognito claims
        user_id = get_user_id_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Extract docId from path parameters
        path_parameters = event.get('pathParameters', {})
        doc_id = path_parameters.get('docId')
        
        if not doc_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'docId is required'})
            }
        
        logger.info(f"Deleting document {doc_id} for user {user_id}")
        
        # Find the document in S3
        user_prefix = f"users/{user_id}/"
        
        try:
            response = s3_client.list_objects_v2(
                Bucket=DOCUMENTS_BUCKET_NAME,
                Prefix=user_prefix
            )
        except ClientError as e:
            logger.error(f"Error listing S3 objects: {str(e)}")
            return {
                'statusCode': 500,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Failed to find document'})
            }
        
        # Find the document key
        document_key = None
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                if generate_doc_id_from_key(key) == doc_id:
                    document_key = key
                    break
        
        if not document_key:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Document not found'})
            }
        
        # Delete the document
        try:
            s3_client.delete_object(Bucket=DOCUMENTS_BUCKET_NAME, Key=document_key)
            logger.info(f"Deleted document: {document_key}")
        except ClientError as e:
            logger.error(f"Error deleting document: {str(e)}")
            return {
                'statusCode': 500,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Failed to delete document'})
            }
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': 'Document deleted successfully'})
        }
        
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to delete document'})
        }


def get_user_id_from_event(event: Dict[str, Any]) -> str:
    """
    Extract user ID from Cognito JWT claims in API Gateway event.
    
    Args:
        event: API Gateway event
        
    Returns:
        User ID string or None if not found
    """
    try:
        # Try to get from authorizer context (API Gateway v1)
        request_context = event.get('requestContext', {})
        authorizer = request_context.get('authorizer', {})
        
        # Check for Cognito claims
        claims = authorizer.get('claims', {})
        if claims:
            # Try different claim fields
            user_id = claims.get('sub') or claims.get('cognito:username') or claims.get('username')
            if user_id:
                return user_id
        
        # Try to get from JWT token directly (API Gateway v2)
        jwt = authorizer.get('jwt', {})
        if jwt:
            jwt_claims = jwt.get('claims', {})
            user_id = jwt_claims.get('sub') or jwt_claims.get('cognito:username') or jwt_claims.get('username')
            if user_id:
                return user_id
        
        logger.warning("Could not extract user ID from event")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting user ID: {str(e)}")
        return None


def generate_doc_id_from_key(s3_key: str) -> str:
    """
    Generate document ID from S3 key.
    
    Args:
        s3_key: S3 object key
        
    Returns:
        Document ID
    """
    # Extract filename from key
    filename = s3_key.split('/')[-1]
    
    # If filename starts with UUID, extract it
    if '_' in filename:
        potential_uuid = filename.split('_')[0]
        # Check if it looks like a UUID
        if len(potential_uuid) == 36 and potential_uuid.count('-') == 4:
            return potential_uuid
    
    # Fallback: use filename without extension
    return filename.rsplit('.', 1)[0]


def determine_document_status(user_id: str, doc_id: str, metadata: Dict[str, str]) -> str:
    """
    Determine document processing status.
    
    First checks DynamoDB for processing status, falls back to S3 metadata.
    
    Args:
        user_id: User identifier
        doc_id: Document ID
        metadata: S3 object metadata (fallback)
        
    Returns:
        Status string: 'processing', 'completed', or 'failed'
    """
    # Try to get status from DynamoDB first
    if processing_status_manager:
        try:
            status_data = processing_status_manager.get_processing_status(user_id, doc_id)
            if status_data:
                return status_data.get('status', 'processing')
        except Exception as e:
            logger.warning(f"Error getting status from DynamoDB: {str(e)}")
        
    # Default to processing
    return 'processing'


def handle_get_processing_status(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /documents/{docId}/status request.
    
    Gets the current processing status for a document.
    
    Args:
        event: API Gateway event
        
    Returns:
        API Gateway response
    """
    try:
        # Get user ID from Cognito claims
        user_id = get_user_id_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Extract docId from path parameters
        path_parameters = event.get('pathParameters', {})
        doc_id = path_parameters.get('docId')
        
        if not doc_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'docId is required'})
            }
        
        logger.info(f"Getting processing status for docId: {doc_id}, user: {user_id}")
        
        if not processing_status_manager:
            # Fallback to S3 metadata approach
            return get_status_from_s3_metadata(user_id, doc_id)
        
        # Get processing status from DynamoDB
        status_data = processing_status_manager.get_processing_status(user_id, doc_id)
        
        if not status_data:
            # Check if document exists in S3
            if not document_exists_in_s3(user_id, doc_id):
                return {
                    'statusCode': 404,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Document not found'})
                }
            
            # Document exists but no processing status - assume completed
            status_data = {
                'status': 'completed',
                'docId': doc_id,
                'message': 'Processing completed (legacy document)'
            }
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(status_data)
        }
        
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to get processing status'})
        }


def get_status_from_s3_metadata(user_id: str, doc_id: str) -> Dict[str, Any]:
    """
    Fallback method to get status from S3 metadata.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        
    Returns:
        API Gateway response
    """
    try:
        # Find the document in S3
        user_prefix = f"users/{user_id}/"
        
        response = s3_client.list_objects_v2(
            Bucket=DOCUMENTS_BUCKET_NAME,
            Prefix=user_prefix
        )
        
        document_key = None
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                if generate_doc_id_from_key(key) == doc_id:
                    document_key = key
                    break
        
        if not document_key:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Document not found'})
            }
        
        # Get metadata
        head_response = s3_client.head_object(Bucket=DOCUMENTS_BUCKET_NAME, Key=document_key)
        metadata = head_response.get('Metadata', {})
        
        # Determine status from metadata (fallback)
        status = determine_document_status(user_id, doc_id, metadata)
        
        status_data = {
            'docId': doc_id,
            'status': status,
            'filename': metadata.get('filename', document_key.split('/')[-1]),
            'message': f'Status determined from S3 metadata: {status}'
        }
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(status_data, cls=CustomJsonEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error getting status from S3: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to get processing status'})
        }


def document_exists_in_s3(user_id: str, doc_id: str) -> bool:
    """
    Check if document exists in S3.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        
    Returns:
        True if document exists, False otherwise
    """
    try:
        user_prefix = f"users/{user_id}/"
        
        response = s3_client.list_objects_v2(
            Bucket=DOCUMENTS_BUCKET_NAME,
            Prefix=user_prefix
        )
        
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                if generate_doc_id_from_key(key) == doc_id:
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking document existence: {str(e)}")
        return False


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
        'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
    }