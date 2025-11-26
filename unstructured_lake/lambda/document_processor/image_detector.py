"""
Image Detection Module

This module provides functionality to detect images in PDF pages.
"""
import logging
from typing import List, Dict
from io import BytesIO
from pypdf import PdfReader
from decimal import Decimal
logger = logging.getLogger(__name__)


class ImageDetector:
    """Detect images in PDF pages."""
    
    def __init__(self):
        """Initialize image detector."""
        self.logger = logging.getLogger(__name__)
    
    def has_images(self, pdf_bytes: bytes, page_num: int) -> bool:
        """
        Check if a PDF page contains images.
        
        Args:
            pdf_bytes: PDF file content as bytes
            page_num: Page number (0-indexed)
            
        Returns:
            True if page contains images, False otherwise
        """
        try:
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            
            if page_num >= len(reader.pages):
                self.logger.warning(f"Page {page_num} does not exist")
                return False
            
            page = reader.pages[page_num]
            
            # Use pypdf's built-in images property
            has_imgs = len(page.images) > 0
            if has_imgs:
                self.logger.debug(f"Page {page_num} contains {len(page.images)} images")
            
            return has_imgs
            
        except Exception as e:
            self.logger.warning(f"Error detecting images on page {page_num}: {str(e)}")
            return False
    
    def extract_images(self, pdf_bytes: bytes, page_num: int) -> List[bytes]:
        """
        Extract images from a PDF page.
        
        Args:
            pdf_bytes: PDF file content as bytes
            page_num: Page number (0-indexed)
            
        Returns:
            List of image data as bytes (ready for OCR processing)
        """
        images = []
        
        try:
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            
            if page_num >= len(reader.pages):
                self.logger.warning(f"Page {page_num} does not exist")
                return images
            
            page = reader.pages[page_num]
            
            # Use pypdf's built-in images property
            for image_file_object in page.images:
                try:
                    # Get image data directly
                    image_data = image_file_object.data
                    images.append(image_data)
                    
                    self.logger.debug(
                        f"Extracted image from page {page_num}, size: {len(image_data)} bytes"
                    )
                    
                except Exception as e:
                    self.logger.warning(
                        f"Error extracting image from page {page_num}: {str(e)}"
                    )
            
            self.logger.info(f"Extracted {len(images)} images from page {page_num}")
            return images
            
        except Exception as e:
            self.logger.error(f"Error extracting images from page {page_num}: {str(e)}")
            return images
