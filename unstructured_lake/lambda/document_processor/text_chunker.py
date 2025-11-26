"""
Text Chunking Module

This module provides functionality to split text into chunks with overlap
for optimal embedding generation and retrieval using LangChain's RecursiveCharacterTextSplitter.
"""
import logging
from typing import List, Dict
#from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class TextChunker:
    """Split text into chunks with configurable size and overlap using LangChain."""
    
    def __init__(self, chunk_size: int = 5000, chunk_overlap: int = 819):
        """
        Initialize text chunker with LangChain's RecursiveCharacterTextSplitter.
        
        Args:
            chunk_size: Maximum number of characters per chunk (default: 5000)
            chunk_overlap: Number of characters to overlap between chunks (default: 819)
        """
        self.logger = logging.getLogger(__name__)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize LangChain's RecursiveCharacterTextSplitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
    
    def chunk_text(
        self,
        text: str,
        page_range: str,
        doc_id: str
    ) -> List[Dict[str, any]]:
        """
        Split text into chunks with overlap and metadata using LangChain.
        
        Args:
            text: Text to chunk
            page_range: Page range for this text (e.g., "1-10")
            doc_id: Document identifier
            
        Returns:
            List of chunk dictionaries:
            [
                {
                    "text": "chunk text...",
                    "metadata": {
                        "docId": "doc-id",
                        "pageRange": "1-10",
                        "chunkIndex": 0
                    }
                },
                ...
            ]
        """
        if not text or not text.strip():
            self.logger.warning("Empty text provided for chunking")
            return []
        
        # Use LangChain's RecursiveCharacterTextSplitter
        chunks = self.text_splitter.split_text(text)
        
        # Add metadata to each chunk
        chunk_dicts = []
        for idx, chunk_text in enumerate(chunks):
            chunk_dicts.append({
                "text": chunk_text,
                "metadata": {
                    "docId": doc_id,
                    "pageRange": page_range,
                    "chunkIndex": idx
                }
            })
        
        self.logger.info(
            f"Created {len(chunk_dicts)} chunks from {len(text)} characters "
            f"(page range: {page_range})"
        )
        
        return chunk_dicts
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate the number of tokens in text.
        
        This is a rough approximation: 1 token ≈ 4 characters.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
