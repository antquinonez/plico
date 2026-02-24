import json
import re
from typing import Optional, Any, Dict, List, Union
from enum import Enum

class ResponseFormat(Enum):
    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"
    MARKDOWN = "markdown"

class ResponseProcessor:
    def __init__(self):
        self._extractors: Dict[str, callable] = {
            'json': self._extract_json,
            'code': self._extract_code_blocks,
            'thinking': self._extract_thinking_blocks
        }
        self._validators: Dict[ResponseFormat, callable] = {}
        self._transformers: List[callable] = []
    
    def process_response(self, 
                        response: str, 
                        expected_format: ResponseFormat = ResponseFormat.TEXT,
                        extract: Optional[List[str]] = None) -> Any:
        """Main processing pipeline"""
        # Clean basic issues
        cleaned = self._clean_base(response)
        
        # Extract requested elements
        if extract:
            for extractor_name in extract:
                if extractor_name in self._extractors:
                    cleaned = self._extractors[extractor_name](cleaned)
        
        # Validate format
        if expected_format in self._validators:
            if not self._validators[expected_format](cleaned):
                raise ValueError(f"Response doesn't match expected format: {expected_format}")
        
        # Apply transformers
        for transformer in self._transformers:
            cleaned = transformer(cleaned)
        
        return cleaned
    
    def _clean_base(self, response: str) -> str:
        """Remove common unwanted elements"""
        # Remove think tags
        response = re.sub(r'<think>[\s\S]*?</think>', '', response)
        # Remove excess whitespace
        response = re.sub(r'\s+', ' ', response)
        return response.strip()
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Enhanced JSON extraction with multiple strategies"""
        strategies = [
            self._extract_json_from_markdown,
            self._extract_json_from_raw,
            self._extract_json_fuzzy
        ]
        
        for strategy in strategies:
            result = strategy(text)
            if result is not None:
                return result
        return None
    
    def _extract_code_blocks(self, text: str) -> Dict[str, str]:
        """Extract all code blocks by language"""
        pattern = r'```(\w+)?\n([\s\S]*?)\n```'
        blocks = {}
        for match in re.finditer(pattern, text):
            lang = match.group(1) or 'unknown'
            code = match.group(2)
            if lang not in blocks:
                blocks[lang] = []
            blocks[lang].append(code)
        return blocks
    
    def register_validator(self, format: ResponseFormat, validator: callable) -> None:
        """Register a custom validator for a response format"""
        self._validators[format] = validator
    
    def register_transformer(self, transformer: callable) -> None:
        """Register a custom transformer"""
        self._transformers.append(transformer)