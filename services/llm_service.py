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
    
    async def call_api(self, session: aiohttp.ClientSession, prompt: str, response_format: Optional[Dict] = None) -> Optional[str]:
        """Abstract method for API calls."""
        raise NotImplementedError

class GeminiHandler(LLMHandler):
    """Google Gemini API handler."""
    
    async def call_api(self, session: aiohttp.ClientSession, prompt: str, response_format: Optional[Dict] = None) -> Optional[str]:
        url = f"https://generativelanguage.googleapis.com/v1/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        
        # Add JSON formatting instructions to the prompt if needed
        if response_format and response_format.get("type") == "json_object":
            prompt = f"{prompt}\n\nIMPORTANT: Your response must be a valid JSON object. Do not include any text before or after the JSON."
        
        # Split prompt if it's too long (Gemini has an 8k token limit)
        # For comparison tasks, we'll focus on the essential parts
        if len(prompt) > 200000:  # Approximate character limit
            logger.warning("Prompt too long for Gemini, truncating...")
            # Keep the instructions and format the data sections more concisely
            prompt_parts = prompt.split("Below are the complete baseline")
            if len(prompt_parts) > 1:
                instructions = prompt_parts[0]
                data_section = prompt_parts[1]
                
                # Truncate the data sections while keeping structure
                try:
                    # Extract and summarize the JSON data
                    import re
                    baseline_json = re.search(r'Baseline Dataset \(LL1\):\s*(.*?)\s*Target Dataset', data_section, re.DOTALL)
                    target_json = re.search(r'Target Dataset \(LL2\):\s*(.*?)\s*Please evaluate', data_section, re.DOTALL)
                    
                    if baseline_json and target_json:
                        # Load and summarize the JSON data
                        baseline_data = json.loads(baseline_json.group(1))
                        target_data = json.loads(target_json.group(1))
                        
                        # Create a summary of the data
                        baseline_summary = {
                            "metadata": baseline_data.get("metadata", {}),
                            "total_results": len(baseline_data.get("results", {})),
                            "sample_results": dict(list(baseline_data.get("results", {}).items())[:3])
                        }
                        
                        target_summary = {
                            "metadata": target_data.get("metadata", {}),
                            "total_results": len(target_data.get("results", {})),
                            "sample_results": dict(list(target_data.get("results", {}).items())[:3])
                        }
                        
                        # Reconstruct the prompt with summarized data
                        prompt = f"{instructions}\nBelow are summarized baseline and target datasets:\n\n"
                        prompt += f"Baseline Dataset (LL1) Summary:\n{json.dumps(baseline_summary, indent=2)}\n\n"
                        prompt += f"Target Dataset (LL2) Summary:\n{json.dumps(target_summary, indent=2)}\n\n"
                        prompt += "Please evaluate based on these samples and summaries.\n\n"
                        prompt += prompt_parts[1].split("Please evaluate", 1)[1]
                except Exception as e:
                    logger.error(f"Error processing large prompt: {e}")
                    # If processing fails, use a simpler truncation
                    prompt = instructions + "\n[Data truncated due to length]\n" + prompt_parts[1].split("Please evaluate", 1)[1]
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,  # Lower temperature for more consistent outputs
                "topP": 0.8,
                "topK": 40
            }
        }
        
        try:
            async with session.post(url, headers=headers, params=params, json=data, timeout=DEFAULT_TIMEOUT) as response:
                if response.status != 200:
                    error_body = await response.text()
                    logger.error(f"Gemini API error: {response.status}, message='{error_body}', url='{response.url}'")
                    return None
                    
                result = await response.json()
                
                if 'candidates' not in result or not result['candidates']:
                    logger.error("No candidates in Gemini response")
                    return None
                
                content = result['candidates'][0]['content']['parts'][0]['text']
                
                # Clean up the response if it's supposed to be JSON
                if response_format and response_format.get("type") == "json_object":
                    # Remove any text before and after the JSON object
                    content = content.strip()
                    start_idx = content.find("{")
                    end_idx = content.rfind("}") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        content = content[start_idx:end_idx]
                
                return content
                
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

class OpenAIHandler(LLMHandler):
    """OpenAI API handler."""
    
    async def call_api(self, session: aiohttp.ClientSession, prompt: str, response_format: Optional[Dict] = None) -> Optional[str]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        # Add response format if specified
        if response_format:
            data["response_format"] = response_format
        
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
    async def call_llm(self, prompt: str, response_format: Optional[Dict] = None, expect_json: bool = True) -> Optional[Union[List[Dict], Dict, str]]:
        """Call LLM with retry logic and rate limiting."""
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                content = await self.handler.call_api(session, prompt, response_format)
                
                if content:
                    if expect_json:
                        try:
                            # First try direct JSON parsing
                            return json.loads(content)
                        except json.JSONDecodeError:
                            # If that fails, try sanitizing
                            sanitized = KatalonJSONSanitizer.sanitize(content)
                            if sanitized:
                                try:
                                    return json.loads(sanitized)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse sanitized JSON: {e}")
                                    logger.error(f"Raw content: {content}")
                    else:
                        return content
                
                await asyncio.sleep(API_RATE_LIMIT_DELAY)
                return None
            

            