"""
Document Processing Lambda Handler

Main handler for processing PDF documents: extract text, generate embeddings,
and store in S3 Vectors with real-time progress updates via WebSocket.
"""
import os
import logging
import json
import time
import uuid
import boto3
from typing import Dict, Any, List, Optional
from decimal import Decimal
# Import local modules
from pdf_extractor import PDFExtractor
from image_detector import ImageDetector
from ocr_processor import OCRProcessor
from text_chunker import TextChunker
from embedding_generator import EmbeddingGenerator
from vector_store import VectorStore
from websocket_notifier import WebSocketNotifier
from processing_status_manager import ProcessingStatusManager
from websocket_connection_manager import WebSocketConnectionManager

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
WSS_URL = os.environ.get('WSS_URL')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
REGION = os.environ.get('REGION', 'us-east-1')
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', '2048'))
CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', '204'))

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=REGION)

# Initialize processors (reused across invocations)
pdf_extractor = PDFExtractor()
image_detector = ImageDetector()
ocr_processor = OCRProcessor(region=REGION)
text_chunker = TextChunker(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
embedding_generator = EmbeddingGenerator(region=REGION, model_id=EMBED_MODEL_ID)
vector_store = VectorStore(
    region=REGION,
    bucket_name=VECTOR_BUCKET_NAME,
    index_arn=VECTOR_INDEX_ARN
)
websocket_notifier = WebSocketNotifier(websocket_url=WSS_URL, region=REGION)

# Initialize processing status manager and connection manager if DynamoDB table is configured
processing_status_manager = None
connection_manager = None
if DYNAMODB_TABLE_NAME:
    processing_status_manager = ProcessingStatusManager(region=REGION, table_name=DYNAMODB_TABLE_NAME)
    connection_manager = WebSocketConnectionManager(region=REGION, table_name=DYNAMODB_TABLE_NAME)
    print(f"Processing status manager initialized with table: {DYNAMODB_TABLE_NAME}")
else:
    logger.warning("DYNAMODB_TABLE_NAME not set - processing status tracking disabled")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for document processing.
    
    Triggered by S3 events:
    - OBJECT_CREATED: Process document
    - OBJECT_REMOVED_DELETE: Clean up vectors
    
    Args:
        event: Lambda event (S3 event notification)
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    print(f"Received event: {json.dumps(event)}")
    
    # Handle WebSocket events
    if 'requestContext' in event and 'connectionId' in event.get('requestContext', {}):
        return handle_websocket_event(event)
    
    # Handle S3 events
    try:
        # Parse S3 event
        if 'Records' not in event:
            logger.error("No Records in event")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid event format'})
            }
        
        for record in event['Records']:
            # Check event type
            event_name = record.get('eventName', '')
            
            if event_name.startswith('ObjectCreated'):
                # Process new document
                process_document(record)
            elif event_name.startswith('ObjectRemoved:Delete'):
                # Clean up deleted document
                cleanup_document(record)
            else:
                logger.warning(f"Unhandled event type: {event_name}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Processing complete'})
        }
        
    except Exception as e:
        logger.error(f"Error in handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def handle_websocket_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle WebSocket connection events.
    
    Args:
        event: WebSocket event from API Gateway
        
    Returns:
        Response dictionary
    """
    try:
        request_context = event.get('requestContext', {})
        connection_id = request_context.get('connectionId')
        route_key = request_context.get('routeKey')
        
        logger.info(f"WebSocket event: {route_key}, connection: {connection_id}")
        
        if route_key == '$connect':
            # Handle new connection
            query_params = event.get('queryStringParameters', {})
            token = query_params.get('token')
            
            if not token:
                logger.error("No token provided in WebSocket connection")
                return {'statusCode': 401, 'body': 'Unauthorized - token required'}
            
            if not connection_manager:
                logger.error("Connection manager not initialized")
                return {'statusCode': 500, 'body': 'Server configuration error'}
            
            # Decode JWT token to get user ID
            payload = connection_manager.decode_jwt_token(token)
            if not payload:
                logger.error("Invalid token")
                return {'statusCode': 401, 'body': 'Unauthorized - invalid token'}
            
            # Extract user ID from token (Cognito uses 'sub' claim)
            user_id = payload.get('sub') or payload.get('cognito:username') or payload.get('username')
            if not user_id:
                logger.error("No user ID in token")
                return {'statusCode': 401, 'body': 'Unauthorized - invalid token claims'}
            
            # Store connection
            success = connection_manager.store_connection(user_id, connection_id)
            if success:
                logger.info(f"WebSocket connected: user={user_id}, connection={connection_id}")
                return {'statusCode': 200, 'body': 'Connected'}
            else:
                return {'statusCode': 500, 'body': 'Failed to store connection'}
        
        elif route_key == '$disconnect':
            # Handle disconnection - we need to find the user by connection_id
            # For now, we'll let TTL handle cleanup
            logger.info(f"WebSocket disconnected: {connection_id}")
            return {'statusCode': 200, 'body': 'Disconnected'}
        
        else:
            # Handle other routes (if any)
            logger.warning(f"Unhandled WebSocket route: {route_key}")
            return {'statusCode': 200, 'body': 'OK'}
    
    except Exception as e:
        logger.error(f"Error handling WebSocket event: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': f'Error: {str(e)}'}


def process_document(record: Dict[str, Any]) -> None:
    """
    Process a newly uploaded document.
    
    Args:
        record: S3 event record
    """
    try:
        # Extract S3 information
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"Processing document: s3://{bucket}/{key}")
        
        # Generate document ID from key
        doc_id = generate_doc_id(key)
        
        # Get user ID from S3 metadata
        user_id = get_user_id_from_s3(bucket, key)
        
        # Get connection IDs from DynamoDB (if user has active WebSocket connections)
        connection_ids = []
        if connection_manager and user_id:
            connection_ids = connection_manager.get_connections(user_id)
        
        # Download PDF from S3
        print(f"Downloading PDF from S3...")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_bytes = response['Body'].read()
        
        # Extract all text from PDF once (more efficient than page-by-page)
        print(f"Extracting text from PDF...")
        all_page_texts = pdf_extractor.extract_text_from_pdf(pdf_bytes)
        total_pages = len(all_page_texts)
        print(f"Document has {total_pages} pages")
        
        # Extract filename from key
        filename = key.split('/')[-1]
        
        # Create processing status record
        if processing_status_manager and user_id:
            processing_status_manager.create_processing_record(
                user_id=user_id,
                doc_id=doc_id,
                total_pages=total_pages,
                filename=filename
            )
        
        # Send processing started notification to all active connections
        for connection_id in connection_ids:
            try:
                websocket_notifier.send_processing_started(
                    connection_id=connection_id,
                    doc_id=doc_id,
                    total_pages=total_pages
                )
            except Exception as e:
                logger.warning(f"Failed to send to connection {connection_id}: {str(e)}")
        
        # Process document in batches
        page_texts = []
        total_chunks = 0
        batch_size = 10
        
        for page_num in range(total_pages):
            try:
                # Get text from already extracted pages
                page_text = all_page_texts[page_num]['text']
                
                # Check for images and perform OCR if needed
                if image_detector.has_images(pdf_bytes, page_num):
                    print(f"Page {page_num + 1} has images, performing OCR...")
                    images = image_detector.extract_images(pdf_bytes, page_num)
                    ocr_text = ocr_processor.process_images(images)
                    
                    # Combine text and OCR
                    if ocr_text:
                        page_text = f"{page_text}\n\n{ocr_text}" if page_text else ocr_text
                
                # Add to batch
                page_texts.append({
                    'page': page_num + 1,
                    'text': page_text
                })
                
                # Process batch every 10 pages
                if (page_num + 1) % batch_size == 0:
                    chunks_created = process_batch(page_texts, doc_id)
                    total_chunks += chunks_created
                    
                    # Update processing status
                    if processing_status_manager and user_id:
                        processing_status_manager.update_progress(
                            user_id=user_id,
                            doc_id=doc_id,
                            current_page=page_num + 1,
                            message=f"Processed {page_num + 1} pages, created {chunks_created} chunks"
                        )
                    
                    # Send progress update to all active connections
                    for connection_id in connection_ids:
                        try:
                            websocket_notifier.send_progress(
                                connection_id=connection_id,
                                doc_id=doc_id,
                                pages_processed=page_num + 1,
                                total_pages=total_pages,
                                message_text=f"Processed {page_num + 1} pages, created {chunks_created} chunks"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send progress to connection {connection_id}: {str(e)}")
                    
                    # Clear batch
                    page_texts = []
                
            except Exception as e:
                logger.error(f"Error processing page {page_num + 1}: {str(e)}")
                
                # Record error in DynamoDB
                if processing_status_manager and user_id:
                    processing_status_manager.add_error(
                        user_id=user_id,
                        doc_id=doc_id,
                        page_num=page_num + 1,
                        error_message=str(e)
                    )
                
                # Send error notification but continue processing
                for connection_id in connection_ids:
                    try:
                        websocket_notifier.send_error(
                            connection_id=connection_id,
                            doc_id=doc_id,
                            error_code="PAGE_PROCESSING_ERROR",
                            error_message=f"Error on page {page_num + 1}: {str(e)}",
                            recoverable=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send error to connection {connection_id}: {str(e)}")
        
        # Process remaining pages
        if page_texts:
            chunks_created = process_batch(page_texts, doc_id)
            total_chunks += chunks_created
        
        # Mark processing as completed
        if processing_status_manager and user_id:
            processing_status_manager.mark_completed(
                user_id=user_id,
                doc_id=doc_id,
                total_chunks=total_chunks
            )
        
        # Send completion notification to all active connections
        for connection_id in connection_ids:
            try:
                websocket_notifier.send_processing_complete(
                    connection_id=connection_id,
                    doc_id=doc_id,
                    total_chunks=total_chunks
                )
            except Exception as e:
                logger.warning(f"Failed to send completion to connection {connection_id}: {str(e)}")
        
        print(
            f"Document processing complete: {doc_id}, "
            f"{total_pages} pages, {total_chunks} chunks"
        )
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        
        # Mark processing as failed
        if 'doc_id' in locals() and 'user_id' in locals() and processing_status_manager and user_id:
            processing_status_manager.mark_failed(
                user_id=user_id,
                doc_id=doc_id,
                error_message=str(e)
            )
        
        # Send error notification to all active connections
        if 'connection_ids' in locals():
            for connection_id in connection_ids:
                try:
                    websocket_notifier.send_error(
                        connection_id=connection_id,
                        doc_id=doc_id if 'doc_id' in locals() else 'unknown',
                        error_code="PROCESSING_FAILED",
                        error_message=str(e),
                        recoverable=False
                    )
                except Exception as send_error:
                    logger.warning(f"Failed to send error to connection {connection_id}: {str(send_error)}")
        
        raise





def process_batch(page_texts: List[Dict[str, Any]], doc_id: str) -> int:
    """
    Process a batch of pages: chunk text, generate embeddings, store vectors.
    
    Args:
        page_texts: List of page text dictionaries
        doc_id: Document identifier
        
    Returns:
        Number of chunks created
    """
    if not page_texts:
        return 0
    
    try:
        # Combine text from all pages in batch
        combined_text = "\n\n".join([p['text'] for p in page_texts if p['text']])
        
        if not combined_text.strip():
            logger.warning("No text content in batch")
            return 0
        
        # Determine page range
        first_page = page_texts[0]['page']
        last_page = page_texts[-1]['page']
        page_range = f"{first_page}-{last_page}"
        
        print(f"Processing batch: pages {page_range}, {len(combined_text)} characters")
        
        # Chunk text
        chunks = text_chunker.chunk_text(
            text=combined_text,
            page_range=page_range,
            doc_id=doc_id
        )
        
        print(f"Created {len(chunks)} chunks")
        
        # Generate embeddings and store vectors
        vectors_to_store = []
        
        for chunk in chunks:
            try:
                # Generate embedding
                embedding = embedding_generator.generate_embedding(chunk['text'])
                
                # Prepare vector data
                chunk_index = chunk['metadata']['chunkIndex']
                vector_key = vector_store.create_vector_key(doc_id, chunk_index)
                
                vectors_to_store.append({
                    'key': vector_key,
                    'vector': embedding,
                    'filterable_metadata': {
                        'docId': doc_id,
                        'pageRange': page_range,
                        'uploadTimestamp': int(time.time())
                    },
                    'non_filterable_metadata': {
                        'textChunk': chunk['text']
                    }
                })
                
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_index}: {str(e)}")
                continue
        
        # Store vectors in batch
        success_count = vector_store.put_vectors_batch(vectors_to_store)
        
        print(f"Stored {success_count}/{len(vectors_to_store)} vectors")
        
        return len(chunks)
        
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}", exc_info=True)
        return 0


def cleanup_document(record: Dict[str, Any]) -> None:
    """
    Clean up vectors when a document is deleted.
    
    Args:
        record: S3 event record
    """
    try:
        # Extract S3 information
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"Cleaning up document: s3://{bucket}/{key}")
        
        # Generate document ID from key
        doc_id = generate_doc_id(key)
        
        # Delete all vectors for this document
        deleted_count = vector_store.delete_vectors_by_doc_id(doc_id)
        
        # Clean up processing status record
        # Note: We need user_id from metadata to clean up
        user_id = get_user_id_from_s3(bucket, key)
        if processing_status_manager and user_id:
            processing_status_manager.cleanup_old_records(user_id, doc_id)
        
        print(f"Deleted {deleted_count} vectors for document {doc_id}")
        
    except Exception as e:
        logger.error(f"Error cleaning up document: {str(e)}", exc_info=True)


def generate_doc_id(s3_key: str) -> str:
    """
    Generate a document ID from S3 key.
    
    Extracts the UUID from filenames like: uuid_filename.pdf
    
    Args:
        s3_key: S3 object key
        
    Returns:
        Document ID (UUID part if present, otherwise filename without extension)
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


def get_user_id_from_s3(bucket: str, key: str) -> Optional[str]:
    """
    Get user ID from S3 object metadata.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        User ID or None if not found
    """
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        metadata = response.get('Metadata', {})
        
        user_id = metadata.get('user-id')
        
        if user_id:
            print(f"Found user ID in metadata: {user_id}")
        else:
            print("No user ID found in object metadata")
        
        return user_id
            
    except Exception as e:
        logger.warning(f"Error getting metadata from S3: {str(e)}")
        return None
