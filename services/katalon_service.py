"""Katalon Studio API service with multi-LLM support."""

import json
import requests
import logging
import time
from typing import Dict, Optional
from abc import ABC, abstractmethod

from config import Config
from constants import FEATURE_CONFIGS, DEFAULT_TIMEOUT, LLMConfigType, FEATURE_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class LLMAPIHandler(ABC):
    """Abstract base class for LLM API handlers."""
    
    @abstractmethod
    def call_api(self, feature: str, prompt: str, config: Dict) -> Dict:
        """Call the LLM API."""
        pass
    
    @abstractmethod
    def get_handler_info(self) -> Dict:
        """Get handler information for logging."""
        pass


class KatalonAIHandler(LLMAPIHandler):
    """Handler for Katalon AI service."""
    
    def __init__(self, session: requests.Session, katalon_config: Config):
        self.session = session
        self.config = katalon_config
        self.api_url = katalon_config.katalon_api_url
        logger.info(f"Initialized KatalonAIHandler with URL: {self.api_url}")
    
    def get_handler_info(self) -> Dict:
        return {
            "type": "katalon_ai",
            "api_url": self.api_url,
            "model": "studio-g4 (Katalon's internal model)"
        }
    
    def call_api(self, feature: str, prompt: str, config: Dict) -> Dict:
        """Call Katalon AI API."""
        logger.info(f"🔷 KatalonAI API Call - Feature: {feature}")
        logger.debug(f"Using Katalon AI service at: {self.api_url}")
        
        if feature == "chat_window":
            return self._handle_chat_window(prompt, config)
        
        # Standard generate/explain code
        payload = {
            "prompt": {
                "chat_completion": {
                    "config": {
                        "id": "studio-g4",  # Katalon's internal config
                        "inputParameters": {"user_input": prompt},
                        "promptId": FEATURE_CONFIGS[feature]["prompt_id"],
                        "feature": feature
                    }
                }
            }
        }
        
        logger.debug(f"Katalon AI Request payload: {json.dumps(payload, indent=2)[:500]}...")
        
        try:
            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=DEFAULT_TIMEOUT
            )
            logger.info(f"Katalon AI Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            
            output = result["response"]["chatCompletion"]["choices"][0]["message"]["content"]
            logger.debug(f"Katalon AI Output length: {len(output)} characters")
            
            return {
                "api_input": payload["prompt"]["chat_completion"]["config"],
                "api_output": output,
                "gui_output": self._format_gui_output(feature, output),
                "full_response": result,
                "api_handler": "katalon_ai"
            }
            
        except Exception as e:
            logger.error(f"Katalon AI API error: {e}")
            return {"error": str(e)}
    
    def _handle_chat_window(self, prompt: str, config: Dict) -> Dict:
        """Handle chat_window with two-step process."""
        logger.info("🔷 KatalonAI Chat Job API Call")
        chat_jobs_url = "https://katalon-api.katalon.com/v1/llm/chatJobs"
        
        # Get headers with additional IDs
        headers = self.session.headers.copy()
        headers.update({
            "X-Account-Id": getattr(self.config, 'account_id', '1410137'),
            "X-Organization-Id": getattr(self.config, 'organization_id', '1666289'),
            "X-User-Id": getattr(self.config, 'user_id_numeric', '12539647')
        })
        
        payload = {
            "orgId": int(headers.get("X-Organization-Id", "1666289")),
            "accountId": int(headers.get("X-Account-Id", "1410137")),
            "userId": int(headers.get("X-User-Id", "12539647")),
            "messages": [
                {
                    "request": {
                        "finalInput": prompt,
                        "attachments": None
                    },
                    "response": None
                }
            ]
        }
        
        try:
            logger.info(f"Submitting chat job to: {chat_jobs_url}")
            response = self.session.post(
                chat_jobs_url,
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            job_data = response.json()
            
            chat_job_id = job_data.get("chatJobId")
            if not chat_job_id:
                raise ValueError("No chatJobId in response")
            
            logger.info(f"Chat job submitted: {chat_job_id}")
            
            # Step 2: Poll for completion
            poll_url = f"{chat_jobs_url}/{chat_job_id}"
            max_attempts = 30
            poll_interval = 1
            
            for attempt in range(max_attempts):
                time.sleep(poll_interval)
                
                poll_response = self.session.get(
                    poll_url,
                    headers=headers,
                    timeout=DEFAULT_TIMEOUT
                )
                poll_response.raise_for_status()
                poll_data = poll_response.json()
                
                status = poll_data.get("status")
                logger.debug(f"Poll attempt {attempt + 1}: Status = {status}")
                
                if status == "COMPLETED":
                    answer = poll_data.get("answer", {}).get("finalAnswer", "")
                    logger.info(f"Chat job completed. Answer length: {len(answer)}")
                    
                    return {
                        "api_input": {
                            "prompt": prompt,
                            "chatJobId": chat_job_id,
                            "api_type": "katalon_ai_chat"
                        },
                        "api_output": answer,
                        "gui_output": "Response shown in StudioAssist chat window",
                        "full_response": poll_data,
                        "api_handler": "katalon_ai_chat"
                    }
                elif status in ["FAILED", "ERROR"]:
                    error_msg = poll_data.get("error", "Chat job failed")
                    logger.error(f"Chat job failed: {error_msg}")
                    return {"error": f"Chat job failed: {error_msg}"}
            
            logger.error(f"Chat job timed out after {max_attempts} seconds")
            return {"error": f"Chat job timed out (status: {status})"}
            
        except Exception as e:
            logger.error(f"Chat API request failed: {e}")
            return {"error": str(e)}
    
    def _format_gui_output(self, feature: str, output: str) -> str:
        """Format output based on feature type."""
        if feature == "generate_code":
            return "Code generated below prompt in Script editor"
        elif feature == "explain_code":
            return "Explanation displayed below selected code"
        elif feature == "chat_window":
            return "Response shown in StudioAssist chat window"
        else:
            return f"Output displayed in Katalon Studio {feature} interface"


class PersonalOpenAIHandler(LLMAPIHandler):
    """Handler for personal OpenAI API keys - bypasses Katalon API entirely."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
        # Create a separate session for OpenAI without Katalon headers
        self.session = requests.Session()
        logger.info(f"Initialized PersonalOpenAIHandler with model: {self.model}")
    
    def get_handler_info(self) -> Dict:
        return {
            "type": "personal_openai",
            "api_url": self.api_url,
            "model": self.model
        }
    
    def call_api(self, feature: str, prompt: str, config: Dict) -> Dict:
        """Call OpenAI API directly - no Katalon involvement."""
        logger.info(f"🟦 Direct OpenAI API Call - Feature: {feature}, Model: {self.model}")
        logger.debug(f"Using OpenAI API at: {self.api_url}")
        
        # OpenAI-specific headers - no Katalon headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Get system prompt for the feature
        system_prompt = FEATURE_SYSTEM_PROMPTS.get(feature, "")
        
        # Build messages based on feature
        if feature == "chat_window":
            # Chat window format
            messages = [
                {"content": system_prompt, "role": "system"},
                {"content": """You have to follow these rules below step by step, respects their order strictly AND stop when its say that you DO NOT go to the next rules:
1. IF the user's question is related to any other tools OR platform THEN
  1.1. MUST NOT return "finalAnswer" in your response
  1.2. use "NOT_KATALON" value in your response to the warning's summary
  1.3. ONLY ask the user to visit [Integrations in Katalon Platform](https://docs.katalon.com/katalon-studio/integrations/integrations-in-katalon-platform) in the warning's explanation
  1.4. DO NOT go to the next rules
2. IF the user ask about broad kind of testing OR general about Katalon THEN
  2.1. you have to answer the user's question as the NON EMPTY "finalAnswer" in your response no matter what AND DO NOT go to the next rules
3. IF any of the user's provided information does NOT mention about any kind of testing AND does NOT mention about Katalon THEN
  3.1. MUST return ONLY an empty string as the "finalAnswer" in your response
  3.2. use "NOT_SOFTWARE_TESTING_DOMAIN" value in your response to the warning's summary
  3.3. DO NOT go to the next rules
4. IF you see that the user's question is related to the user-provided information during the conversation THEN:
  4.1. IF the user-provided information is enough to answer the user's question THEN
    4.1.1. answer the user's question as the NON EMPTY "finalAnswer" in the response and DO NOT go to the next rules
  4.2. IF the user-provided information is NOT enough to answer the user's question THEN
    4.2.1. MUST always give the NON EMPTY explanation as the "finalAnswer" in your response
    4.2.2. use "NOT_KATALON" value in your response to the warning's summary
    4.2.3. DO NOT go to the next rules
5. IF the user's question mentions about any kind of testing OR mentions about Katalon
   THEN you have to answer the user's question as the NON EMPTY "finalAnswer" in your response no matter what AND DO NOT go to the next rules
   OTHERWISE you MUST return ONLY an empty string as the "finalAnswer" in your response AND give the explanation to the warning's explanation AND use the below value in your response to the warning's summary:
    5.1. NOT_SOFTWARE_TESTING_DOMAIN when the request's topic doesn't relate to any kind of software testing
    5.2. NOT_KATALON when the request's topic relates to software testing but NOT Katalon product""", "role": "system"},
                {"role": "user", "content": prompt, "name": "user-input"}
            ]
            
            payload = {
                "messages": messages,
                "max_completion_tokens": 16000,
                "n": 1,
                "model": self.model,
                "response_format": {
                    "json_schema": {
                        "name": "response-message-schema",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "finalAnswer": {
                                    "anyOf": [{"type": "null"}, {"type": "string"}],
                                    "additionalProperties": False
                                },
                                "warning": {
                                    "anyOf": [
                                        {"type": "null"},
                                        {
                                            "type": "object",
                                            "properties": {
                                                "explanation": {"anyOf": [{"type": "null"}, {"type": "string"}]},
                                                "shortSummary": {"anyOf": [{"type": "null"}, {"type": "string"}]}
                                            },
                                            "additionalProperties": False
                                        }
                                    ]
                                }
                            },
                            "additionalProperties": False,
                            "required": []
                        },
                        "strict": False
                    },
                    "type": "json_schema"
                }
            }
        else:
            # Generate/explain code format
            messages = [
                {"content": system_prompt, "role": "system"},
                {"role": "user", "content": prompt, "name": "user-input"}
            ]
            
            payload = {
                "messages": messages,
                "max_completion_tokens": 16000,
                "n": 1,
                "model": self.model
            }
        
        logger.debug(f"OpenAI Request - Model: {self.model}, Messages: {len(messages)}")
        logger.debug(f"Using API Key: {self.api_key[:10]}...{self.api_key[-4:]}")
        
        try:
            # Direct call to OpenAI - no Katalon proxy
            response = self.session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT
            )
            
            logger.info(f"OpenAI Response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"OpenAI API error response: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            # Log token usage
            if "usage" in result:
                usage = result["usage"]
                logger.info(f"OpenAI Token usage - Prompt: {usage.get('prompt_tokens', 0)}, "
                          f"Completion: {usage.get('completion_tokens', 0)}, "
                          f"Total: {usage.get('total_tokens', 0)}")
            
            # Extract output based on feature
            if feature == "chat_window":
                content = result["choices"][0]["message"]["content"]
                try:
                    parsed = json.loads(content)
                    output = parsed.get("finalAnswer", "")
                except json.JSONDecodeError:
                    logger.warning("Failed to parse chat response as JSON, using raw content")
                    output = content
            else:
                output = result["choices"][0]["message"]["content"]
            
            logger.debug(f"OpenAI Output length: {len(output)} characters")
            
            return {
                "api_input": {
                    "model": self.model,
                    "prompt": prompt[:100] + "...",  # Truncate for logging
                    "llm_type": "personal_openai",
                    "api_url": self.api_url
                },
                "api_output": output,
                "gui_output": f"Output displayed in Katalon Studio {feature} interface",
                "full_response": result,
                "api_handler": "personal_openai",
                "api_endpoint": self.api_url
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"OpenAI HTTP error: {e}")
            logger.error(f"Response content: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return {"error": f"OpenAI API HTTP error: {str(e)}"}
        except Exception as e:
            logger.error(f"Personal OpenAI API error: {e}")
            return {"error": str(e)}


class KatalonStudioAssistService:
    """Service for Katalon Studio StudioAssist API interactions with multi-LLM support."""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self._setup_session()
        
        # Log configuration
        logger.info("="*60)
        logger.info("Katalon StudioAssist Service Configuration")
        logger.info("="*60)
        logger.info(f"Katalon Version: {getattr(config, 'katalon_version', '10.2.0')}")
        
        # Check LL1 configuration
        ll1_config_type = getattr(config, 'll1_config_type', 'katalon_ai')
        ll1_api_key = getattr(config, 'll1_api_key', '')
        ll1_model = getattr(config, 'll1_model', 'gpt-4o-mini')
        
        if ll1_config_type == 'katalon_ai':
            logger.info(f"LL1: Using Katalon AI Service")
        else:
            logger.info(f"LL1: Using {ll1_config_type} with model {ll1_model}")
            logger.info(f"LL1 API Key: {'Configured' if ll1_api_key else 'NOT SET'}")
        
        # Check LL2 configuration
        ll2_config_type = getattr(config, 'll2_config_type', 'personal_openai')
        ll2_api_key = getattr(config, 'll2_api_key', '')
        ll2_model = getattr(config, 'll2_model', 'gpt-4o-mini')
        
        if ll2_config_type == 'katalon_ai':
            logger.info(f"LL2: Using Katalon AI Service")
        else:
            logger.info(f"LL2: Using {ll2_config_type} with model {ll2_model}")
            logger.info(f"LL2 API Key: {'Configured' if ll2_api_key else 'NOT SET'}")
        
        logger.info("="*60)
        
        # Initialize handlers
        self.katalon_handler = KatalonAIHandler(self.session, config)
        
        try:
            self.handlers = {
                "LL1": self._create_handler(ll1_config_type, ll1_api_key, ll1_model),
                "LL2": self._create_handler(ll2_config_type, ll2_api_key, ll2_model)
            }
        except Exception as e:
            logger.error(f"Failed to initialize handlers: {e}")
            raise
        
        # Log handler info
        for llm_version, handler in self.handlers.items():
            info = handler.get_handler_info()
            logger.info(f"{llm_version} Handler: {info}")
    
    def _setup_session(self):
        """Setup session with StudioAssist-specific headers for Katalon API only."""
        self.session.headers.update({
            "content-type": "application/json",
            "accept": "application/json",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "sec-fetch-site": "same-site",
            "X-Client-App-Version": getattr(self.config, 'katalon_version', '10.2.0'),
            "X-Client-App-Module": "studioassist",
            "X-User-Id": self.config.user_id,
            "X-Client-App-Name": "katalon_studio",
            "Authorization": self.config.katalon_api_key,
            "Host": "katalon-api.katalon.com",
            "Connection": "Keep-Alive",
            "User-Agent": "Apache-HttpClient/4.5.14 (Java/17.0.14)"
        })
    
    def _create_handler(self, config_type: str, api_key: str, model: str) -> LLMAPIHandler:
        """Create appropriate handler based on config type."""
        logger.debug(f"Creating handler for config_type: {config_type}")
        
        if config_type == LLMConfigType.KATALON_AI.value or config_type == "katalon_ai":
            logger.info("Creating Katalon AI handler")
            return self.katalon_handler
        elif config_type == LLMConfigType.PERSONAL_OPENAI.value or config_type == "personal_openai":
            if not api_key:
                raise ValueError(f"Personal OpenAI API key is required but not provided")
            logger.info(f"Creating Personal OpenAI handler with model: {model}")
            return PersonalOpenAIHandler(api_key, model)
        elif config_type == LLMConfigType.PERSONAL_AZURE.value or config_type == "personal_azure":
            raise NotImplementedError("Azure OpenAI handler not yet implemented")
        else:
            raise ValueError(f"Unknown LLM config type: {config_type}")
    
    def call_api(self, feature: str, prompt: str, config: Dict, prompt_id: str, llm: str = "LL1") -> Dict:
        """Call appropriate LLM API based on configuration."""
        logger.info(f"\n{'='*60}")
        logger.info(f"API CALL: {llm} - Feature: {feature}")
        logger.info(f"{'='*60}")
        
        if llm not in self.handlers:
            raise ValueError(f"Unknown LLM version: {llm}")
        
        handler = self.handlers[llm]
        handler_info = handler.get_handler_info()
        logger.info(f"Using handler: {handler_info['type']} ({handler_info.get('model', 'N/A')})")
        logger.info(f"Prompt preview: {prompt[:100]}...")
        
        result = handler.call_api(feature, prompt, config)
        
        # Add metadata about which LLM config was used
        if "error" not in result:
            result["llm_config"] = {
                "version": llm,
                "type": handler_info['type'],
                "model": handler_info.get('model', 'N/A'),
                "katalon_version": getattr(self.config, 'katalon_version', '10.2.0')
            }
            logger.info(f"✅ API call successful - Output length: {len(result.get('api_output', ''))} chars")
        else:
            logger.error(f"❌ API call failed: {result['error']}")
        
        logger.info(f"{'='*60}\n")
        return result