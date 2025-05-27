"""Baseline creation service for StudioAssist PoC."""

import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import asdict

from services.katalon_service import KatalonStudioAssistService  # Changed
from utils.file_manager import FeatureFileManager  # Changed
from models import StudioAssistTestInput, StudioAssistTestResult  # Changed
from constants import API_RATE_LIMIT_DELAY  # Changed

logger = logging.getLogger(__name__)

class BaselineCreationService:
    """Service specifically for creating baseline datasets via Katalon API."""
    
    def __init__(self, katalon_service: KatalonStudioAssistService, file_manager: FeatureFileManager):
        self.katalon_service = katalon_service
        self.file_manager = file_manager
    
    async def create_baseline_from_inputs(self, inputs: List[Dict], llm_version: str = "LL1") -> Dict[str, Any]:
        """Create baseline by calling Katalon API for each input."""
        logger.info(f"Creating baseline dataset by calling Katalon API with {llm_version}")
        logger.info(f"Processing {len(inputs)} inputs")
        
        baseline_results = {}
        api_call_summary = {
            "total_inputs": len(inputs),
            "successful_calls": 0,
            "failed_calls": 0,
            "errors": [],
            "start_time": datetime.now().isoformat()
        }
        
        for idx, input_data in enumerate(inputs):
            logger.info(f"Processing input {idx + 1}/{len(inputs)}: {input_data.get('input_id', 'unknown')}")
            
            try:
                test_input = StudioAssistTestInput(**input_data)
                if not test_input.validate():
                    error_msg = f"Invalid input data for {test_input.input_id}"
                    logger.warning(error_msg)
                    api_call_summary["errors"].append({"input_id": test_input.input_id, "error": error_msg})
                    api_call_summary["failed_calls"] += 1
                    continue
                
                start_time = time.time()
                response = self.katalon_service.call_api(
                    feature=test_input.feature,
                    prompt=test_input.prompt,
                    config=test_input.config,
                    prompt_id=test_input.prompt_id,
                    llm=llm_version
                )
                response_time = time.time() - start_time
                
                if "error" not in response:
                    result = StudioAssistTestResult(
                        input_id=test_input.input_id,
                        feature=test_input.feature,
                        user_input=test_input.prompt,
                        api_input=response["api_input"],
                        config=test_input.config,
                        api_output=response["api_output"],
                        gui_output=response["gui_output"],
                        llm_version=llm_version,
                        timestamp=datetime.now().isoformat(),
                        response_time=response_time
                    )
                    
                    baseline_results[test_input.input_id] = result
                    api_call_summary["successful_calls"] += 1
                    
                    logger.info(f"Successfully processed {test_input.input_id} in {response_time:.2f}s")
                else:
                    error_msg = f"API error: {response['error']}"
                    logger.error(f"Failed to process {test_input.input_id}: {error_msg}")
                    api_call_summary["errors"].append({"input_id": test_input.input_id, "error": error_msg})
                    api_call_summary["failed_calls"] += 1
                
                await asyncio.sleep(API_RATE_LIMIT_DELAY)
                
            except Exception as e:
                error_msg = f"Exception: {str(e)}"
                logger.error(f"Error processing input {input_data.get('input_id', 'unknown')}: {error_msg}")
                api_call_summary["errors"].append({"input_id": input_data.get('input_id', 'unknown'), "error": error_msg})
                api_call_summary["failed_calls"] += 1
        
        api_call_summary["end_time"] = datetime.now().isoformat()
        
        if baseline_results:
            baseline_filename = self.file_manager.generate_filename("baseline_raw", llm_version.lower())
            baseline_data = {
                "metadata": {
                    "feature": inputs[0]["feature"] if inputs else "unknown",
                    "llm_version": llm_version,
                    "creation_timestamp": datetime.now().isoformat(),
                    "total_results": len(baseline_results)
                },
                "inputs": inputs,
                "results": {k: asdict(v) for k, v in baseline_results.items()}
            }
            self.file_manager.save_json(baseline_data, baseline_filename)
            logger.info(f"Baseline data saved to {baseline_filename}")
            
            summary_filename = self.file_manager.generate_filename("api_call_summary", llm_version.lower())
            self.file_manager.save_json(api_call_summary, summary_filename)
            logger.info(f"API call summary saved to {summary_filename}")
        
        return {
            "baseline_results": baseline_results,
            "api_call_summary": api_call_summary,
            "baseline_filename": str(baseline_filename) if baseline_results else None,
            "inputs": inputs
        }