"""LLM service for interacting with various LLM providers."""

import asyncio
import aiohttp
import logging
from typing import Optional, Union, List, Dict
import json
import backoff

from config import Config  # Changed from ..config
from constants import LLMProvider, DEFAULT_TIMEOUT, MAX_RETRIES, API_RATE_LIMIT_DELAY  # Changed from ..constants
from utils.json_sanitizer import KatalonJSONSanitizer  # Changed from ..utils

logger = logging.getLogger(__name__)

class LLMHandler:
    """Base class for LLM API interactions."""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
    
    async def call_api(self, session: aiohttp.ClientSession, prompt: str) -> Optional[str]:
        """Abstract method for API calls."""
        raise NotImplementedError

class GeminiHandler(LLMHandler):
    """Google Gemini API handler."""
    
    async def call_api(self, session: aiohttp.ClientSession, prompt: str) -> Optional[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            async with session.post(url, headers=headers, params=params, json=data, timeout=DEFAULT_TIMEOUT) as response:
                response.raise_for_status()
                result = await response.json()
                
                if 'candidates' not in result or not result['candidates']:
                    logger.error("No candidates in Gemini response")
                    return None
                
                return result['candidates'][0]['content']['parts'][0]['text']
                
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

class OpenAIHandler(LLMHandler):
    """OpenAI API handler."""
    
    async def call_api(self, session: aiohttp.ClientSession, prompt: str) -> Optional[str]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            async with session.post(url, headers=headers, json=data, timeout=DEFAULT_TIMEOUT) as response:
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content']
                
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None

class LLMService:
    """Main service for LLM interactions with retry logic."""
    
    def __init__(self, config: Config):
        self.config = config
        self.handler = self._create_handler()
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)
    
    def _create_handler(self) -> LLMHandler:
        """Create appropriate LLM handler based on provider."""
        provider = LLMProvider(self.config.llm3_provider)
        
        if provider == LLMProvider.GEMINI:
            return GeminiHandler(self.config.llm3_api_key, self.config.llm3_model)
        elif provider == LLMProvider.OPENAI:
            return OpenAIHandler(self.config.llm3_api_key, self.config.llm3_model)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    @backoff.on_exception(backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=MAX_RETRIES)
    async def call_llm(self, prompt: str, expect_json: bool = True) -> Optional[Union[List[Dict], Dict, str]]:
        """Call LLM with retry logic and rate limiting."""
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                content = await self.handler.call_api(session, prompt)
                
                if content:
                    if expect_json:
                        sanitized = KatalonJSONSanitizer.sanitize(content)
                        if sanitized:
                            try:
                                return json.loads(sanitized)
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse sanitized JSON: {e}")
                    else:
                        return content
                
                await asyncio.sleep(API_RATE_LIMIT_DELAY)
                return None
            

            