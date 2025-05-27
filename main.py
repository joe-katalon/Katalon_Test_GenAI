"""Main entry point for StudioAssist PoC."""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# For direct execution, use regular imports (not relative)
from config import load_config, setup_logging
from constants import FEATURE_CONFIGS, TestMode, WorkflowStep
from phased_orchestrator import PhasedOrchestrator

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Katalon Studio StudioAssist PoC - Phased Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phased Workflow:

PHASE 1 - Create Baseline (with LL1):
  python main.py --feature generate_code --phase baseline
  
PHASE 2 - Create Target (with LL2):
  # First: Reconfigure product to use LL2
  python main.py --feature generate_code --phase target
  
PHASE 3 - Compare Datasets:
  python main.py --feature generate_code --phase compare

Other Commands:
  python main.py --feature generate_code --status         # Check workflow status
  python main.py --feature generate_code --promote        # Promote target to baseline
  python main.py --list-features                          # List available features

Legacy Commands (for development):
  python main.py --feature generate_code --step generate_inputs
  python main.py --feature generate_code --step create_baseline --inputs-file inputs.json
        """
    )
    
    # Main arguments
    parser.add_argument(
        "--feature", 
        choices=list(FEATURE_CONFIGS.keys()), 
        default="generate_code",
        help="StudioAssist feature to test"
    )
    
    # Phase-based workflow
    parser.add_argument(
        "--phase",
        choices=["baseline", "target", "compare"],
        help="Run specific phase of the workflow"
    )
    
    # Individual steps (legacy support)
    parser.add_argument(
        "--step",
        choices=[step.value for step in WorkflowStep],
        help="Run specific workflow step (for development)"
    )
    
    # Workflow management
    parser.add_argument("--status", action="store_true", help="Check workflow status")
    parser.add_argument("--promote", action="store_true", help="Promote target to baseline")
    
    # Test configuration
    parser.add_argument(
        "--test-mode",
        choices=[mode.value for mode in TestMode],
        default=TestMode.CONSISTENCY.value,
        help="Test mode for target creation: consistency (same inputs) or accuracy (new inputs)"
    )
    
    # File inputs
    parser.add_argument("--baseline-file", help="Existing baseline JSON file")
    parser.add_argument("--target-file", help="Target (LL2) JSON file")
    parser.add_argument("--inputs-file", help="Existing inputs JSON file")
    
    # Other options
    parser.add_argument("--num-patterns", type=int, default=10, help="Number of mock input patterns")
    parser.add_argument("--skip-evaluation", action="store_true", help="Skip LL3 evaluation step")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    parser.add_argument("--list-features", action="store_true", help="List available StudioAssist features and exit")
    
    args = parser.parse_args()
    
    if args.list_features:
        print("\nAvailable Katalon Studio StudioAssist features:")
        print("=" * 60)
        for feature, config in FEATURE_CONFIGS.items():
            print(f"\nFeature: {feature}")
            print(f"Description: {config['description']}")
            print(f"Prompt ID: {config['prompt_id']}")
            print(f"Evaluation Criteria:")
            for criterion, description in config["evaluation_criteria"].items():
                print(f"  - {criterion}: {description}")
        print("\n" + "=" * 60)
        return
    
    logger = setup_logging(args.log_level)
    
    try:
        config = load_config(args.feature)
        orchestrator = PhasedOrchestrator(config)
        
        logger.info(f"Selected StudioAssist feature: {args.feature}")
        logger.info(f"Feature description: {FEATURE_CONFIGS[args.feature]['description']}")
        
        # Check workflow status
        if args.status:
            status = orchestrator.get_workflow_status()
            print("\n" + "="*60)
            print("WORKFLOW STATUS")
            print("="*60)
            for key, value in status.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
            print("="*60 + "\n")
            return
        
        # Promote target to baseline
        if args.promote:
            asyncio.run(orchestrator.promote_target_to_baseline())
            return
        
        # Phase-based execution
        if args.phase:
            if args.phase == "baseline":
                asyncio.run(orchestrator.run_phase_1_baseline(
                    num_patterns=args.num_patterns,
                    inputs_file=args.inputs_file,
                    skip_evaluation=args.skip_evaluation
                ))
            
            elif args.phase == "target":
                test_mode = TestMode(args.test_mode)
                asyncio.run(orchestrator.run_phase_2_target(
                    test_mode=test_mode,
                    skip_evaluation=args.skip_evaluation,
                    num_patterns=args.num_patterns
                ))
            
            elif args.phase == "compare":
                asyncio.run(orchestrator.run_phase_3_compare())
        
        # Legacy step-based execution (for development)
        elif args.step:
            logger.warning("Using legacy step-based execution. Consider using phase-based workflow.")
            step = WorkflowStep(args.step)
            
            if step == WorkflowStep.GENERATE_INPUTS:
                asyncio.run(orchestrator.run_workflow_step(step, num_patterns=args.num_patterns))
            
            elif step == WorkflowStep.CREATE_BASELINE:
                if not args.inputs_file:
                    raise ValueError("--inputs-file required for baseline creation")
                
                inputs = orchestrator.file_manager.load_json(args.inputs_file)
                inputs = [inp for inp in inputs if inp.get('feature') == args.feature]
                
                asyncio.run(orchestrator.run_workflow_step(
                    step, 
                    inputs=inputs
                ))
            
            elif step == WorkflowStep.EVALUATE_BASELINE:
                if not args.baseline_file:
                    raise ValueError("--baseline-file required for evaluation")
                
                asyncio.run(orchestrator.run_workflow_step(
                    step,
                    baseline_file=args.baseline_file
                ))
            
            elif step == WorkflowStep.CREATE_TARGET:
                if not args.inputs_file:
                    raise ValueError("--inputs-file required for target creation")
                
                inputs = orchestrator.file_manager.load_json(args.inputs_file)
                inputs = [inp for inp in inputs if inp.get('feature') == args.feature]
                
                asyncio.run(orchestrator.run_workflow_step(
                    step, 
                    inputs=inputs
                ))
            
            elif step == WorkflowStep.EVALUATE_TARGET:
                if not args.target_file:
                    raise ValueError("--target-file required for evaluation")
                
                asyncio.run(orchestrator.run_workflow_step(
                    step,
                    target_file=args.target_file
                ))
            
            elif step == WorkflowStep.COMPARE_DATASETS:
                if not args.baseline_file or not args.target_file:
                    raise ValueError("Both --baseline-file and --target-file required for comparison")
                
                asyncio.run(orchestrator.run_workflow_step(
                    step,
                    baseline_file=args.baseline_file,
                    target_file=args.target_file,
                    mode=args.test_mode
                ))
        else:
            # Show help if no action specified
            parser.print_help()
            print("\n💡 TIP: Start with 'python main.py --feature generate_code --phase baseline'")
            
    except Exception as e:
        logger.error(f"Application failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()