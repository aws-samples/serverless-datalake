"""
PDF Text Extraction Module

This module provides functionality to extract text from PDF documents using pypdf.
Handles pages with and without text content.
"""
import logging
from typing import List, Dict
from io import BytesIO
from pypdf import PdfReader
from decimal import Decimal
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF documents."""
    
    def __init__(self):
        """Initialize PDF extractor."""
        self.logger = logging.getLogger(__name__)
    
    def extract_text_from_pdf(self, pdf_bytes: bytes) -> List[Dict[str, any]]:
        """
        Extract text from all pages of a PDF document.
        
        Args:
            pdf_bytes: PDF file content as bytes
            
        Returns:
            List of dictionaries containing page number and extracted text:
            [
                {"page": 1, "text": "Page 1 content..."},
                {"page": 2, "text": "Page 2 content..."},
                ...
            ]
            
        Raises:
            ValueError: If PDF is invalid or cannot be read
        """
        try:
            # Create PDF reader from bytes
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            
            total_pages = len(reader.pages)
            print(f"PDF has {total_pages} pages")
            
            # Extract text from each page
            page_texts = []
            for page_num in range(total_pages):
                page = reader.pages[page_num]
                text = self._extract_page_text(page, page_num + 1)
                
                page_texts.append({
                    "page": page_num + 1,
                    "text": text
                })
            
            return page_texts
            
        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {str(e)}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    
    def _extract_page_text(self, page, page_num: int) -> str:
        """
        Extract text from a single PDF page.
        
        Args:
            page: PyPDF2 page object
            page_num: Page number (1-indexed)
            
        Returns:
            Extracted text from the page (empty string if no text)
        """
        try:
            text = page.extract_text()
            
            # Handle pages with no text content
            if not text or text.strip() == "":
                self.logger.debug(f"Page {page_num} has no text content")
                return ""
            
            # Clean up text
            text = text.strip()
            
            self.logger.debug(f"Extracted {len(text)} characters from page {page_num}")
            return text
            
        except Exception as e:
            self.logger.warning(f"Error extracting text from page {page_num}: {str(e)}")
            return ""
    
    def get_page_count(self, pdf_bytes: bytes) -> int:
        """
        Get the total number of pages in a PDF document.
        
        Args:
            pdf_bytes: PDF file content as bytes
            
        Returns:
            Total number of pages
            
        Raises:
            ValueError: If PDF is invalid or cannot be read
        """
        try:
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            return len(reader.pages)
        except Exception as e:
            self.logger.error(f"Error getting page count: {str(e)}")
            raise ValueError(f"Failed to read PDF: {str(e)}")
    
    def has_text_content(self, page_text: str) -> bool:
        """
        Check if a page has meaningful text content.
        
        Args:
            page_text: Extracted text from a page
            
        Returns:
            True if page has text content, False otherwise
        """
        return bool(page_text and page_text.strip())
