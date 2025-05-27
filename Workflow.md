Katalon StudioAssist PoC Testing Framework - User Guide
Prerequisites
1. Environment Setup
bash
Copy code
# Clone the repository
cd test_GenAI_poc

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys:
# - KATALON_API_KEY: Your Katalon API Bearer token
# - LLM3_API_KEY: Your Gemini/OpenAI API key
# - KATALON_USER_ID: Your Katalon user email
2. Verify Configuration
bash
Copy code
# List available features
python main.py --list-features

# Check current status
python main.py --feature generate_code --status
Phase-by-Phase Workflow
Phase 1: Create Baseline(s) with LL1
Purpose: Create reference datasets using the current production LLM (LL1)

bash
Copy code
# Create a baseline with 10 test patterns
python main.py --feature generate_code --phase baseline --num-patterns 10

# Create another baseline with 20 patterns (you can have multiple baselines)
python main.py --feature generate_code --phase baseline --num-patterns 20

# Create baseline without LL3 evaluation (faster, for testing)
python main.py --feature generate_code --phase baseline --skip-evaluation

# Use existing inputs file
python main.py --feature generate_code --phase baseline --inputs-file path/to/inputs.json
Output:

Mock inputs file: poc_data/generate_code/studioassist_generate_code_mock_inputs_*.json
Baseline dataset: poc_data/generate_code/studioassist_generate_code_baseline_raw_ll1_*.json
Evaluated baseline: poc_data/generate_code/studioassist_generate_code_baseline_evaluated_ll1_*.json
Phase 2: Create Target Dataset with LL2
Important: Before running Phase 2, you must reconfigure your Katalon product to use LL2!

bash
Copy code
# Run Phase 2 - you'll be prompted to select a baseline
python main.py --feature generate_code --phase target

# Run with accuracy mode (generates new test patterns)
python main.py --feature generate_code --phase target --test-mode accuracy --num-patterns 15

# Run with consistency mode (uses same inputs as selected baseline) - default
python main.py --feature generate_code --phase target --test-mode consistency

# Skip evaluation for faster testing
python main.py --feature generate_code --phase target --skip-evaluation
Interactive Selection:

markdown
Copy code
Available Baselines:
--------------------------------------------------------------------------------
ID                             Created              Inputs     State          
--------------------------------------------------------------------------------
1. baseline_20240115_093000_10    2024-01-15 09:30:00  10         EVALUATED      
2. baseline_20240115_143000_20    2024-01-15 14:30:00  20         EVALUATED      
--------------------------------------------------------------------------------

Select baseline (1-2), or 'q' to quit: 2
Phase 3: Compare Datasets
Purpose: Analyze differences between LL1 (baseline) and LL2 (target)

bash
Copy code
# Compare the datasets (uses the baseline selected in Phase 2)
python main.py --feature generate_code --phase compare
Output:

Comparison report with quality scores, consistency metrics, and recommendations
Final report: poc_data/generate_code/studioassist_generate_code_final_report_*.json
Common Workflows
1. Complete Testing Cycle
bash
Copy code
# Step 1: Create baseline with LL1
python main.py --feature generate_code --phase baseline --num-patterns 20

# Step 2: Reconfigure product to use LL2 (manual step)
# ... change your Katalon configuration ...

# Step 3: Create target with LL2 (select baseline when prompted)
python main.py --feature generate_code --phase target

# Step 4: Compare and analyze
python main.py --feature generate_code --phase compare
2. Testing Multiple LLM Configurations
bash
Copy code
# Create multiple baselines with different input sizes
python main.py --feature generate_code --phase baseline --num-patterns 10
python main.py --feature generate_code --phase baseline --num-patterns 50
python main.py --feature generate_code --phase baseline --num-patterns 100

# Later, test LL2 against the most appropriate baseline
python main.py --feature generate_code --phase target
# Select the baseline that matches your testing needs
3. Testing Different Features
bash
Copy code
# Test code generation
python main.py --feature generate_code --phase baseline

# Test code explanation
python main.py --feature explain_code --phase baseline

# Test chat functionality
python main.py --feature chat_window --phase baseline
4. Quick Development Testing
bash
Copy code
# Skip LL3 evaluation for faster iteration
python main.py --feature generate_code --phase baseline --num-patterns 5 --skip-evaluation
python main.py --feature generate_code --phase target --skip-evaluation
python main.py --feature generate_code --phase compare
Utility Commands
Check Workflow Status
bash
Copy code
python main.py --feature generate_code --status
Output example:

yaml
Copy code
WORKFLOW STATUS
==============
Feature: generate_code
Current Phase: target_created
Llm Config State: ll2_active
Num Baselines: 3
Selected Baseline: baseline_20240115_143000_20
Target Exists: True
Last Updated: 2024-01-16 15:30:00
Next Action: Run Phase 3 to compare datasets
Promote Target to Baseline
bash
Copy code
# Make the current LL2 target the new baseline for future tests
python main.py --feature generate_code --promote
Test Modes Explained
Consistency Mode (Default)
Uses the same inputs as the selected baseline
Tests if LL2 produces similar outputs for identical inputs
Best for evaluating output consistency between models
Accuracy Mode
Generates new inputs for LL2 testing
Tests LL2 performance on fresh scenarios
Best for evaluating overall model capabilities
File Organization
python
Run Code
Copy code
poc_data/
├── generate_code/
│   ├── *_mock_inputs_*.json           # Generated test inputs
│   ├── *_baseline_raw_ll1_*.json      # Raw baseline outputs
│   ├── *_baseline_evaluated_ll1_*.json # Evaluated baselines
│   ├── *_target_raw_ll2_*.json        # Raw target outputs
│   ├── *_target_evaluated_ll2_*.json  # Evaluated targets
│   ├── *_comparison_report_*.json     # Comparison results
│   └── *_final_report_*.json          # Final analysis
├── explain_code/
├── chat_window/
└── workflow_state.json                # Tracks current workflow state
Tips and Best Practices
Start Small: Begin with 5-10 test patterns to verify everything works
Always Evaluate: Skip evaluation only during development/debugging
Multiple Baselines: Create baselines with different input sizes for comprehensive testing
Document Configuration: Note which LLM configurations were used for each test
Review Reports: Always check the comparison report recommendations before making decisions