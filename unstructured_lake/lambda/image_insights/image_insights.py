"""
Image Insights Lambda Handler

Handles HTTP API requests for image analysis:
- POST /image-insights/analyze - Analyze image with Claude vision model
"""
import os
import logging
import json
import base64
import boto3
from typing import Dict, Any, List, Optional, Tuple
from botocore.exceptions import ClientError
from decimal import Decimal
from io import BytesIO

# Try importing PIL for image processing
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
    print(f"PIL.__version__ {Image.__version__ if hasattr(Image, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"PIL import failed: {e}")
    PILLOW_AVAILABLE = False

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
REGION = os.environ.get('REGION', 'us-east-1')
VISION_MODEL_ID = os.environ.get('VISION_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')

# Initialize AWS clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name=REGION)


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
    Lambda handler for image insights API requests.
    
    Handles:
    - POST /image-insights/analyze - Analyze image with Claude
    
    Args:
        event: API Gateway proxy event
        context: Lambda context
        
    Returns:
        API Gateway response dictionary
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")

    try:
        # Extract HTTP method and path
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'POST'))
        path = event.get('path', event.get('rawPath', ''))
        
        logger.info(f"Processing {http_method} {path}")
        
        # Route to appropriate handler
        if http_method == 'POST' and path == '/image-insights/analyze':
            return handle_analyze_image(event)
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


def handle_analyze_image(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /image-insights/analyze request.
    
    Analyzes an image using Claude vision model to:
    1. Validate the image
    2. Extract key insights (Name, Age, etc.)
    3. Detect potential forgery or deepfakes
    4. Detect QR codes with bounding boxes
    
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
        
        image_base64 = body.get('image')
        prompt = body.get('prompt', '')
        
        # Validate input
        if not image_base64:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'image (base64) is required'})
            }
        
        logger.info(f"Analyzing image for user: {user_id}")
        
        # Analyze image with Claude
        analysis_result = analyze_image_with_claude(image_base64, prompt)
        
        # If QR code detected, crop and return the QR code image
        if analysis_result.get('qr_code_detected') and analysis_result.get('qr_bounding_box'):
            qr_image_base64 = crop_qr_code_image(image_base64, analysis_result['qr_bounding_box'])
            if qr_image_base64:
                analysis_result['qr_code_image'] = qr_image_base64
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(analysis_result, cls=CustomJsonEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing image: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Failed to analyze image'})
        }


def analyze_image_with_claude(image_base64: str, user_prompt: str = '') -> Dict[str, Any]:
    """
    Analyze image using Claude vision model.
    
    Args:
        image_base64: Base64 encoded image
        user_prompt: Optional user-provided prompt for additional analysis
        
    Returns:
        Dictionary with analysis results
    """
    try:
        # Remove data URL prefix if present
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        
        # Build the prompt
        system_prompt = """You are an expert image analyst. Analyze the provided image and return a JSON response with the following structure:

{
  "is_valid_image": true/false,
  "validation_message": "Brief explanation of validity",
  "key_insights": {
    "name": "Extracted name if visible, otherwise null",
    "age": "Estimated age or age range if person visible, otherwise null",
    "document_type": "Type of document if applicable (ID, passport, etc.)",
    "other_details": ["List of other notable details"]
  },
  "forgery_detection": {
    "suspicious": true/false,
    "confidence": 0.0-1.0,
    "indicators": ["List of forgery indicators if any"]
  },
  "qr_code_detected": true/false,
  "qr_code_data": "Decoded QR code content if readable, otherwise null",
  "qr_bounding_box": {
    "x": 0,
    "y": 0,
    "width": 0,
    "height": 0
  }
}

IMPORTANT INSTRUCTIONS:
- Be thorough but concise in your analysis
- For QR codes: If detected, try to read the QR code content and include it in qr_code_data. Also provide pixel coordinates relative to the image dimensions in qr_bounding_box. The bounding box should tightly fit the QR code.
- If no QR code is detected, set qr_code_detected to false, qr_code_data to null, and qr_bounding_box to null
- For forgery detection: Look for inconsistencies in lighting, shadows, edges, text alignment, or digital artifacts
- Confidence should be between 0.0 (no confidence) and 1.0 (very confident)

CRITICAL: Return ONLY valid JSON in the exact structure shown above, with no additional text before or after the JSON.

JSON Response:"""

        if user_prompt:
            system_prompt += f"\n\nAdditional user request: {user_prompt}"
        
        # Prepare the request
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": system_prompt
                        }
                    ]
                }
            ]
        }
        
        # Invoke Bedrock
        logger.info(f"Invoking Claude vision model: {VISION_MODEL_ID}")
        response = bedrock_runtime.invoke_model(
            modelId=VISION_MODEL_ID,
            body=json.dumps(request_body)
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        logger.info(f"Claude response: {json.dumps(response_body, default=str)}")
        
        # Extract the text content
        content = response_body.get('content', [])
        if not content:
            raise ValueError("No content in Claude response")
        
        # Get the text from the first content block
        text_content = content[0].get('text', '')
        
        # Try to parse as JSON (following insight_generator.py pattern)
        try:
            # Try to extract JSON from response
            # Sometimes models include extra text before/after JSON
            json_start = text_content.find('{')
            json_end = text_content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                # No JSON found - return raw response wrapped
                logger.warning("No JSON found in Claude response, wrapping in structure")
                analysis_result = _wrap_raw_response(text_content)
            else:
                json_text = text_content[json_start:json_end]
                
                # Parse JSON
                analysis_result = json.loads(json_text)
                
                # Validate and add defaults for missing fields
                if 'is_valid_image' not in analysis_result:
                    analysis_result['is_valid_image'] = True
                if 'validation_message' not in analysis_result:
                    analysis_result['validation_message'] = "Analysis completed"
                if 'key_insights' not in analysis_result:
                    analysis_result['key_insights'] = {}
                if 'forgery_detection' not in analysis_result:
                    analysis_result['forgery_detection'] = {
                        "suspicious": False,
                        "confidence": 0.0,
                        "indicators": []
                    }
                if 'qr_code_detected' not in analysis_result:
                    analysis_result['qr_code_detected'] = False
                if 'qr_code_data' not in analysis_result:
                    analysis_result['qr_code_data'] = None
                if 'qr_bounding_box' not in analysis_result:
                    analysis_result['qr_bounding_box'] = None
                    
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed, wrapping raw response: {str(e)}")
            logger.debug(f"Response text: {text_content[:500]}")
            analysis_result = _wrap_raw_response(text_content)
        
        return analysis_result
        
    except ClientError as e:
        logger.error(f"Bedrock API error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error analyzing image with Claude: {str(e)}", exc_info=True)
        raise


def crop_qr_code_image(image_base64: str, bounding_box: Optional[Dict[str, int]]) -> Optional[str]:
    """
    Crop QR code region from image and return as base64.
    
    Args:
        image_base64: Base64 encoded image
        bounding_box: Dictionary with x, y, width, height for cropping
        
    Returns:
        Base64 encoded cropped QR code image or None
    """
    if not PILLOW_AVAILABLE:
        logger.warning("Pillow not available, cannot crop QR code")
        return None
    
    try:
        # Remove data URL prefix if present
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        
        # Decode base64 to image
        image_data = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_data))
        
        # Validate and crop to bounding box
        if bounding_box and all(k in bounding_box for k in ['x', 'y', 'width', 'height']):
            x = int(bounding_box['x'])
            y = int(bounding_box['y'])
            width = int(bounding_box['width'])
            height = int(bounding_box['height'])
            
            # Validate bounding box is within image dimensions
            img_width, img_height = image.size
            if x >= 0 and y >= 0 and (x + width) <= img_width and (y + height) <= img_height:
                # Add some padding around the QR code (10% on each side)
                padding = int(min(width, height) * 0.1)
                x = max(0, x - padding)
                y = max(0, y - padding)
                width = min(img_width - x, width + 2 * padding)
                height = min(img_height - y, height + 2 * padding)
                
                # Crop the image to the bounding box
                cropped_image = image.crop((x, y, x + width, y + height))
                logger.info(f"Cropped QR code image: ({x}, {y}, {width}, {height})")
                
                # Convert cropped image to base64
                buffer = BytesIO()
                cropped_image.save(buffer, format='PNG')
                cropped_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                return cropped_base64
            else:
                logger.warning(f"Invalid bounding box coordinates: ({x}, {y}, {width}, {height}) for image size ({img_width}, {img_height})")
                return None
        else:
            logger.warning("Invalid or missing bounding box")
            return None
        
    except Exception as e:
        logger.error(f"Error cropping QR code image: {str(e)}", exc_info=True)
        return None


def _wrap_raw_response(response_text: str) -> Dict[str, Any]:
    """
    Wrap raw (non-JSON) response in a structured format.
    This handles cases where Claude doesn't return valid JSON.
    
    Args:
        response_text: Raw response text from Claude
        
    Returns:
        Structured dictionary with raw response
    """
    return {
        "is_valid_image": True,
        "validation_message": "Analysis completed (raw response)",
        "key_insights": {
            "raw_analysis": response_text
        },
        "forgery_detection": {
            "suspicious": False,
            "confidence": 0.0,
            "indicators": []
        },
        "qr_code_detected": False,
        "qr_bounding_box": None,
        "raw_response": response_text
    }


def get_user_id_from_event(event: Dict[str, Any]) -> Optional[str]:
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
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }
