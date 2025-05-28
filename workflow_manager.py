"""Workflow state management for multi-phase PoC execution."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple  # Add Tuple here
from dataclasses import dataclass, asdict

from constants import WorkflowStep, DatasetState, LLMConfigState
from report_generator import ReportGenerator

logger = logging.getLogger(__name__)

@dataclass
class WorkflowState:
    """Tracks the state of the PoC workflow."""
    feature: str
    current_phase: str
    llm_config_state: str
    baselines: Dict[str, Dict] = None  # Changed from baseline_dataset
    target_dataset: Optional[Dict] = None
    selected_baseline_id: Optional[str] = None  # Track which baseline is selected
    inputs_file: Optional[str] = None
    created_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.baselines is None:
            self.baselines = {}
        self.updated_at = datetime.now().isoformat()

class WorkflowManager:
    """Manages workflow state across multiple execution phases."""
    
    def __init__(self, config, state_dir: str = "workflow_states"):
        """Initialize with state directory path and config."""
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.config = config
        self.report_generator = ReportGenerator(config)
    
    def _get_state_file(self, feature: str) -> Path:
        """Get the state file path for a feature."""
        return self.state_dir / f"{feature}_state.json"
    
    def load_state(self, feature: str) -> Optional[WorkflowState]:
        """Load workflow state for a feature."""
        state_file = self._get_state_file(feature)
        if not state_file.exists():
            return None
        
        try:
            with state_file.open('r') as f:
                data = json.load(f)
                return WorkflowState(**data)
        except Exception as e:
            logger.error(f"Error loading state for feature {feature}: {e}")
            return None
    
    def save_state(self, state: WorkflowState):
        """Save workflow state to disk."""
        state_file = self._get_state_file(state.feature)
        try:
            with state_file.open('w') as f:
                json.dump(asdict(state), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state for feature {state.feature}: {e}")
    
    def update_baseline_info(self, feature: str, baseline_info: Dict):
        """Add a new baseline dataset."""
        state = self.load_state(feature) or WorkflowState(
            feature=feature,
            current_phase="baseline_created",
            llm_config_state=LLMConfigState.LL1_ACTIVE.value
        )
        
        # Generate unique ID for this baseline
        baseline_id = f"baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{baseline_info.get('num_inputs', 0)}"
        baseline_info['baseline_id'] = baseline_id
        
        state.baselines[baseline_id] = baseline_info
        state.current_phase = "baseline_created"
        self.save_state(state)
        
        return baseline_id
    
    def update_target_info(self, feature: str, target_info: Dict):
        """Update or add target dataset information."""
        state = self.load_state(feature) or WorkflowState(
            feature=feature,
            current_phase="target_created",
            llm_config_state=LLMConfigState.LL1_ACTIVE.value
        )
        
        target_info['updated_at'] = datetime.now().isoformat()
        
        state.target_dataset = target_info
        state.current_phase = "target_created"
        state.updated_at = datetime.now().isoformat()
        self.save_state(state)
    
    def get_all_baselines(self, feature: str) -> Dict[str, Dict]:
        """Get all baselines for a feature."""
        state = self.load_state(feature)
        return state.baselines if state else {}
    
    def get_baseline_by_id(self, feature: str, baseline_id: str) -> Optional[Dict]:
        """Get specific baseline by ID."""
        state = self.load_state(feature)
        if state and baseline_id in state.baselines:
            return state.baselines[baseline_id]
        return None
    
    def set_selected_baseline(self, feature: str, baseline_id: str):
        """Set which baseline is selected for comparison."""
        state = self.load_state(feature)
        if state and baseline_id in state.baselines:
            state.selected_baseline_id = baseline_id
            self.save_state(state)
            
    def check_ready_for_comparison(self, feature: str) -> Tuple[bool, str]:
        """Check if workflow is ready for phase 3 comparison.
        
        Returns:
            Tuple[bool, str]: (is_ready, message)
        """
        state = self.load_state(feature)
        if not state:
            return False, "No workflow state found"
            
        if not state.baselines:
            return False, "No baselines created yet. Run phase 1 first."
            
        if not state.selected_baseline_id:
            return False, "No baseline selected for comparison. Run phase 2 first."
            
        if not state.target_dataset:
            return False, "No target dataset created yet. Run phase 2 first."
            
        # Check if both baseline and target are evaluated
        baseline = state.baselines.get(state.selected_baseline_id, {})
        if baseline.get('state') != DatasetState.EVALUATED.value:
            return False, "Selected baseline has not been evaluated"
            
        if state.target_dataset.get('state') != DatasetState.EVALUATED.value:
            return False, "Target dataset has not been evaluated"
            
        return True, "Ready for comparison"
        
    def generate_html_report(self, feature: str, comparison_data: Dict) -> Tuple[bool, str]:
        """Generate an HTML report for the comparison results.
        
        Args:
            feature: The feature being tested
            comparison_data: Results from the comparison
            
        Returns:
            Tuple[bool, str]: (success, report_path or error_message)
        """
        try:
            state = self.load_state(feature)
            if not state:
                return False, "No workflow state found"
                
            baseline_info = state.baselines.get(state.selected_baseline_id)
            if not baseline_info:
                return False, "No baseline information found"
                
            target_info = state.target_dataset
            if not target_info:
                return False, "No target information found"
            
            # Ensure baseline_info has llm_config
            if "llm_config" not in baseline_info:
                baseline_info["llm_config"] = {
                    "type": baseline_info.get("llm_version", "LL1"),
                    "model": baseline_info.get("llm_model", "Unknown")
                }
            
            # Ensure target_info has llm_config
            if "llm_config" not in target_info:
                target_info["llm_config"] = {
                    "type": target_info.get("llm_version", "LL2"),
                    "model": target_info.get("llm_model", "Unknown")
                }
            
            # Add Katalon version to both info objects
            baseline_info["katalon_version"] = self.config.katalon_version
            target_info["katalon_version"] = self.config.katalon_version
            
            # Use the instance method of report_generator
            report_path = self.report_generator.generate_html_report(
                feature=feature,
                comparison_data=comparison_data,
                baseline_info=baseline_info,
                target_info=target_info
            )
            
            return True, report_path
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return False, str(e)