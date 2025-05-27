"""Phased orchestrator for managing multi-step workflow with pauses."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from orchestrator import StudioAssistPoCOrchestrator
from workflow_manager import WorkflowManager, WorkflowState  # Add this import
from constants import WorkflowStep, DatasetState, LLMConfigState, TestMode, DatasetType  

logger = logging.getLogger(__name__)

class PhasedOrchestrator(StudioAssistPoCOrchestrator):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_manager = WorkflowManager()
    
    def _display_baseline_options(self, baselines: Dict[str, Dict]) -> None:
        """Display available baselines in a formatted table."""
        print("\nAvailable Baselines:")
        print("-" * 80)
        print(f"{'ID':<30} {'Created':<20} {'Inputs':<10} {'State':<15}")
        print("-" * 80)
        
        for idx, (baseline_id, info) in enumerate(baselines.items(), 1):
            created = info.get('created_at', 'Unknown')[:19]  # Trim to date+time
            num_inputs = info.get('num_inputs', 0)
            state = info.get('state', 'Unknown')
            print(f"{idx}. {baseline_id:<28} {created:<20} {num_inputs:<10} {state:<15}")
        print("-" * 80)
    
    def _prompt_baseline_selection(self, baselines: Dict[str, Dict]) -> Optional[str]:
        """Prompt user to select a baseline."""
        baseline_ids = list(baselines.keys())
        
        while True:
            try:
                choice = input(f"\nSelect baseline (1-{len(baseline_ids)}), or 'q' to quit: ").strip()
                
                if choice.lower() == 'q':
                    return None
                
                idx = int(choice) - 1
                if 0 <= idx < len(baseline_ids):
                    return baseline_ids[idx]
                else:
                    print(f"Please enter a number between 1 and {len(baseline_ids)}")
                    
            except ValueError:
                print("Invalid input. Please enter a number or 'q' to quit.")
    async def run_phase_1_baseline(self, num_patterns: int = 10,
                                inputs_file: Optional[str] = None,
                                skip_evaluation: bool = False) -> Dict:
        """Phase 1: Create and evaluate baseline with LL1."""
        logger.info("="*60)
        logger.info("PHASE 1: BASELINE CREATION WITH LL1")
        logger.info("="*60)
        logger.info(f"Feature: {self.feature}")
        logger.info(f"LL1 Configuration: {self.config.ll1_config_type}")
        logger.info(f"LL1 Model: {self.config.ll1_model}")
        logger.info(f"Katalon Version: {self.config.katalon_version}")
        
        # Check current state
        state = self.workflow_manager.load_state(self.feature)
        if state and state.baselines:  # Changed from state.baseline_dataset
            logger.warning("Baseline(s) already exist for this feature")
            response = input("Create another baseline? (y/N): ")
            if response.lower() != 'y':
                logger.info("Cancelled baseline creation")
                return {}
        
        try:
            # Step 1: Generate or load inputs
            logger.info("\n📝 Preparing inputs for baseline")
            if inputs_file:
                inputs = self.file_manager.load_json(inputs_file)
                inputs = [inp for inp in inputs if inp.get('feature') == self.feature]
                inputs_filename = inputs_file
            else:
                inputs = await self.generate_feature_mock_data(num_patterns)
                inputs_filename = str(self.file_manager.get_latest_file("*mock_inputs*"))
            
            if not inputs:
                raise ValueError("No inputs available for baseline testing")
            
            # Step 2: Create baseline
            logger.info("\n🔨 Creating baseline dataset with LL1")
            baseline_creation = await self.create_dataset(inputs, "LL1", DatasetType.BASELINE)
            baseline_filename = baseline_creation.get("baseline_filename")
            
            # Step 3: Evaluate if requested
            if not skip_evaluation:
                logger.info("\n🔍 Evaluating baseline with LL3")
                evaluation_result = await self.evaluate_dataset(baseline_filename, DatasetType.BASELINE)
                baseline_filename = evaluation_result.get("baseline_evaluated_filename", baseline_filename)
                
                if "comprehensive_analysis" in evaluation_result:
                    self.print_comprehensive_analysis(evaluation_result["comprehensive_analysis"])
            
            # Update workflow state
            baseline_info = {
                "filename": baseline_filename,
                "inputs_file": inputs_filename,
                "num_inputs": len(inputs),
                "created_at": datetime.now().isoformat(),
                "state": DatasetState.EVALUATED.value if not skip_evaluation else DatasetState.RAW.value,
                "llm_version": "LL1"
            }
            
            baseline_id = self.workflow_manager.update_baseline_info(self.feature, baseline_info)
            baseline_info["baseline_id"] = baseline_id
            
            # Save phase summary
            phase_summary = {
                "phase": "baseline_creation",
                "feature": self.feature,
                "baseline_info": baseline_info,
                "next_steps": [
                    "1. Reconfigure product to use LL2",
                    "2. Run Phase 2 to create target dataset",
                    "3. Use 'python main.py --feature {} --phase target' to continue".format(self.feature)
                ]
            }
            
            summary_file = self.file_manager.generate_filename("phase1_summary")
            self.file_manager.save_json(phase_summary, summary_file)
            
            logger.info("\n" + "="*60)
            logger.info("✅ PHASE 1 COMPLETED SUCCESSFULLY")
            logger.info("="*60)
            logger.info(f"Baseline created: {baseline_filename}")
            logger.info(f"Baseline ID: {baseline_id}")
            logger.info("\n⚠️  NEXT STEPS:")
            for step in phase_summary["next_steps"]:
                logger.info(f"   {step}")
            logger.info("="*60 + "\n")
            
            return baseline_info
            
        except Exception as e:
            logger.error(f"Phase 1 failed: {e}")
            raise
    
    async def run_phase_2_target(self, test_mode: TestMode = TestMode.CONSISTENCY,
                                skip_evaluation: bool = False,
                                num_patterns: int = 10) -> Dict:
        """Phase 2: Create and evaluate target with LL2."""
        logger.info("="*60)
        logger.info("PHASE 2: TARGET CREATION WITH LL2")
        logger.info("="*60)
        logger.info(f"Feature: {self.feature}")
        logger.info(f"Test Mode: {test_mode.value}")
        
        # Check if we have the LLM config attributes
        ll2_config_type = getattr(self.config, 'll2_config_type', 'personal_openai')
        ll2_model = getattr(self.config, 'll2_model', 'gpt-4o-mini')
        ll1_config_type = getattr(self.config, 'll1_config_type', 'katalon_ai')
        ll1_model = getattr(self.config, 'll1_model', 'gpt-4o-mini')
        katalon_version = getattr(self.config, 'katalon_version', '10.2.0')
        
        logger.info(f"LL2 Configuration: {ll2_config_type}")
        logger.info(f"LL2 Model: {ll2_model}")
        logger.info(f"Katalon Version: {katalon_version}")
        
        # Get all baselines for this feature
        baselines = self.workflow_manager.get_all_baselines(self.feature)
        
        if not baselines:
            logger.error("No baselines found for this feature. Please create a baseline first.")
            return {}
        
        # Show available baselines and prompt for selection
        self._display_baseline_options(baselines)
        selected_baseline_id = self._prompt_baseline_selection(baselines)
        
        if not selected_baseline_id:
            logger.info("Baseline selection cancelled")
            return {}
        
        # Get selected baseline info
        baseline_info = baselines[selected_baseline_id]
        logger.info(f"\nSelected baseline: {selected_baseline_id}")
        logger.info(f"  Created: {baseline_info.get('created_at', 'Unknown')}")
        logger.info(f"  Inputs: {baseline_info.get('num_inputs', 0)}")
        logger.info(f"  State: {baseline_info.get('state', 'Unknown')}")
        
        # Store selected baseline in workflow state
        self.workflow_manager.set_selected_baseline(self.feature, selected_baseline_id)
        
        # Check if baseline is evaluated
        if baseline_info.get("state") != DatasetState.EVALUATED.value:
            logger.warning("Selected baseline is not evaluated. Consider evaluating it first.")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                return {}
        
        # Show configuration comparison
        logger.info("\nConfiguration Comparison:")
        logger.info(f"  LL1: {ll1_config_type} ({ll1_model})")
        logger.info(f"  LL2: {ll2_config_type} ({ll2_model})")
        
        # No need to ask about reconfiguration if using different API configs
        if ll1_config_type != ll2_config_type:
            logger.info("\n✅ Using different LLM configurations - no product reconfiguration needed")
        else:
            logger.warning("\n⚠️  IMPORTANT: Ensure product is configured differently for LL2")
            response = input("Is the product configured differently for LL2? (y/N): ")
            if response.lower() != 'y':
                logger.info("Please configure product differently and try again")
                return {}
        
        try:
            # Determine inputs based on test mode
            if test_mode == TestMode.CONSISTENCY:
                logger.info("\n📝 Using same inputs as selected baseline (consistency testing)")
                inputs_file = baseline_info["inputs_file"]
                inputs = self.file_manager.load_json(inputs_file)
                inputs = [inp for inp in inputs if inp.get('feature') == self.feature]
            else:
                logger.info(f"\n📝 Generating new inputs for accuracy testing")
                inputs = await self.generate_feature_mock_data(num_patterns)
                inputs_file = str(self.file_manager.get_latest_file("*mock_inputs*"))
            
            # Create target dataset
            logger.info("\n🎯 Creating target dataset with LL2")
            target_creation = await self.create_dataset(inputs, "LL2", DatasetType.TARGET)
            target_filename = target_creation.get("target_filename")
            
            # Evaluate if requested
            if not skip_evaluation:
                logger.info("\n🔍 Evaluating target with LL3")
                evaluation_result = await self.evaluate_dataset(target_filename, DatasetType.TARGET)
                target_filename = evaluation_result.get("target_evaluated_filename", target_filename)
                
                if "comprehensive_analysis" in evaluation_result:
                    self.print_comprehensive_analysis(evaluation_result["comprehensive_analysis"])
            
            # Update workflow state
            target_info = {
                "filename": target_filename,
                "inputs_file": inputs_file,
                "num_inputs": len(inputs),
                "created_at": datetime.now().isoformat(),
                "state": DatasetState.EVALUATED.value if not skip_evaluation else DatasetState.RAW.value,
                "llm_version": "LL2",
                "test_mode": test_mode.value,
                "compared_with_baseline": selected_baseline_id,
                "llm_config": {
                    "type": ll2_config_type,
                    "model": ll2_model
                }
            }
            
            self.workflow_manager.update_target_info(self.feature, target_info)
            
            # Save phase summary
            phase_summary = {
                "phase": "target_creation",
                "feature": self.feature,
                "target_info": target_info,
                "selected_baseline": {
                    "id": selected_baseline_id,
                    "info": baseline_info
                },
                "next_steps": [
                    "1. Run Phase 3 to compare datasets",
                    "2. Use 'python main.py --feature {} --phase compare' to continue".format(self.feature)
                ]
            }
            
            summary_file = self.file_manager.generate_filename("phase2_summary")
            self.file_manager.save_json(phase_summary, summary_file)
            
            logger.info("\n" + "="*60)
            logger.info("✅ PHASE 2 COMPLETED SUCCESSFULLY")
            logger.info("="*60)
            logger.info(f"Target created: {target_filename}")
            logger.info(f"Will be compared against: {selected_baseline_id}")
            logger.info("\n⚠️  NEXT STEPS:")
            for step in phase_summary["next_steps"]:
                logger.info(f"   {step}")
            logger.info("="*60 + "\n")
            
            return target_info
            
        except Exception as e:
            logger.error(f"Phase 2 failed: {e}")
            raise
    
    async def run_phase_3_compare(self) -> Dict:
        """Phase 3: Compare baseline and target datasets."""
        logger.info("="*60)
        logger.info("PHASE 3: DATASET COMPARISON")
        logger.info("="*60)
        logger.info(f"Feature: {self.feature}")
        
        # Check prerequisites
        ready, message = self.workflow_manager.check_ready_for_comparison(self.feature)
        if not ready:
            logger.error(f"Not ready for Phase 3: {message}")
            return {}
        
        try:
            # Get selected baseline and target info
            state = self.workflow_manager.load_state(self.feature)
            if not state.selected_baseline_id:
                logger.error("No baseline was selected in Phase 2")
                return {}
            
            baseline_info = state.baselines[state.selected_baseline_id]
            target_info = state.target_dataset
            
            logger.info(f"\nComparing:")
            logger.info(f"  Baseline (LL1): {baseline_info['filename']}")
            logger.info(f"  Baseline ID: {state.selected_baseline_id}")
            logger.info(f"  Target (LL2): {target_info['filename']}")
            logger.info(f"  Test Mode: {target_info.get('test_mode', 'consistency')}")
            

            # Run comparison
            test_mode = TestMode(target_info.get('test_mode', 'consistency'))
            comparison_result = await self.run_comparison(
                baseline_info['filename'],
                target_info['filename'],
                test_mode
            )
            
            # Generate final report
            final_report = {
                "phase": "comparison",
                "feature": self.feature,
                "baseline_info": baseline_info,
                "target_info": target_info,
                "comparison_result": comparison_result,
                "recommendation": comparison_result.get("recommendation", {}),
                "timestamp": datetime.now().isoformat()
            }
            
            report_file = self.file_manager.generate_filename("final_report")
            self.file_manager.save_json(final_report, report_file)
            
            logger.info("\n" + "="*60)
            logger.info("✅ PHASE 3 COMPLETED SUCCESSFULLY")
            logger.info("="*60)
            logger.info(f"Final report: {report_file}")
            
            # Print recommendation
            rec = comparison_result.get("recommendation", {})
            if rec:
                logger.info(f"\n📊 RECOMMENDATION: {rec.get('decision', 'N/A')}")
                logger.info(f"   Confidence: {rec.get('confidence', 'N/A')}")
                for reason in rec.get('reasons', []):
                    logger.info(f"   - {reason}")
            
            logger.info("="*60 + "\n")
            
            return final_report
            
        except Exception as e:
            logger.error(f"Phase 3 failed: {e}")
            raise
    
    def get_workflow_status(self) -> Dict:
        """Get current workflow status."""
        state = self.workflow_manager.load_state(self.feature)
        if not state:
            return {
                "feature": self.feature,
                "status": "Not started",
                "next_action": "Run Phase 1 to create baseline"
            }
        
        status = {
            "feature": self.feature,
            "current_phase": state.current_phase,
            "llm_config_state": state.llm_config_state,
            "num_baselines": len(state.baselines),
            "baseline_ids": list(state.baselines.keys()) if state.baselines else [],
            "selected_baseline": state.selected_baseline_id,
            "target_exists": state.target_dataset is not None,
            "last_updated": state.updated_at
        }
        
        # Determine next action
        if not state.baselines:
            status["next_action"] = "Run Phase 1 to create baseline(s)"
        elif not state.target_dataset:
            status["next_action"] = "Configure product with LL2, then run Phase 2"
        else:
            status["next_action"] = "Run Phase 3 to compare datasets"
        
        return status
    
    async def promote_target_to_baseline(self) -> bool:
        """Promote current target dataset to be the new baseline."""
        logger.info("="*60)
        logger.info("PROMOTING TARGET TO BASELINE")
        logger.info("="*60)
        
        state = self.workflow_manager.load_state(self.feature)
        if not state or not state.target_dataset:
            logger.error("No target dataset found to promote")
            return False
        
        logger.warning("⚠️  This will make the current LL2 target the new baseline for future comparisons")
        response = input("Are you sure you want to promote target to baseline? (y/N): ")
        if response.lower() != 'y':
            logger.info("Promotion cancelled")
            return False
        
        success = self.workflow_manager.promote_target_to_baseline(self.feature)
        if success:
            logger.info("✅ Target successfully promoted to baseline")
            logger.info("The previous baseline has been archived")
            logger.info("You can now test a new LL2 configuration against this baseline")
        else:
            logger.error("Failed to promote target to baseline")
        
        return success