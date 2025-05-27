"""Data models for StudioAssist PoC."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

from constants import FEATURE_CONFIGS  # Changed from .constants

logger = logging.getLogger(__name__)

@dataclass
class StudioAssistTestInput:
    """StudioAssist test input data structure."""
    input_id: str
    feature: str
    prompt: str
    config: Dict
    prompt_id: str
    
    def validate(self) -> bool:
        """Validate test input data against StudioAssist requirements."""
        if self.feature not in FEATURE_CONFIGS:
            logger.error(f"Invalid feature: {self.feature}")
            return False
        
        expected_prompt_id = FEATURE_CONFIGS[self.feature]["prompt_id"]
        if self.prompt_id != expected_prompt_id:
            logger.error(f"Invalid prompt_id for {self.feature}: expected {expected_prompt_id}, got {self.prompt_id}")
            return False
        
        if self.feature == "generate_code":
            if not (self.prompt.strip().startswith('/*') or self.prompt.strip().startswith('//')):
                logger.warning(f"Generate code prompt should be in comment format for {self.input_id}")
        elif self.feature == "explain_code":
            if len(self.prompt.strip()) < 20:
                logger.error(f"Explain code prompt too short for {self.input_id}")
                return False
        
        return True

@dataclass
class LLMEvaluation:
    """LL3 evaluation results."""
    scores: Dict[str, float]
    feedback: Dict[str, str]
    overall_assessment: str
    overall_score: float
    suggestions: List[str]
    meets_requirements: bool
    evaluator_model: str
    evaluation_timestamp: str

@dataclass
class StudioAssistTestResult:
    """StudioAssist test result data structure with LL3 evaluation."""
    input_id: str
    feature: str
    user_input: str
    api_input: Dict
    config: Dict
    api_output: str
    gui_output: str
    llm_version: str
    timestamp: str
    response_time: float
    ll3_evaluation: Optional[LLMEvaluation] = None
    human_validation: Optional[Dict] = None
    error: Optional[str] = None