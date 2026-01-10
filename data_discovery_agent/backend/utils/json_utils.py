"""
JSON utility functions for parsing, fixing, and extracting data from JSON strings.
This module contains common JSON processing utilities used across the system.
"""

import json
import re
import logging
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)


def extract_and_fix_json(text: str) -> Optional[Dict]:
    """
    Extract and fix JSON from text with better error handling.
    
    Args:
        text: Text containing JSON data
        
    Returns:
        Parsed JSON dictionary or None if parsing fails
    """
    try:
        # Find the first '{' and the last '}'
        start_index = text.find('{')
        end_index = text.rfind('}') + 1
        
        if start_index == -1 or end_index == 0:
            logger.warning("No JSON object found in text")
            return None
        
        # Extract the JSON string
        json_str = text[start_index:end_index]
        logger.debug(f"Extracted JSON string of length {len(json_str)}")
        
        # Try to parse directly first
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.info("Direct JSON parsing failed, attempting fixes")
        
        # Apply fixes for common JSON issues
        fixed_json = _apply_json_fixes(json_str)
        
        try:
            return json.loads(fixed_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed even after fixes: {e}")
            logger.debug(f"Problematic JSON: {fixed_json[:200]}...")
            return None
            
    except Exception as e:
        logger.error(f"Unexpected error in JSON extraction: {e}")
        return None


def _apply_json_fixes(json_str: str) -> str:
    """
    Apply common JSON fixes to malformed JSON strings.
    
    Args:
        json_str: JSON string that may have formatting issues
        
    Returns:
        Fixed JSON string
    """
    # Remove control characters
    cleaned = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
    
    # Fix trailing commas
    lines = cleaned.split('\n')
    for i in range(len(lines)):
        if i < len(lines) - 1 and (']' in lines[i+1] or '}' in lines[i+1]):
            lines[i] = lines[i].rstrip(',')
    
    return '\n'.join(lines)


def extract_and_merge_json(text: str) -> Dict[str, Any]:
    """
    Extract multiple JSON objects from text and merge them.
    
    Args:
        text: Text containing multiple JSON objects
        
    Returns:
        Merged JSON dictionary
    """
    # Find all JSON objects in the text
    json_pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}')
    json_matches = json_pattern.findall(text)
    
    # Parse each JSON object
    parsed_jsons = []
    for json_str in json_matches:
        try:
            parsed_json = json.loads(json_str)
            parsed_jsons.append(parsed_json)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON: {json_str[:50]}...")
    
    # Merge JSONs with the same keys
    merged_json = {}
    for parsed_json in parsed_jsons:
        for key, value in parsed_json.items():
            if key in merged_json and isinstance(value, list) and isinstance(merged_json[key], list):
                # If both are lists, extend the existing list
                merged_json[key].extend(value)
            else:
                # Otherwise, just set or overwrite the value
                merged_json[key] = value
    
    return merged_json


def get_json_key(input_str_or_json: Union[str, Dict], key: str) -> Any:
    """
    Extract a specific key from JSON data (string or dict).
    
    Args:
        input_str_or_json: JSON string or dictionary
        key: Key to extract
        
    Returns:
        Value associated with the key, or None if not found
    """
    try:
        if isinstance(input_str_or_json, dict):
            return input_str_or_json.get(key)  # Use .get() instead of [] to avoid KeyError
        elif isinstance(input_str_or_json, str):
            # Try to parse as JSON first
            try:
                json_obj = json.loads(input_str_or_json)
                return json_obj.get(key)
            except json.JSONDecodeError:
                # Fall back to string parsing only if the key exists in the string
                if key in input_str_or_json:
                    logger.info(f"Attempting to extract key '{key}' from string using split method")
                    try:
                        return input_str_or_json.split(f"{key}")[1].split(":")[1].split(",")[0].replace('"', '').strip()
                    except (IndexError, AttributeError):
                        logger.warning(f"Failed to extract key '{key}' using string parsing")
                        return None
                else:
                    logger.debug(f"Key '{key}' not found in string")
                    return None
        else:
            logger.warning(f"Unable to extract key '{key}' from {type(input_str_or_json)}")
            return None
    except Exception as e:
        logger.error(f"Error extracting key '{key}' from input: {e}")
        logger.debug(f"Input data: {input_str_or_json[:200]}..." if isinstance(input_str_or_json, str) else str(input_str_or_json))
        return None