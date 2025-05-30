"""Prompt generation utilities for Katalon StudioAssist."""

import logging
from typing import Dict, Any

from constants import FEATURE_CONFIGS  # Changed from ..constants

logger = logging.getLogger(__name__)

class KatalonPromptGenerator:
    """Generates feature-specific prompts based on Katalon Studio StudioAssist capabilities."""
    
    def __init__(self, feature: str):
        self.feature = feature
        self.config = FEATURE_CONFIGS[feature]
    
    def generate_mock_prompt(self, num_patterns: int) -> str:
        """Generate feature-specific mock data prompt."""
        if self.feature == "generate_code":
            return self._generate_code_prompt(num_patterns)
        elif self.feature == "explain_code":
            return self._explain_code_prompt(num_patterns)
        elif self.feature == "chat_window":
            return self._chat_window_prompt(num_patterns)
        else:
            raise ValueError(f"Unsupported feature: {self.feature}")
    
    def generate_evaluation_prompt(self, test_input: Dict, api_output: str) -> str:
        """Generate evaluation prompt for LL3 to assess the quality of StudioAssist output."""
        criteria = FEATURE_CONFIGS[self.feature]["evaluation_criteria"]
        
        prompt = f"""
You are an expert in Katalon Studio test automation. Please evaluate the following StudioAssist {self.feature} output.

**User Input:**
{test_input['prompt']}

**StudioAssist Output:**
{api_output}

**Evaluation Criteria:**
"""
        
        for criterion, description in criteria.items():
            prompt += f"- {criterion}: {description}\n"
        
        prompt += """

Please provide:
1. A score from 0-10 for each criterion
2. Specific feedback for each criterion
3. An overall assessment
4. Suggestions for improvement

Return your evaluation in the following JSON format:
{
  "scores": {
    "criterion_name": score (0-10),
    ...
  },
  "feedback": {
    "criterion_name": "specific feedback",
    ...
  },
  "overall_assessment": "overall evaluation summary",
  "overall_score": overall_score (0-10),
  "suggestions": ["suggestion 1", "suggestion 2", ...],
  "meets_requirements": true/false
}
"""
        return prompt

    def generate_dataset_comparison_prompt(self, baseline_info: Dict[str, Any], target_info: Dict[str, Any]) -> str:
        """Generate a prompt for comparing baseline and target datasets.
        
        Args:
            baseline_info: Information about the baseline dataset
            target_info: Information about the target dataset
            
        Returns:
            A formatted prompt string for dataset comparison
        """
        return f"""You are a highly experienced Software Quality Assurance Engineer specializing in evaluating AI model outputs. 
You are tasked with comparing and analyzing two datasets - a baseline dataset (LL1) and a target dataset (LL2).

Baseline Dataset Information:
{baseline_info}

Target Dataset Information:
{target_info}

Please analyze and compare these datasets focusing on:

1. Completeness:
   - Are all required fields present in both datasets?
   - Are there any missing or null values?
   - Compare the overall structure and organization

2. Accuracy:
   - Are the values in both datasets accurate and valid?
   - Are there any inconsistencies or anomalies?
   - Check for data type consistency

3. Consistency:
   - Are naming conventions consistent?
   - Is data formatting consistent?
   - Are there any structural differences?

4. Performance Metrics:
   - Compare key performance indicators
   - Analyze any metrics present in both datasets
   - Identify significant differences in measurements

5. Quality Assessment:
   - Evaluate the overall quality of both datasets
   - Identify areas where one dataset performs better
   - Note any quality-related concerns

Please provide your analysis in the following JSON format:
{{
  "completeness_analysis": {{
    "baseline": {{
      "missing_fields": [],
      "null_values": [],
      "structure_issues": []
    }},
    "target": {{
      "missing_fields": [],
      "null_values": [],
      "structure_issues": []
    }}
  }},
  "accuracy_analysis": {{
    "baseline": {{
      "invalid_values": [],
      "anomalies": [],
      "type_mismatches": []
    }},
    "target": {{
      "invalid_values": [],
      "anomalies": [],
      "type_mismatches": []
    }}
  }},
  "consistency_analysis": {{
    "naming_issues": [],
    "format_issues": [],
    "structural_differences": []
  }},
  "performance_comparison": {{
    "baseline_metrics": {{}},
    "target_metrics": {{}},
    "significant_differences": []
  }},
  "quality_assessment": {{
    "baseline_strengths": [],
    "baseline_weaknesses": [],
    "target_strengths": [],
    "target_weaknesses": [],
    "overall_comparison": ""
  }},
  "recommendations": []
}}"""
    
    def _generate_code_prompt(self, num_patterns: int) -> str:
        return f"""
        Generate {num_patterns} diverse code generation requests for Katalon Studio's 'Generate Code' feature.
        
        For each request, provide:
        - input_id: Unique identifier (e.g., gen_code_001, gen_code_002).
        - feature: Must be 'generate_code'.
        - prompt: Code generation request in comment format (single line or block comment).
        - config: UI settings (mode: 'script', katalon_version: '10.2.0').
        - prompt_id: Must be 'generate-code'.
        
        Follow Katalon Studio best practices:
        1. Use bullet points for multiple actions
        2. Reference test objects, variables, and specific UI elements
        3. Include browser operations, verifications, and data handling
        
        Include various test scenarios:
        - Web UI automation
        - Mobile testing
        - API testing
        - Data-driven testing
        - Custom keyword creation
        
        Return as a valid JSON array with proper escaping.
        """
    
    def _explain_code_prompt(self, num_patterns: int) -> str:
        return f"""
        Generate {num_patterns} diverse code explanation requests for Katalon Studio's 'Explain Code' feature.
        
        For each request, provide:
        - input_id: Unique identifier (e.g., explain_001, explain_002).
        - feature: Must be 'explain_code'.
        - prompt: Actual Katalon Studio code snippet that needs explanation.
        - config: UI settings (mode: 'script', katalon_version: '10.2.0').
        - prompt_id: Must be 'multi-line-explain-code'.
        
        Include various Katalon Studio code patterns like WebUI Keywords, Mobile Keywords, Custom Keywords, etc.
        
        Return as a valid JSON array with proper escaping.
        """
    
    def _chat_window_prompt(self, num_patterns: int) -> str:
        return f"""
        Generate {num_patterns} diverse chat questions for Katalon Studio's 'Chat Window' feature.
        
        For each request, provide:
        - input_id: Unique identifier (e.g., chat_001, chat_002).
        - feature: Must be 'chat_window'.
        - prompt: A question about Katalon Studio products or features.
        - config: UI settings (mode: 'chat', katalon_version: '10.2.0').
        - prompt_id: Must be 'chat-window'.
        
        Include questions about Katalon Studio features, best practices, troubleshooting, and advanced topics.
        
        Return as a valid JSON array with proper escaping.
        """