"""
OCR Processing Module

This module provides functionality to perform OCR on images using Amazon Bedrock.
"""
import os
import logging
import json
import base64
import boto3
from typing import List, Dict, Tuple
from decimal import Decimal
from io import BytesIO
from PIL import Image
logger = logging.getLogger(__name__)


class OCRProcessor:
    """Perform OCR on images using Amazon Bedrock."""
    
    def __init__(self, region: str):
        """
        Initialize OCR processor.
        
        Args:
            region: AWS region for Bedrock service
        """
        self.logger = logging.getLogger(__name__)
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        # Use Claude 4.5 for OCR capabilities
        self.ocr_model_id = os.environ.get('OCR_MODEL_ID', 'global.anthropic.claude-sonnet-4-5-20250929-v1:0')
    
    def perform_ocr(self, image_data: bytes, image_format: str = "JPEG") -> str:
        """
        Perform OCR on an image using Bedrock.
        
        Args:
            image_data: Image bytes
            image_format: Image format (JPEG, PNG, etc.)
            
        Returns:
            Extracted text from the image
        """
        try:
            # Convert JPEG to PNG since Claude doesn't support JPEG
            image_data, image_format = self._convert_to_png_if_needed(image_data, image_format)
            
            # Convert image format to MIME type
            mime_type = self._get_mime_type(image_format)
            
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare request for Claude 4.5 Sonnet
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 8192,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": "Extract all text from this image. Return only the text content, without any additional commentary or formatting."
                            }
                        ]
                    }
                ]
            }
            
            # Invoke Bedrock model
            response = self.bedrock_runtime.invoke_model(
                modelId=self.ocr_model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract text from response
            if 'content' in response_body and len(response_body['content']) > 0:
                text = response_body['content'][0].get('text', '')
                self.logger.debug(f"OCR extracted {len(text)} characters")
                return text.strip()
            
            self.logger.warning("No text extracted from image")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error performing OCR: {str(e)}")
            # Return empty string on error to allow processing to continue
            return ""
    
    def process_images(self, images: List[bytes]) -> str:
        """
        Process multiple images and combine OCR results.
        
        Args:
            images: List of image data as bytes
            
        Returns:
            Combined OCR text from all images
        """
        ocr_texts = []
        
        for idx, image_data in enumerate(images):
            try:
                if not image_data:
                    self.logger.warning(f"Image {idx} has no data")
                    continue
                
                # Perform OCR (format detection is automatic in most cases)
                text = self.perform_ocr(image_data, "JPEG")
                
                if text:
                    ocr_texts.append(text)
                    self.logger.info(f"OCR successful for image {idx}")
                else:
                    self.logger.warning(f"No text extracted from image {idx}")
                    
            except Exception as e:
                self.logger.error(f"Error processing image {idx}: {str(e)}")
                continue
        
        # Combine all OCR texts
        combined_text = "\n\n".join(ocr_texts)
        self.logger.info(f"Combined OCR text: {len(combined_text)} characters from {len(ocr_texts)} images")
        
        return combined_text
    
    def _convert_to_png_if_needed(self, image_data: bytes, image_format: str) -> Tuple[bytes, str]:
        """
        Convert JPEG images to PNG format since Claude doesn't support JPEG.
        
        Args:
            image_data: Image bytes
            image_format: Current image format
            
        Returns:
            Tuple of (converted image bytes, new format)
        """
        try:
            # Check if conversion is needed
            if image_format.upper() in ["JPEG", "JPG", "JPEG2000"]:
                self.logger.debug(f"Converting {image_format} to PNG for Claude compatibility")
                
                # Open image with PIL
                image = Image.open(BytesIO(image_data))
                
                # Convert to RGB if necessary (some images might be in CMYK or other modes)
                if image.mode not in ('RGB', 'RGBA', 'L'):
                    image = image.convert('RGB')
                
                # Save as PNG
                output = BytesIO()
                image.save(output, format='PNG')
                png_data = output.getvalue()
                
                self.logger.debug(f"Converted image from {len(image_data)} bytes to {len(png_data)} bytes")
                return png_data, "PNG"
            
            # No conversion needed
            return image_data, image_format
            
        except Exception as e:
            self.logger.warning(f"Error converting image to PNG: {str(e)}, using original")
            return image_data, image_format
    
    def _get_mime_type(self, image_format: str) -> str:
        """
        Convert image format to MIME type.
        
        Args:
            image_format: Image format (JPEG, PNG, etc.)
            
        Returns:
            MIME type string
        """
        format_map = {
            "JPEG": "image/jpeg",
            "JPG": "image/jpeg",
            "PNG": "image/png",
            "GIF": "image/gif",
            "WEBP": "image/webp",
            "JPEG2000": "image/jpeg",
        }
        
        return format_map.get(image_format.upper(), "image/png")
