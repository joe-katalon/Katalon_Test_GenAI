"""Human validation service for StudioAssist PoC."""

import logging
from datetime import datetime
from typing import Dict, List
from dataclasses import asdict

from utils.file_manager import FeatureFileManager  # Changed
from models import StudioAssistTestResult  # Changed

logger = logging.getLogger(__name__)

class HumanValidationService:
    """Service for handling human validation of results."""
    
    def __init__(self, file_manager: FeatureFileManager):
        self.file_manager = file_manager
    
    def create_validation_template(self, results: List[StudioAssistTestResult]) -> Dict:
        """Create template for human validation."""
        validation_template = {
            "feature": results[0].feature if results else "",
            "validation_timestamp": datetime.now().isoformat(),
            "validator": "",
            "results": []
        }
        
        for result in results:
            validation_item = {
                "input_id": result.input_id,
                "user_input": result.user_input,
                "api_output": result.api_output,
                "ll3_evaluation": asdict(result.ll3_evaluation) if result.ll3_evaluation else None,
                "human_assessment": {
                    "is_correct": None,
                    "quality_score": None,
                    "issues": [],
                    "comments": ""
                }
            }
            validation_template["results"].append(validation_item)
        
        filename = self.file_manager.generate_filename("human_validation_template")
        self.file_manager.save_json(validation_template, filename)
        logger.info(f"Human validation template saved to {filename}")
        
        return validation_template