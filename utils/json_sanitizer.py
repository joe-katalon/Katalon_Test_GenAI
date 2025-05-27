"""JSON sanitization utilities for Katalon Studio responses."""

import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class KatalonJSONSanitizer:
    """Handles JSON content sanitization for Katalon Studio responses."""
    
    CODE_BLOCK_PATTERN = re.compile(r'```(?:json|groovy|java)?\n?|```')
    
    @classmethod
    def sanitize(cls, content: str) -> Optional[str]:
        """Sanitize and validate JSON content with Katalon-specific handling."""
        if not isinstance(content, str) or not content.strip():
            logger.error("Invalid content for sanitization")
            return None
        
        # Remove code block markers
        content = cls.CODE_BLOCK_PATTERN.sub('', content).strip()
        
        # Try different approaches to parse the JSON
        
        # Approach 1: Direct parsing
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        
        # Approach 2: Extract array
        try:
            start = content.find("[")
            end = content.rfind("]") + 1
            
            if start != -1 and end > 0:
                json_str = content[start:end]
                parsed = json.loads(json_str)
                return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        
        # Approach 3: Extract object
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            
            if start != -1 and end > 0:
                json_str = content[start:end]
                parsed = json.loads(json_str)
                return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        
        # Approach 4: Manual sanitization
        try:
            start = content.find("[") if "[" in content else content.find("{")
            end = content.rfind("]") + 1 if "[" in content else content.rfind("}") + 1
            
            if start == -1 or end == 0:
                logger.error("No valid JSON structure found")
                return None
            
            json_str = content[start:end]
            
            # Common replacements
            json_str = json_str.replace("'", '"')
            json_str = json_str.replace('None', 'null')
            json_str = json_str.replace('True', 'true')
            json_str = json_str.replace('False', 'false')
            
            parsed = json.loads(json_str)
            return json.dumps(parsed, ensure_ascii=False)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON validation failed after all attempts: {e}")
            logger.debug(f"Content sample: {content[:200]}...")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in sanitization: {e}")
            return None