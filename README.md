# Katalon Studio StudioAssist PoC Testing Framework

A comprehensive testing framework for evaluating and comparing different LLM implementations of Katalon Studio's StudioAssist feature.

## Overview

This framework implements a phased testing approach to evaluate and compare different LLM (Language Learning Model) implementations for Katalon Studio's StudioAssist feature. It supports:

- Baseline creation with LL1 (Phase 1)
- Target dataset creation with LL2 (Phase 2)
- Comprehensive comparison and evaluation (Phase 3)

## Features

- **Phased Testing Workflow**:
  - Phase 1: Create baseline datasets using LL1
  - Phase 2: Create target datasets using LL2
  - Phase 3: Compare and evaluate results

- **Comprehensive Evaluation**:
  - Output stability analysis
  - Behavior consistency checks
  - Code quality assessment
  - Performance metrics
  - Detailed comparison reports

- **Flexible Configuration**:
  - Support for multiple LLM providers
  - Configurable through environment variables or config file
  - Feature-specific testing parameters

## Prerequisites

- Python 3.8+
- Katalon Studio Enterprise (KSE) license
- Access to LLM APIs (LL1, LL2, LL3)
- Required environment variables (see Configuration section)

## Installation

1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd Katalon_Test_GenAI
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables (see Configuration section)

## Configuration

### Environment Variables

Key environment variables:

```bash
# Required
KATALON_API_KEY=your_katalon_api_key
LLM3_API_KEY=your_llm3_api_key

# Optional with defaults
KATALON_API_URL=default_url
LLM3_PROVIDER=gemini
LLM3_MODEL=gemini-pro
KATALON_VERSION=10.2.0

# LLM Configuration
LL1_CONFIG_TYPE=katalon_ai
LL1_API_KEY=your_ll1_api_key
LL1_MODEL=gpt-4o-mini

LL2_CONFIG_TYPE=personal_openai
LL2_API_KEY=your_ll2_api_key
LL2_MODEL=gpt-4o-mini
```

### Configuration File

Alternatively, create a `config.json` file:

```json
{
  "katalon_api_url": "your_api_url",
  "katalon_api_key": "your_api_key",
  "llm3_provider": "gemini",
  "llm3_api_key": "your_llm3_key",
  "feature": "generate_code",
  "kse_license": true
}
```

## Usage

### Basic Workflow

1. **Create Baseline (Phase 1)**:
   ```bash
   python main.py --feature generate_code --phase baseline
   ```

2. **Create Target (Phase 2)**:
   ```bash
   python main.py --feature generate_code --phase target
   ```

3. **Compare Results (Phase 3)**:
   ```bash
   python main.py --feature generate_code --phase compare
   ```

### Additional Commands

- Check workflow status:
  ```bash
  python main.py --feature generate_code --status
  ```

- Promote target to baseline:
  ```bash
  python main.py --feature generate_code --promote
  ```

- List available features:
  ```bash
  python main.py --list-features
  ```

### Test Modes

- **Consistency Mode**: Uses same inputs for LL1 and LL2
- **Accuracy Mode**: Uses different inputs to test adaptability

## Project Structure

```
Katalon_Test_GenAI/
├── main.py                 # Main entry point
├── config.py              # Configuration management
├── constants.py           # Constants and enums
├── phased_orchestrator.py # Core testing workflow
├── services/             # Service implementations
├── utils/               # Utility functions
└── poc_data/           # Test data directory
```

## Evaluation Criteria

The framework evaluates LLM implementations based on:

1. **Consistency Metrics**:
   - Output Stability (0-1)
   - Behavior Consistency (0-1)
   - Style Consistency (0-1)

2. **Accuracy Metrics**:
   - Functional Correctness (0-1)
   - Code Quality (0-1)
   - Test Coverage (0-1)

3. **Performance Metrics**:
   - Execution Time
   - Resource Usage
   - Response Time

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your License Information]

## Support

For support, please contact [Your Contact Information]
