"""Configuration management for StudioAssist PoC."""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union
from dotenv import load_dotenv  # Add this
from constants import FEATURE_CONFIGS  # Changed from .constants

logger = logging.getLogger(__name__)
# Load .env file at module level
load_dotenv()  # This loads .env file into environment variables

def str_to_bool(value: Union[str, bool, int]) -> bool:
    """Convert string/int/bool to boolean.
    
    Args:
        value: Value to convert to boolean. Can be:
            - string: 'true', '1', 'yes', 'on' (case insensitive) -> True
            - int: 1 -> True, 0 -> False
            - bool: returns as is
            
    Returns:
        bool: The converted boolean value
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return str(value).lower() in ('true', '1', 'yes', 'on')
    return bool(value)  # Handle any other types through standard bool() conversion

@dataclass
class Config:
    """Configuration data class with validation."""
    katalon_api_url: str
    katalon_api_key: str
    llm3_provider: str
    llm3_api_url: str
    llm3_api_key: str
    llm3_model: str
    user_id: str = "chau.duong@katalon.com"
    
    # Add these for chat_window support
    account_id: str = "1410137"
    organization_id: str = "1666289"
    user_id_numeric: str = "12539647"
    
    # LLM configuration for testing
    ll1_config_type: str = "katalon_ai"  # Default to Katalon AI
    ll1_api_key: str = ""  # For personal keys
    ll1_model: str = "gpt-4o-mini"  # Model to use with personal keys
    
    ll2_config_type: str = "personal_openai"  # Default to personal OpenAI
    ll2_api_key: str = ""  # For personal keys
    ll2_model: str = "gpt-4o-mini"  # Model to use with personal keys
    
    data_dir: str = "poc_data"
    max_concurrent_requests: int = 5
    feature: str = "generate_code"
    kse_license: bool = True
    
    # Version tracking
    katalon_version: str = "10.2.0"  # Track which Katalon version is being tested
    
    # LLM version configuration
    default_llm_version: str = "LL1"
    ll2_enabled: bool = False
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.katalon_api_key or self.katalon_api_key == "Bearer your_katalon_api_key_here":
            raise ValueError("KATALON_API_KEY environment variable must be set")
        if not self.llm3_api_key or "your_" in self.llm3_api_key:
            raise ValueError("LLM3_API_KEY environment variable must be set")
        if self.feature not in FEATURE_CONFIGS:
            raise ValueError(f"Invalid feature: {self.feature}. Must be one of {list(FEATURE_CONFIGS.keys())}")
        if not self.kse_license:
            logger.warning("StudioAssist requires an active KSE license")

def load_config(feature: Optional[str] = None) -> Config:
    """Load configuration from environment variables and config file."""
    config_file = Path("config.json")
    file_config = {}
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load config file: {e}")
    
    # Create a complete dictionary with all values before instantiating Config
    config_data = {
        "katalon_api_url": os.getenv("KATALON_API_URL") or file_config.get("katalon_api_url", ""),
        "katalon_api_key": os.getenv("KATALON_API_KEY") or file_config.get("katalon_api_key", ""),
        "llm3_provider": os.getenv("LLM3_PROVIDER") or file_config.get("llm3_provider", "gemini"),
        "llm3_api_url": os.getenv("LLM3_API_URL") or file_config.get("llm3_api_url", ""),
        "llm3_api_key": os.getenv("LLM3_API_KEY") or file_config.get("llm3_api_key", ""),
        "llm3_model": os.getenv("LLM3_MODEL") or file_config.get("llm3_model", "gemini-pro"),
        "user_id": os.getenv("KATALON_USER_ID") or file_config.get("user_id", "anonymous@katalon.com"),
        "account_id": os.getenv("KATALON_ACCOUNT_ID") or file_config.get("account_id", "1410137"),
        "organization_id": os.getenv("KATALON_ORG_ID") or file_config.get("organization_id", "1666289"),
        "user_id_numeric": os.getenv("KATALON_USER_ID_NUMERIC") or file_config.get("user_id_numeric", "12539647"),
        "feature": feature or os.getenv("KATALON_FEATURE") or file_config.get("feature", "generate_code"),
        "kse_license": str_to_bool(os.getenv("KSE_LICENSE", "true")) if os.getenv("KSE_LICENSE") else file_config.get("kse_license", True),
        "default_llm_version": os.getenv("DEFAULT_LLM_VERSION") or file_config.get("default_llm_version", "LL1"),
        "ll2_enabled": str_to_bool(os.getenv("LL2_ENABLED", "false")) if os.getenv("LL2_ENABLED") else file_config.get("ll2_enabled", False),
        "ll1_config_type": os.getenv("LL1_CONFIG_TYPE") or file_config.get("ll1_config_type", "katalon_ai"),
        "ll1_api_key": os.getenv("LL1_API_KEY") or file_config.get("ll1_api_key", ""),
        "ll1_model": os.getenv("LL1_MODEL") or file_config.get("ll1_model", "gpt-4o-mini"),
        "ll2_config_type": os.getenv("LL2_CONFIG_TYPE") or file_config.get("ll2_config_type", "personal_openai"),
        "ll2_api_key": os.getenv("LL2_API_KEY") or file_config.get("ll2_api_key", ""),
        "ll2_model": os.getenv("LL2_MODEL") or file_config.get("ll2_model", "gpt-4o-mini"),
        "katalon_version": os.getenv("KATALON_VERSION") or file_config.get("katalon_version", "10.2.0"),
        "data_dir": file_config.get("data_dir", "poc_data"),
        "max_concurrent_requests": file_config.get("max_concurrent_requests", 5)
    }
    
    # Create Config instance with the complete dictionary
    return Config(**config_data)

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Set up structured logging."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=getattr(logging, level.upper()), format=log_format)
    return logging.getLogger(__name__)