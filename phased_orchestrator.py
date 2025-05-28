"""Phased orchestrator for managing multi-step workflow with pauses."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
from difflib import SequenceMatcher
import os

from orchestrator import StudioAssistPoCOrchestrator
from workflow_manager import WorkflowManager, WorkflowState  # Add this import
from constants import WorkflowStep, DatasetState, LLMConfigState, TestMode, DatasetType  
from services.llm_service import LLMService  # Add this import at the top

logger = logging.getLogger(__name__)

class PhasedOrchestrator(StudioAssistPoCOrchestrator):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_manager = WorkflowManager(self.config)
        self.llm_manager = LLMService(self.config)  # Initialize LLM manager
    
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

    def _check_baseline_exists(self) -> bool:
        """Check if baselines exist by verifying both workflow state and files."""
        # Check workflow state
        state = self.workflow_manager.load_state(self.feature)
        if not state or not state.baselines:
            return False
            
        # Verify baseline files exist
        for baseline_id, baseline_info in state.baselines.items():
            baseline_file = baseline_info.get('filename')
            if not baseline_file or not Path(baseline_file).exists():
                # Remove invalid baseline from state
                state.baselines.pop(baseline_id)
                self.workflow_manager.save_state(state)
                continue
            return True
            
        return False

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
        
        # Check if baselines exist
        if self._check_baseline_exists():
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
        
        # Check if ready for comparison
        is_ready, message = self.workflow_manager.check_ready_for_comparison(self.feature)
        if not is_ready:
            logger.error(f"Not ready for comparison: {message}")
            return {}
            
        try:
            # Load workflow state
            state = self.workflow_manager.load_state(self.feature)
            baseline = state.baselines[state.selected_baseline_id]
            target = state.target_dataset
            
            # Log comparison details
            logger.info("\nComparing:")
            logger.info(f"  Baseline (LL1): {baseline['filename']}")
            logger.info(f"  Baseline ID: {state.selected_baseline_id}")
            logger.info(f"  Target (LL2): {target['filename']}")
            logger.info(f"  Test Mode: {target.get('test_mode', 'unknown')}")
            
            # Perform comparison
            logger.info("\n🔄 Comparing baseline and target datasets")
            comparison_result = await self.compare_datasets(
                baseline["filename"],
                target["filename"]
            )
            
            # Print detailed comparison summary
            self._print_comparison_summary(comparison_result, baseline, target)
            
            # Generate HTML report
            logger.info("\n📊 Generating comparison report")
            success, report_path = self.workflow_manager.generate_html_report(
                self.feature,
                comparison_result
            )
            
            if success:
                logger.info("\n" + "="*80)
                logger.info("📋 COMPARISON REPORT GENERATED")
                logger.info("="*80)
                logger.info(f"Report Location: {report_path}")
                logger.info("="*80)
            else:
                logger.warning(f"Failed to generate report: {report_path}")
            
            # Save phase summary
            phase_summary = {
                "phase": "comparison",
                "feature": self.feature,
                "baseline_id": state.selected_baseline_id,
                "comparison_result": comparison_result,
                "report_path": report_path if success else None,
                "next_steps": [
                    "1. Review the comparison results and HTML report at:",
                    f"   {report_path}",
                    "2. If target performs better, promote it to baseline with:",
                    f"   python main.py --feature {self.feature} --promote"
                ]
            }
            
            summary_file = self.file_manager.generate_filename("phase3_summary")
            self.file_manager.save_json(phase_summary, summary_file)
            
            logger.info("\n" + "="*60)
            logger.info("✅ PHASE 3 COMPLETED SUCCESSFULLY")
            logger.info("="*60)
            
            return phase_summary
            
        except Exception as e:
            logger.error(f"Phase 3 failed: {e}")
            raise
            
    def _print_comparison_summary(self, comparison_result: Dict, baseline: Dict, target: Dict):
        """Print detailed comparison summary with emoticons."""
        metrics = comparison_result.get("metrics", {})
        raw_eval = comparison_result.get("raw_evaluation", {})
        
        logger.info("\n" + "="*80)
        logger.info("🔍 DATASET COMPARISON SUMMARY 🔍")
        logger.info("="*80)
        logger.info(f"\n📊 Feature: {self.feature}")
        logger.info(f"🔄 Mode: {target.get('test_mode', 'unknown')}")
        logger.info(f"🕒 Timestamp: {datetime.now().isoformat()}")
        
        # Get Katalon Version from config
        logger.info(f"🔖 Katalon Version: {self.config.katalon_version}")
        
        logger.info("\n📑 Dataset Summary:")
        logger.info(f"  📌 Baseline (LL1) results: {baseline.get('num_inputs', 'unknown')}")
        logger.info(f"  🎯 Target (LL2) results: {target.get('num_inputs', 'unknown')}")
        logger.info(f"  🔄 Common inputs: {len(comparison_result.get('detailed_results', []))}")
        
        # Detailed Scores
        logger.info("\n📊 Detailed Scores:")
        
        # Consistency Scores
        consistency_scores = raw_eval.get("consistency_scores", {})
        logger.info("  🎯 Consistency Metrics:")
        output_stability = consistency_scores.get('output_stability', 0)
        behavior_consistency = consistency_scores.get('behavior_consistency', 0)
        style_consistency = consistency_scores.get('style_consistency', 0)
        
        logger.info(f"    {'🟢' if output_stability >= 0.8 else '🟡' if output_stability >= 0.6 else '🔴'} Output Stability: {output_stability:.2f}")
        logger.info(f"    {'🟢' if behavior_consistency >= 0.8 else '🟡' if behavior_consistency >= 0.6 else '🔴'} Behavior Consistency: {behavior_consistency:.2f}")
        logger.info(f"    {'🟢' if style_consistency >= 0.8 else '🟡' if style_consistency >= 0.6 else '🔴'} Style Consistency: {style_consistency:.2f}")
        
        # Accuracy Scores
        accuracy_scores = raw_eval.get("accuracy_scores", {})
        if any(v is not None for v in accuracy_scores.values()):
            logger.info("  ✅ Accuracy Metrics:")
            functional = accuracy_scores.get('functional_correctness', 0)
            code_quality = accuracy_scores.get('code_quality', 0)
            test_coverage = accuracy_scores.get('test_coverage', 0)
            
            logger.info(f"    {'🟢' if functional >= 0.8 else '🟡' if functional >= 0.6 else '🔴'} Functional Correctness: {functional:.2f}")
            logger.info(f"    {'🟢' if code_quality >= 0.8 else '🟡' if code_quality >= 0.6 else '🔴'} Code Quality: {code_quality:.2f}")
            logger.info(f"    {'🟢' if test_coverage >= 0.8 else '🟡' if test_coverage >= 0.6 else '🔴'} Test Coverage: {test_coverage:.2f}")
        
        # Performance Metrics
        perf_metrics = raw_eval.get("performance_metrics", {})
        logger.info("\n⚡ Performance Analysis:")
        time_diff = perf_metrics.get('time_difference', 0)
        logger.info(f"  ⏱️ Baseline Avg Time: {perf_metrics.get('baseline_avg_time', 0):.3f}s")
        logger.info(f"  ⏱️ Target Avg Time: {perf_metrics.get('target_avg_time', 0):.3f}s")
        logger.info(f"  {'🟢' if time_diff < 0 else '🔴' if time_diff > 0 else '⚪'} Time Difference: {time_diff:+.3f}s")
        
        # Analysis Details
        analysis = raw_eval.get("analysis", {})
        logger.info("\n🔬 Detailed Analysis:")
        
        if analysis.get("key_differences"):
            logger.info("  📋 Key Differences:")
            for diff in analysis["key_differences"]:
                logger.info(f"    • {diff}")
        
        if analysis.get("improvements"):
            logger.info("\n  ✨ Improvements:")
            for imp in analysis["improvements"]:
                logger.info(f"    ✅ {imp}")
        
        if analysis.get("regressions"):
            logger.info("\n  ⚠️ Regressions:")
            for reg in analysis["regressions"]:
                logger.info(f"    ❌ {reg}")
        
        if analysis.get("concerns"):
            logger.info("\n  ⚠️ Concerns:")
            for concern in analysis["concerns"]:
                logger.info(f"    ⚠️ {concern}")
        
        # Recommendations
        if raw_eval.get("recommendations"):
            logger.info("\n💡 Recommendations:")
            for i, rec in enumerate(raw_eval["recommendations"], 1):
                logger.info(f"  {i}. 📝 {rec}")
        
        # Final Recommendation and Confidence
        logger.info("\n🎯 Final Assessment:")
        final_rec = raw_eval.get('final_recommendation', 'UNKNOWN')
        confidence = raw_eval.get('confidence_level', 'unknown')
        
        rec_emoji = {
            'PROMOTE_LL2': '🚀',
            'KEEP_LL1': '🛡️',
            'FURTHER_TESTING': '🔄',
            'UNKNOWN': '❓'
        }
        
        conf_emoji = {
            'High': '💪',
            'Moderate': '👍',
            'Low': '🤔',
            'unknown': '❓'
        }
        
        logger.info(f"  {rec_emoji.get(final_rec, '❓')} Decision: {final_rec}")
        logger.info(f"  {conf_emoji.get(confidence, '❓')} Confidence Level: {confidence}")
        
        # Detailed Explanation
        if raw_eval.get("detailed_explanation"):
            logger.info("\n📝 Detailed Explanation:")
            logger.info(f"  {raw_eval['detailed_explanation']}")
        
        logger.info("\n" + "="*80)
    
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

    async def compare_datasets(self, baseline_file: str, target_file: str) -> Dict[str, Any]:
        """Compare baseline and target datasets using LLM3 for advanced evaluation.
        
        Args:
            baseline_file: Path to baseline dataset JSON
            target_file: Path to target dataset JSON
            
        Returns:
            Dict containing comparison metrics and detailed results
        """
        try:
            # Load complete datasets
            baseline_data = self.file_manager.load_json(baseline_file)
            target_data = self.file_manager.load_json(target_file)

            if not baseline_data or not target_data:
                raise ValueError("Failed to load comparison datasets")
            # Get test mode from workflow state
            state = self.workflow_manager.load_state(self.feature)
            test_mode = state.target_dataset.get("test_mode", "consistency") if state and state.target_dataset else "consistency"
            # Prepare comprehensive evaluation prompt for LLM3
            baseline_json = json.dumps(baseline_data, indent=2)
            target_json = json.dumps(target_data, indent=2)
            
            eval_prompt = f"""
            You are an expert evaluator comparing two LLM implementations (LL1 vs LL2) of Katalon Studio's StudioAssist feature.
            Please analyze the complete baseline and target datasets and provide a comprehensive evaluation.

            Context Information:
            Feature: {self.feature}
            Test Mode: {test_mode}

            Below are the complete baseline (LL1) and target (LL2) datasets for comparison:

            Baseline Dataset (LL1):
            {baseline_json}

            Target Dataset (LL2):
            {target_json}

            Please evaluate based on the following criteria:

            For Consistency Mode:
            1. Output Stability (0-1): How consistent are the outputs in terms of structure and format?
            2. Behavior Consistency (0-1): Do both implementations exhibit the same logical behavior?
            3. Style Consistency (0-1): How well does the target maintain coding style conventions?

            For Accuracy Mode:
            1. Functional Correctness (0-1): Does the target implementation correctly solve the problem?
            2. Code Quality (0-1): How well-written, maintainable, and efficient is the code?
            3. Test Coverage (0-1): How comprehensively does it handle different cases?

            Additional Analysis Required:
            1. Key Differences:
               - Identify structural and logical differences
               - Note any improvements or regressions
               - Highlight any concerning variations

            2. Performance Analysis:
               - Compare execution times
               - Identify performance bottlenecks
               - Suggest optimizations

            3. Quality Assessment:
               - Code structure and organization
               - Error handling and edge cases
               - Documentation and readability

            4. Recommendations:
               - Specific improvements needed
               - Best practices to implement
               - Risk mitigation strategies

            Please provide:
            1. Numerical scores for each criterion (0-1 scale)
            2. Detailed explanations for each score
            3. Comprehensive analysis of differences
            4. Specific recommendations for improvement
            5. Any concerns or potential risks
            6. Final recommendation: PROMOTE_LL2, KEEP_LL1, or FURTHER_TESTING

            Format your response as a JSON object with the following structure:
            {{
                "consistency_scores": {{
                    "output_stability": float,
                    "behavior_consistency": float,
                    "style_consistency": float
                }},
                "accuracy_scores": {{
                    "functional_correctness": float,
                    "code_quality": float,
                    "test_coverage": float
                }},
                "performance_metrics": {{
                    "baseline_avg_time": float,
                    "target_avg_time": float,
                    "time_difference": float
                }},
                "analysis": {{
                    "key_differences": [string],
                    "improvements": [string],
                    "regressions": [string],
                    "concerns": [string]
                }},
                "recommendations": [string],
                "final_recommendation": string,
                "confidence_level": string,
                "detailed_explanation": string
            }}
            """
            
            # Get LLM3's comprehensive evaluation
            evaluation = await self.evaluate_with_llm3(eval_prompt)
            print("\n" + "="*80)
            print("RAW LLM3 EVALUATION RESPONSE:")
            print("="*80)
            print(json.dumps(evaluation, indent=2))
            print("="*80 + "\n")
            
            # Return the evaluation results with complete raw data
            return {
                "metrics": {
                    "consistency_metrics": evaluation.get("consistency_scores", {}),
                    "accuracy_metrics": evaluation.get("accuracy_scores", {}),
                    "performance": evaluation.get("performance_metrics", {})
                },
                "analysis": evaluation.get("analysis", {}),
                "recommendations": evaluation.get("recommendations", []),
                "final_recommendation": evaluation.get("final_recommendation", "FURTHER_TESTING"),
                "confidence_level": evaluation.get("confidence_level", "low"),
                "detailed_explanation": evaluation.get("detailed_explanation", ""),
                "comparison_timestamp": datetime.now().isoformat(),
                "test_mode": test_mode,
                "raw_evaluation": evaluation  # Keep the complete raw evaluation
            }
            
        except Exception as e:
            logger.error(f"Dataset comparison failed: {e}")
            raise

    async def evaluate_with_llm3(self, prompt: str) -> Dict[str, Any]:
        """Evaluate outputs using LLM3 for advanced analysis.
        
        Args:
            prompt: The evaluation prompt for LLM3
            
        Returns:
            Dict containing evaluation scores and analysis
        """
        try:
            # Call LLM3 for evaluation with proper JSON schema
            response = await self.llm_manager.call_llm(
                prompt,
                response_format={
                    "type": "json_object"
                },
                expect_json=True
            )
            
            if not response:
                logger.error("No response from LLM3")
                return self._get_default_evaluation()
            
            # Validate the response has required fields
            required_fields = [
                "consistency_scores",
                "accuracy_scores",
                "performance_metrics",
                "analysis",
                "recommendations",
                "final_recommendation",
                "confidence_level",
                "detailed_explanation"
            ]
            
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                logger.error(f"Missing required fields in LLM3 response: {missing_fields}")
                logger.error(f"Raw response: {response}")
                return self._get_default_evaluation()
            
            return response
            
        except Exception as e:
            logger.error(f"LLM3 evaluation failed: {e}")
            logger.error(f"Prompt: {prompt}")
            return self._get_default_evaluation()
    
    def _get_default_evaluation(self) -> Dict[str, Any]:
        """Return default evaluation structure with zero scores."""
        return {
            "consistency_scores": {
                "output_stability": 0.0,
                "behavior_consistency": 0.0,
                "style_consistency": 0.0
            },
            "accuracy_scores": {
                "functional_correctness": 0.0,
                "code_quality": 0.0,
                "test_coverage": 0.0
            },
            "performance_metrics": {
                "baseline_avg_time": 0.0,
                "target_avg_time": 0.0,
                "time_difference": 0.0
            },
            "analysis": {
                "key_differences": ["Evaluation failed"],
                "improvements": [],
                "regressions": [],
                "concerns": ["LLM3 evaluation failed"]
            },
            "recommendations": ["Unable to provide recommendations due to evaluation failure"],
            "final_recommendation": "FURTHER_TESTING",
            "confidence_level": "low",
            "detailed_explanation": "LLM3 evaluation failed"
        }
    
    def _generate_comparison_notes(self, similarity: float, baseline_quality: float, target_quality: float) -> str:
        """Generate human-readable notes about the comparison."""
        quality_diff = target_quality - baseline_quality
        
        if similarity >= 0.9:
            if quality_diff > 0:
                return "Outputs are highly similar with improved quality"
            elif quality_diff < 0:
                return "Outputs are highly similar but quality decreased"
            return "Outputs are highly similar with equivalent quality"
            
        elif similarity >= 0.7:
            if quality_diff > 0:
                return "Moderate differences but improved quality"
            elif quality_diff < 0:
                return "Moderate differences with decreased quality"
            return "Moderate differences with equivalent quality"
            
        else:
            if quality_diff > 0:
                return "Significant differences but potentially better approach"
            elif quality_diff < 0:
                return "Significant differences with quality concerns"
            return "Significant differences detected"
    
    def _generate_recommendations(self, metrics: Dict[str, float]) -> List[str]:
        """Generate recommendations based on comparison metrics."""
        recommendations = []
        
        # Quality comparison
        quality_diff = metrics["quality_diff"]
        if quality_diff > 0.5:
            recommendations.append(
                "Target implementation shows significant quality improvement. Consider promoting to baseline."
            )
        elif quality_diff < -0.5:
            recommendations.append(
                "Target implementation shows quality regression. Review before promotion."
            )
        
        # Similarity analysis
        if metrics["overall_similarity"] < 0.7:
            if metrics["target_quality"] > metrics["baseline_quality"]:
                recommendations.append(
                    "Different approach detected but quality metrics are improved. Review changes."
                )
            else:
                recommendations.append(
                    "High output divergence detected. Verify if changes are intentional."
                )
        
        # Performance analysis
        time_diff = metrics["performance"]["average_time_diff"]
        if abs(time_diff) > 0.1:  # More than 100ms difference
            if time_diff > 0:
                recommendations.append(
                    f"Target is slower by {time_diff:.2f}s on average. Consider performance optimization."
                )
            else:
                recommendations.append(
                    f"Target shows {abs(time_diff):.2f}s performance improvement on average."
                )
        
        if not recommendations:
            if metrics["overall_similarity"] >= 0.9 and abs(quality_diff) < 0.1:
                recommendations.append(
                    "Target implementation is equivalent to baseline with no significant changes."
                )
            else:
                recommendations.append(
                    "Results are within acceptable ranges but could be improved."
                )
        
        return recommendations