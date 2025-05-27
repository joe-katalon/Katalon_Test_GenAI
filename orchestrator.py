"""Main orchestrator for StudioAssist PoC workflow."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict

from config import Config
from constants import TestMode, WorkflowStep, FEATURE_CONFIGS, DatasetType
from models import StudioAssistTestInput, StudioAssistTestResult
from services.llm_service import LLMService
from services.katalon_service import KatalonStudioAssistService
from services.baseline_service import BaselineCreationService
from services.evaluation_service import LL3EvaluationService
from services.validation_service import HumanValidationService
from services.comparison_service import DatasetComparisonService  # New import
from utils.file_manager import FeatureFileManager
from utils.prompt_generator import KatalonPromptGenerator

logger = logging.getLogger(__name__)

class StudioAssistPoCOrchestrator:
    """StudioAssist feature-specific orchestrator with full workflow support."""
    
    def __init__(self, config: Config):
        self.config = config
        self.feature = config.feature
        self.file_manager = FeatureFileManager(config.data_dir, self.feature)
        self.llm_service = LLMService(config)
        self.katalon_service = KatalonStudioAssistService(config)
        self.prompt_generator = KatalonPromptGenerator(self.feature)
        self.baseline_service = BaselineCreationService(self.katalon_service, self.file_manager)
        self.evaluation_service = LL3EvaluationService(self.llm_service, self.prompt_generator, self.file_manager)
        self.validation_service = HumanValidationService(self.file_manager)
        self.comparison_service = DatasetComparisonService(self.file_manager)  # New service
    
    async def generate_feature_mock_data(self, num_patterns: int = 10) -> List[Dict]:
        """Generate StudioAssist feature-specific mock test data."""
        logger.info(f"Generating {num_patterns} mock patterns for StudioAssist '{self.feature}' using {self.config.llm3_provider}")
        
        prompt = self.prompt_generator.generate_mock_prompt(num_patterns)
        
        response = await self.llm_service.call_llm(prompt)
        if response:
            validated_response = []
            for entry in response:
                if entry.get('feature') == self.feature:
                    test_input = StudioAssistTestInput(**entry)
                    if test_input.validate():
                        validated_response.append(entry)
                    else:
                        logger.warning(f"Invalid entry: {entry.get('input_id')}")
                else:
                    logger.warning(f"Skipping entry with mismatched feature: {entry.get('feature')}")
            
            filename = self.file_manager.generate_filename("mock_inputs")
            self.file_manager.save_json(validated_response, filename)
            logger.info(f"Mock dataset for StudioAssist '{self.feature}' generated and saved to {filename}")
            return validated_response
        
        logger.error(f"Failed to generate mock dataset for StudioAssist '{self.feature}'")
        return []
    
    async def create_dataset(self, inputs: List[Dict], llm_version: str, 
                           dataset_type: DatasetType = DatasetType.BASELINE) -> Dict[str, Any]:
        """Create dataset (baseline or target) with specified LLM version."""
        logger.info(f"Creating {dataset_type.value} dataset with {llm_version}")
        
        # Create dataset via API calls
        creation_result = await self.baseline_service.create_baseline_from_inputs(inputs, llm_version)
        
        # Update filenames based on dataset type
        if creation_result.get("baseline_filename"):
            # Rename files to reflect dataset type
            old_filename = creation_result["baseline_filename"]
            new_filename = self.file_manager.generate_filename(
                f"{dataset_type.value}_raw", 
                llm_version.lower()
            )
            
            # Load and resave with new filename
            data = self.file_manager.load_json(old_filename)
            data["metadata"]["dataset_type"] = dataset_type.value
            self.file_manager.save_json(data, new_filename)
            
            creation_result[f"{dataset_type.value}_filename"] = str(new_filename)
        
        return creation_result
    
    async def evaluate_dataset(self, dataset_file: str, dataset_type: DatasetType = DatasetType.BASELINE) -> Dict[str, Any]:
        """Evaluate a dataset with LL3."""
        logger.info(f"Evaluating {dataset_type.value} dataset")
        
        evaluation_result = await self.evaluation_service.evaluate_baseline_from_file(dataset_file)
        
        # Update filename to reflect dataset type
        if evaluation_result.get("evaluated_filename"):
            old_filename = evaluation_result["evaluated_filename"]
            data = self.file_manager.load_json(old_filename)
            
            # Extract LLM version from metadata
            llm_version = data.get("metadata", {}).get("llm_version", "unknown")
            
            new_filename = self.file_manager.generate_filename(
                f"{dataset_type.value}_evaluated",
                llm_version.lower()
            )
            
            # Update metadata
            data["metadata"]["dataset_type"] = dataset_type.value
            self.file_manager.save_json(data, new_filename)
            
            evaluation_result[f"{dataset_type.value}_evaluated_filename"] = str(new_filename)
        
        return evaluation_result
    
    async def run_comparison(self, baseline_file: str, target_file: str, 
                           mode: TestMode = TestMode.CONSISTENCY) -> Dict[str, Any]:
        """Compare baseline (LL1) and target (LL2) datasets."""
        logger.info(f"Running comparison in {mode.value} mode")
        
        # Load datasets
        baseline_data = self.file_manager.load_json(baseline_file)
        target_data = self.file_manager.load_json(target_file)
        
        # Run comparison
        comparison_result = self.comparison_service.compare_datasets(
            baseline_data, 
            target_data, 
            self.feature, 
            mode.value
        )
        
        # Print comparison summary
        self.print_comparison_summary(comparison_result)
        
        return comparison_result
    
    async def run_workflow_step(self, step: WorkflowStep, **kwargs):
        """Run a specific workflow step."""
        logger.info(f"Running workflow step: {step.value}")
        
        if step == WorkflowStep.GENERATE_INPUTS:
            num_patterns = kwargs.get("num_patterns", 10)
            return await self.generate_feature_mock_data(num_patterns)
        
        elif step == WorkflowStep.CREATE_BASELINE:
            inputs = kwargs.get("inputs")
            if not inputs:
                raise ValueError("Inputs required for baseline creation")
            return await self.create_dataset(inputs, "LL1", DatasetType.BASELINE)
        
        elif step == WorkflowStep.EVALUATE_BASELINE:
            baseline_file = kwargs.get("baseline_file")
            if not baseline_file:
                raise ValueError("Baseline file required for evaluation")
            result = await self.evaluate_dataset(baseline_file, DatasetType.BASELINE)
            
            if "comprehensive_analysis" in result:
                self.print_comprehensive_analysis(result["comprehensive_analysis"])
            
            return result
        
        elif step == WorkflowStep.CREATE_TARGET:
            inputs = kwargs.get("inputs")
            if not inputs:
                raise ValueError("Inputs required for target creation")
            return await self.create_dataset(inputs, "LL2", DatasetType.TARGET)
        
        elif step == WorkflowStep.EVALUATE_TARGET:
            target_file = kwargs.get("target_file")
            if not target_file:
                raise ValueError("Target file required for evaluation")
            result = await self.evaluate_dataset(target_file, DatasetType.TARGET)
            
            if "comprehensive_analysis" in result:
                self.print_comprehensive_analysis(result["comprehensive_analysis"])
            
            return result
        
        elif step == WorkflowStep.COMPARE_DATASETS:
            baseline_file = kwargs.get("baseline_file")
            target_file = kwargs.get("target_file")
            mode = TestMode(kwargs.get("mode", "consistency"))
            
            if not baseline_file or not target_file:
                raise ValueError("Both baseline and target files required for comparison")
            
            return await self.run_comparison(baseline_file, target_file, mode)
        
        else:
            raise ValueError(f"Unsupported workflow step: {step}")
    
    async def run_full_poc(self, baseline_file: Optional[str] = None, 
                          inputs_file: Optional[str] = None,
                          num_patterns: int = 10,
                          skip_evaluation: bool = False,
                          test_mode: TestMode = TestMode.CONSISTENCY):
        """Run the complete PoC workflow including LL2 testing and comparison."""
        logger.info(f"Starting Full Katalon StudioAssist PoC for '{self.feature}' feature")
        logger.info(f"Test mode: {test_mode.value}")
        logger.info("="*60)
        
        try:
            # Step 1: Prepare baseline with LL1
            logger.info("\n📝 Step 1: Establishing LL1 Baseline")
            
            # Generate or load inputs for baseline
            if inputs_file:
                logger.info(f"Loading inputs from {inputs_file}")
                baseline_inputs = self.file_manager.load_json(inputs_file)
                baseline_inputs = [inp for inp in baseline_inputs if inp.get('feature') == self.feature]
            else:
                logger.info(f"Generating {num_patterns} mock inputs for baseline")
                baseline_inputs = await self.generate_feature_mock_data(num_patterns)
            
            if not baseline_inputs:
                raise ValueError("No inputs available for baseline testing")
            
            # Create or load baseline
            if baseline_file:
                logger.info(f"Loading existing baseline from {baseline_file}")
                baseline_filename = baseline_file
            else:
                logger.info("Creating new baseline with LL1")
                baseline_creation = await self.create_dataset(baseline_inputs, "LL1", DatasetType.BASELINE)
                baseline_filename = baseline_creation.get("baseline_filename")
                
                if not skip_evaluation:
                    logger.info("Evaluating baseline with LL3")
                    baseline_eval = await self.evaluate_dataset(baseline_filename, DatasetType.BASELINE)
                    baseline_filename = baseline_eval.get("baseline_evaluated_filename", baseline_filename)
            
            logger.info(f"✅ Baseline established: {baseline_filename}")
            
            # Step 2: Create target dataset with LL2
            logger.info("\n🎯 Step 2: Creating Target Dataset with LL2")
            
            # Determine inputs for target
            if test_mode == TestMode.CONSISTENCY:
                logger.info("Using same inputs as baseline (consistency testing)")
                target_inputs = baseline_inputs
            else:
                logger.info(f"Generating new inputs for accuracy testing")
                target_inputs = await self.generate_feature_mock_data(num_patterns)
            
            # Create target dataset with LL2
            logger.info("Creating target dataset with LL2")
            target_creation = await self.create_dataset(target_inputs, "LL2", DatasetType.TARGET)
            target_filename = target_creation.get("target_filename")
            
            if not skip_evaluation:
                logger.info("Evaluating target dataset with LL3")
                target_eval = await self.evaluate_dataset(target_filename, DatasetType.TARGET)
                target_filename = target_eval.get("target_evaluated_filename", target_filename)
            
            logger.info(f"✅ Target dataset created: {target_filename}")
            
            # Step 3: Compare datasets
            logger.info("\n📊 Step 3: Comparing Baseline (LL1) vs Target (LL2)")
            
            comparison_result = await self.run_comparison(
                baseline_filename, 
                target_filename, 
                test_mode
            )
            
            # Generate final summary
            logger.info("\n📋 Generating Final Summary")
            summary = self._generate_final_summary(
                baseline_inputs,
                target_inputs,
                baseline_filename,
                target_filename,
                comparison_result,
                test_mode
            )
            
            summary_filename = self.file_manager.generate_filename("poc_complete_summary")
            self.file_manager.save_json(summary, summary_filename)
            
            # Print final summary
            self._print_final_summary(summary)
            
            logger.info(f"\n✅ PoC completed successfully!")
            logger.info(f"📁 All results saved in: {self.file_manager.feature_dir}")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ PoC failed: {e}")
            raise
    
    def print_comparison_summary(self, comparison: Dict):
        """Print comparison summary in a formatted way."""
        print("\n" + "="*80)
        print("DATASET COMPARISON SUMMARY")
        print("="*80)
        
        # Metadata
        meta = comparison.get("metadata", {})
        print(f"\nFeature: {meta.get('feature', 'N/A')}")
        print(f"Mode: {meta.get('comparison_mode', 'N/A')}")
        print(f"Timestamp: {meta.get('timestamp', 'N/A')}")
        
        # Summary
        summary = comparison.get("summary", {})
        print(f"\nDataset Summary:")
        print(f"  - Baseline (LL1) results: {summary.get('baseline_count', 0)}")
        print(f"  - Target (LL2) results: {summary.get('target_count', 0)}")
        if "common_inputs" in summary:
            print(f"  - Common inputs: {summary.get('common_inputs', 0)}")
        
        # Quality Comparison
        quality = comparison.get("quality_comparison", {})
        if quality.get("overall_comparison"):
            overall = quality["overall_comparison"]
            print(f"\nQuality Comparison:")
            print(f"  - LL1 Mean Score: {overall.get('baseline_mean', 0):.2f}")
            print(f"  - LL2 Mean Score: {overall.get('target_mean', 0):.2f}")
            
            diff = overall.get('target_mean', 0) - overall.get('baseline_mean', 0)
            if diff > 0:
                print(f"  - Improvement: +{diff:.2f} points")
            else:
                print(f"  - Difference: {diff:.2f} points")
        
        # Consistency Metrics (if applicable)
        if comparison.get("consistency_metrics"):
            consistency = comparison["consistency_metrics"]
            print(f"\nConsistency Metrics:")
            print(f"  - Overall Consistency: {consistency.get('overall_consistency', 0):.1%}")
            print(f"  - High Consistency Rate: {consistency.get('high_consistency_rate', 0):.1%}")
            print(f"  - Significant Variations: {consistency.get('significant_variations', 0)}")
        
        # Insights
        insights = comparison.get("insights", [])
        if insights:
            print(f"\nKey Insights:")
            for i, insight in enumerate(insights, 1):
                print(f"  {i}. {insight}")
        
        # Recommendation
        rec = comparison.get("recommendation", {})
        if rec:
            print(f"\nRecommendation:")
            print(f"  Decision: {rec.get('decision', 'N/A')}")
            print(f"  Confidence: {rec.get('confidence', 'N/A')}")
            if rec.get("reasons"):
                print(f"  Reasons:")
                for reason in rec["reasons"]:
                    print(f"    - {reason}")
        
        print("\n" + "="*80 + "\n")
    
    def _generate_final_summary(self, baseline_inputs, target_inputs, 
                               baseline_file, target_file, 
                               comparison_result, test_mode):
        """Generate comprehensive final summary."""
        return {
            "poc_metadata": {
                "feature": self.feature,
                "feature_description": FEATURE_CONFIGS[self.feature]["description"],
                "test_mode": test_mode.value,
                "timestamp": datetime.now().isoformat(),
                "ll3_model": self.config.llm3_model
            },
            "test_configuration": {
                "baseline_inputs": len(baseline_inputs),
                "target_inputs": len(target_inputs),
                "inputs_overlap": len(set(inp["input_id"] for inp in baseline_inputs) & 
                                    set(inp["input_id"] for inp in target_inputs))
            },
            "datasets": {
                "baseline": baseline_file,
                "target": target_file
            },
            "comparison_summary": {
                "quality_improvement": comparison_result.get("quality_comparison", {})
                                                      .get("overall_comparison", {})
                                                      .get("target_mean", 0) -
                                      comparison_result.get("quality_comparison", {})
                                                      .get("overall_comparison", {})
                                                      .get("baseline_mean", 0),
                "consistency_score": comparison_result.get("consistency_metrics", {})
                                                     .get("overall_consistency", 0) if test_mode == TestMode.CONSISTENCY else None,
                "recommendation": comparison_result.get("recommendation", {}).get("decision", "N/A"),
                "confidence": comparison_result.get("recommendation", {}).get("confidence", "N/A")
            },
            "key_insights": comparison_result.get("insights", [])[:5]  # Top 5 insights
        }
    
    def _print_final_summary(self, summary: Dict):
        """Print final summary in a clean format."""
        print("\n" + "="*60)
        print("POC COMPLETE SUMMARY")
        print("="*60)
        
        meta = summary["poc_metadata"]
        print(f"Feature: {meta['feature_description']}")
        print(f"Test Mode: {meta['test_mode']}")
        print(f"LL3 Model: {meta['ll3_model']}")
        
        config = summary["test_configuration"]
        print(f"\nTest Configuration:")
        print(f"  - Baseline Inputs: {config['baseline_inputs']}")
        print(f"  - Target Inputs: {config['target_inputs']}")
        
        comp_summary = summary["comparison_summary"]
        print(f"\nResults:")
        print(f"  - Quality Change: {comp_summary['quality_improvement']:+.2f} points")
        if comp_summary["consistency_score"] is not None:
            print(f"  - Consistency: {comp_summary['consistency_score']:.1%}")
        print(f"  - Recommendation: {comp_summary['recommendation']}")
        print(f"  - Confidence: {comp_summary['confidence']}")
        
        insights = summary.get("key_insights", [])
        if insights:
            print(f"\nKey Insights:")
            for insight in insights:
                print(f"  • {insight}")
        
        print("="*60 + "\n")
    
    # Keep existing print methods
    def print_comprehensive_analysis(self, analysis: Dict):
        """Print comprehensive analysis in a formatted way."""
        # ... (keep existing implementation)
        pass