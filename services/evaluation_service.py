"""LL3 evaluation service for StudioAssist PoC with comprehensive analysis."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import asdict
from collections import defaultdict, Counter
import statistics
import re

from services.llm_service import LLMService
from utils.prompt_generator import KatalonPromptGenerator
from utils.file_manager import FeatureFileManager
from models import LLMEvaluation, StudioAssistTestResult
from constants import API_RATE_LIMIT_DELAY, FEATURE_CONFIGS

logger = logging.getLogger(__name__)

class LL3EvaluationService:
    """Service for evaluating StudioAssist outputs using LL3 with comprehensive analysis."""
    
    def __init__(self, llm_service: LLMService, prompt_generator: KatalonPromptGenerator, file_manager: FeatureFileManager):
        self.llm_service = llm_service
        self.prompt_generator = prompt_generator
        self.file_manager = file_manager
    
    async def evaluate_output(self, test_input: Dict, api_output: str) -> Optional[LLMEvaluation]:
        """Evaluate StudioAssist output using LL3."""
        eval_prompt = self.prompt_generator.generate_evaluation_prompt(test_input, api_output)
        
        eval_result = await self.llm_service.call_llm(eval_prompt, expect_json=True)
        
        if eval_result and isinstance(eval_result, dict):
            try:
                return LLMEvaluation(
                    scores=eval_result.get("scores", {}),
                    feedback=eval_result.get("feedback", {}),
                    overall_assessment=eval_result.get("overall_assessment", ""),
                    overall_score=eval_result.get("overall_score", 0.0),
                    suggestions=eval_result.get("suggestions", []),
                    meets_requirements=eval_result.get("meets_requirements", False),
                    evaluator_model=self.llm_service.config.llm3_model,
                    evaluation_timestamp=datetime.now().isoformat()
                )
            except Exception as e:
                logger.error(f"Error parsing LL3 evaluation: {e}")
                return None
        
        return None
    
    def analyze_input_diversity(self, inputs: List[Dict]) -> Dict[str, Any]:
        """Analyze the diversity of input patterns."""
        diversity_analysis = {
            "total_inputs": len(inputs),
            "unique_patterns": len(set(inp.get("prompt", "")[:50] for inp in inputs)),
            "prompt_length_stats": {},
            "pattern_categories": {},
            "complexity_distribution": {}
        }
        
        # Analyze prompt lengths
        prompt_lengths = [len(inp.get("prompt", "")) for inp in inputs]
        if prompt_lengths:
            diversity_analysis["prompt_length_stats"] = {
                "min": min(prompt_lengths),
                "max": max(prompt_lengths),
                "mean": statistics.mean(prompt_lengths),
                "median": statistics.median(prompt_lengths),
                "std_dev": statistics.stdev(prompt_lengths) if len(prompt_lengths) > 1 else 0
            }
        
        # Categorize patterns based on content
        categories = defaultdict(int)
        complexity_scores = []
        
        for inp in inputs:
            prompt = inp.get("prompt", "").lower()
            
            # Categorize by type
            if "test" in prompt or "verify" in prompt:
                categories["testing"] += 1
            if "web" in prompt or "browser" in prompt:
                categories["web_automation"] += 1
            if "mobile" in prompt or "app" in prompt:
                categories["mobile_testing"] += 1
            if "api" in prompt or "rest" in prompt:
                categories["api_testing"] += 1
            if "data" in prompt or "csv" in prompt or "excel" in prompt:
                categories["data_driven"] += 1
            if "keyword" in prompt or "function" in prompt:
                categories["custom_keywords"] += 1
            
            # Calculate complexity score
            complexity = self._calculate_prompt_complexity(prompt)
            complexity_scores.append(complexity)
        
        diversity_analysis["pattern_categories"] = dict(categories)
        
        # Complexity distribution
        if complexity_scores:
            diversity_analysis["complexity_distribution"] = {
                "low": sum(1 for s in complexity_scores if s < 3),
                "medium": sum(1 for s in complexity_scores if 3 <= s < 7),
                "high": sum(1 for s in complexity_scores if s >= 7)
            }
        
        return diversity_analysis
    
    def _calculate_prompt_complexity(self, prompt: str) -> int:
        """Calculate complexity score for a prompt."""
        complexity = 0
        
        # Check for various complexity indicators
        if len(prompt) > 200:
            complexity += 2
        if len(prompt) > 500:
            complexity += 2
        
        # Check for technical terms
        technical_terms = ["verify", "assert", "validate", "handle", "catch", "try", 
                          "loop", "iterate", "condition", "if", "else", "switch"]
        complexity += sum(1 for term in technical_terms if term in prompt.lower())
        
        # Check for multiple steps (numbered lists)
        if re.search(r'\d+\.', prompt):
            complexity += 2
        
        # Check for code snippets
        if "```" in prompt or re.search(r'[{}\[\]()]', prompt):
            complexity += 2
        
        return min(complexity, 10)  # Cap at 10
    
    def analyze_output_quality(self, results: Dict[str, StudioAssistTestResult]) -> Dict[str, Any]:
        """Analyze the quality of outputs in detail."""
        quality_analysis = {
            "total_outputs": len(results),
            "output_length_stats": {},
            "keyword_usage": {},
            "error_patterns": {},
            "response_time_analysis": {}
        }
        
        output_lengths = []
        response_times = []
        katalon_keywords = defaultdict(int)
        error_types = defaultdict(int)
        
        for result in results.values():
            output = result.api_output
            output_lengths.append(len(output))
            response_times.append(result.response_time)
            
            # Analyze Katalon keyword usage
            for keyword in ["WebUI", "Mobile", "WS", "Windows", "TestObject", 
                           "GlobalVariable", "KeywordUtil", "@Keyword"]:
                if keyword in output:
                    katalon_keywords[keyword] += output.count(keyword)
            
            # Analyze common error patterns
            if "error" in output.lower():
                error_types["error_handling"] += 1
            if "exception" in output.lower():
                error_types["exception_handling"] += 1
            if "null" in output.lower() or "none" in output.lower():
                error_types["null_checks"] += 1
        
        # Calculate statistics
        if output_lengths:
            quality_analysis["output_length_stats"] = {
                "min": min(output_lengths),
                "max": max(output_lengths),
                "mean": statistics.mean(output_lengths),
                "median": statistics.median(output_lengths),
                "std_dev": statistics.stdev(output_lengths) if len(output_lengths) > 1 else 0
            }
        
        if response_times:
            quality_analysis["response_time_analysis"] = {
                "min": min(response_times),
                "max": max(response_times),
                "mean": statistics.mean(response_times),
                "median": statistics.median(response_times),
                "percentile_95": sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
            }
        
        quality_analysis["keyword_usage"] = dict(katalon_keywords)
        quality_analysis["error_patterns"] = dict(error_types)
        
        return quality_analysis
    
    def analyze_evaluation_scores(self, results: Dict[str, StudioAssistTestResult], 
                                feature: str) -> Dict[str, Any]:
        """Analyze evaluation scores in detail for each criterion."""
        criteria = FEATURE_CONFIGS[feature]["evaluation_criteria"]
        score_analysis = {
            "criteria_analysis": {},
            "overall_statistics": {},
            "score_distribution": {},
            "correlation_analysis": {},
            "improvement_areas": []
        }
        
        # Collect scores by criterion
        criterion_scores = defaultdict(list)
        overall_scores = []
        meets_requirements_count = 0
        
        for result in results.values():
            if result.ll3_evaluation:
                overall_scores.append(result.ll3_evaluation.overall_score)
                if result.ll3_evaluation.meets_requirements:
                    meets_requirements_count += 1
                
                for criterion, score in result.ll3_evaluation.scores.items():
                    criterion_scores[criterion].append(score)
        
        # Analyze each criterion
        for criterion, description in criteria.items():
            scores = criterion_scores.get(criterion, [])
            if scores:
                analysis = {
                    "description": description,
                    "count": len(scores),
                    "mean": statistics.mean(scores),
                    "median": statistics.median(scores),
                    "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0,
                    "min": min(scores),
                    "max": max(scores),
                    "distribution": {
                        "excellent (8-10)": sum(1 for s in scores if s >= 8),
                        "good (6-8)": sum(1 for s in scores if 6 <= s < 8),
                        "fair (4-6)": sum(1 for s in scores if 4 <= s < 6),
                        "poor (0-4)": sum(1 for s in scores if s < 4)
                    }
                }
                
                # Identify if this criterion needs improvement
                if analysis["mean"] < 6:
                    score_analysis["improvement_areas"].append({
                        "criterion": criterion,
                        "mean_score": analysis["mean"],
                        "description": description
                    })
                
                score_analysis["criteria_analysis"][criterion] = analysis
        
        # Overall statistics
        if overall_scores:
            score_analysis["overall_statistics"] = {
                "mean": statistics.mean(overall_scores),
                "median": statistics.median(overall_scores),
                "std_dev": statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0,
                "min": min(overall_scores),
                "max": max(overall_scores),
                "meets_requirements_percentage": (meets_requirements_count / len(results)) * 100
            }
            
            # Score distribution
            score_analysis["score_distribution"] = {
                "0-2": sum(1 for s in overall_scores if 0 <= s < 2),
                "2-4": sum(1 for s in overall_scores if 2 <= s < 4),
                "4-6": sum(1 for s in overall_scores if 4 <= s < 6),
                "6-8": sum(1 for s in overall_scores if 6 <= s < 8),
                "8-10": sum(1 for s in overall_scores if 8 <= s <= 10)
            }
        
        # Correlation analysis between criteria
        if len(criterion_scores) > 1:
            correlations = {}
            criteria_list = list(criterion_scores.keys())
            for i, crit1 in enumerate(criteria_list):
                for crit2 in criteria_list[i+1:]:
                    if len(criterion_scores[crit1]) == len(criterion_scores[crit2]):
                        correlation = self._calculate_correlation(
                            criterion_scores[crit1], 
                            criterion_scores[crit2]
                        )
                        correlations[f"{crit1}_vs_{crit2}"] = correlation
            
            score_analysis["correlation_analysis"] = correlations
        
        return score_analysis
    
    def _calculate_correlation(self, scores1: List[float], scores2: List[float]) -> float:
        """Calculate Pearson correlation coefficient between two score lists."""
        if len(scores1) != len(scores2) or len(scores1) < 2:
            return 0.0
        
        mean1 = statistics.mean(scores1)
        mean2 = statistics.mean(scores2)
        
        numerator = sum((s1 - mean1) * (s2 - mean2) for s1, s2 in zip(scores1, scores2))
        denominator1 = sum((s - mean1) ** 2 for s in scores1)
        denominator2 = sum((s - mean2) ** 2 for s in scores2)
        
        if denominator1 == 0 or denominator2 == 0:
            return 0.0
        
        return numerator / (denominator1 * denominator2) ** 0.5
    
    def analyze_feedback_patterns(self, results: Dict[str, StudioAssistTestResult]) -> Dict[str, Any]:
        """Analyze patterns in feedback and suggestions."""
        feedback_analysis = {
            "common_feedback_themes": {},
            "suggestion_frequency": {},
            "feedback_sentiment": {
                "positive": 0,
                "neutral": 0,
                "negative": 0
            }
        }
        
        all_feedback = []
        all_suggestions = []
        
        for result in results.values():
            if result.ll3_evaluation:
                # Collect feedback
                for feedback in result.ll3_evaluation.feedback.values():
                    all_feedback.append(feedback.lower())
                
                # Collect suggestions
                all_suggestions.extend(result.ll3_evaluation.suggestions)
                
                # Analyze sentiment of overall assessment
                assessment = result.ll3_evaluation.overall_assessment.lower()
                if any(word in assessment for word in ["excellent", "great", "good", "well"]):
                    feedback_analysis["feedback_sentiment"]["positive"] += 1
                elif any(word in assessment for word in ["poor", "bad", "incorrect", "wrong"]):
                    feedback_analysis["feedback_sentiment"]["negative"] += 1
                else:
                    feedback_analysis["feedback_sentiment"]["neutral"] += 1
        
        # Analyze common themes in feedback
        theme_keywords = {
            "completeness": ["complete", "missing", "partial", "comprehensive"],
            "accuracy": ["accurate", "correct", "wrong", "error"],
            "clarity": ["clear", "unclear", "confusing", "readable"],
            "best_practices": ["practice", "convention", "standard", "pattern"],
            "error_handling": ["error", "exception", "handle", "catch"]
        }
        
        for theme, keywords in theme_keywords.items():
            count = sum(1 for feedback in all_feedback 
                       if any(keyword in feedback for keyword in keywords))
            if count > 0:
                feedback_analysis["common_feedback_themes"][theme] = count
        
        # Count suggestion frequency
        suggestion_counter = Counter(all_suggestions)
        feedback_analysis["suggestion_frequency"] = dict(suggestion_counter.most_common(10))
        
        return feedback_analysis
    
    async def evaluate_baseline_from_file(self, baseline_file: str) -> Dict[str, Any]:
        """Evaluate an entire baseline dataset from file with comprehensive analysis."""
        logger.info(f"Loading baseline from {baseline_file}")
        baseline_data = self.file_manager.load_json(baseline_file)
        
        inputs = baseline_data.get("inputs", [])
        if not inputs:
            logger.warning("No inputs found in baseline file, reconstructing from results")
            inputs = []
            for input_id, result in baseline_data.get("results", {}).items():
                inputs.append({
                    "input_id": input_id,
                    "feature": result["feature"],
                    "prompt": result["user_input"],
                    "config": result["config"],
                    "prompt_id": result["api_input"]["promptId"]
                })
        
        input_lookup = {inp["input_id"]: inp for inp in inputs}
        
        baseline_results = {}
        for input_id, result_dict in baseline_data.get("results", {}).items():
            result_dict.pop("ll3_evaluation", None)
            baseline_results[input_id] = StudioAssistTestResult(**result_dict)
        
        evaluated_results = {}
        evaluation_summary = {
            "total_evaluated": 0,
            "evaluation_errors": 0,
            "start_time": datetime.now().isoformat()
        }
        
        # Evaluate each result
        for input_id, result in baseline_results.items():
            if input_id in input_lookup:
                logger.info(f"Evaluating result for {input_id}")
                
                try:
                    evaluation = await self.evaluate_output(input_lookup[input_id], result.api_output)
                    if evaluation:
                        result.ll3_evaluation = evaluation
                        evaluation_summary["total_evaluated"] += 1
                    else:
                        logger.warning(f"No evaluation returned for {input_id}")
                        evaluation_summary["evaluation_errors"] += 1
                    
                    evaluated_results[input_id] = result
                    await asyncio.sleep(API_RATE_LIMIT_DELAY)
                    
                except Exception as e:
                    logger.error(f"Error evaluating {input_id}: {e}")
                    evaluation_summary["evaluation_errors"] += 1
                    evaluated_results[input_id] = result
            else:
                logger.warning(f"No input found for result {input_id}")
                evaluated_results[input_id] = result
        
        evaluation_summary["end_time"] = datetime.now().isoformat()
        
        # Perform comprehensive analysis
        feature = baseline_data.get("metadata", {}).get("feature", "unknown")
        
        # Input diversity analysis
        diversity_analysis = self.analyze_input_diversity(inputs)
        
        # Output quality analysis
        quality_analysis = self.analyze_output_quality(evaluated_results)
        
        # Evaluation score analysis
        score_analysis = self.analyze_evaluation_scores(evaluated_results, feature)
        
        # Feedback pattern analysis
        feedback_analysis = self.analyze_feedback_patterns(evaluated_results)
        
        # Compile comprehensive analysis
        comprehensive_analysis = {
            "summary": evaluation_summary,
            "diversity_analysis": diversity_analysis,
            "quality_analysis": quality_analysis,
            "score_analysis": score_analysis,
            "feedback_analysis": feedback_analysis,
            "insights": self._generate_insights(
                diversity_analysis, 
                quality_analysis, 
                score_analysis, 
                feedback_analysis
            )
        }
        
        # Save evaluated baseline with comprehensive analysis
        evaluated_filename = self.file_manager.generate_filename("baseline_evaluated", 
                                                               baseline_results[list(baseline_results.keys())[0]].llm_version.lower())
        evaluated_data = {
            "metadata": {
                **baseline_data.get("metadata", {}),
                "evaluation_metadata": {
                    "evaluator_model": self.llm_service.config.llm3_model,
                    "evaluation_timestamp": datetime.now().isoformat(),
                    "original_baseline_file": baseline_file
                }
            },
            "inputs": inputs,
            "results": {k: asdict(v) for k, v in evaluated_results.items()},
            "comprehensive_analysis": comprehensive_analysis
        }
        self.file_manager.save_json(evaluated_data, evaluated_filename)
        
        # Save analysis report separately for easy access
        analysis_filename = self.file_manager.generate_filename("analysis_report", 
                                                              baseline_results[list(baseline_results.keys())[0]].llm_version.lower())
        self.file_manager.save_json(comprehensive_analysis, analysis_filename)
        logger.info(f"Comprehensive analysis saved to {analysis_filename}")
        
        return {
            "evaluated_results": evaluated_results,
            "evaluated_filename": str(evaluated_filename),
            "analysis_filename": str(analysis_filename),
            "comprehensive_analysis": comprehensive_analysis
        }
    
    def _generate_insights(self, diversity: Dict, quality: Dict, 
                          scores: Dict, feedback: Dict) -> List[str]:
        """Generate actionable insights from the analysis."""
        insights = []
        
        # Diversity insights
        if diversity["total_inputs"] < 10:
            insights.append("Limited test coverage: Consider increasing the number of test patterns for more comprehensive evaluation.")
        
        if diversity.get("complexity_distribution", {}).get("low", 0) > diversity["total_inputs"] * 0.7:
            insights.append("Low complexity bias: Most test inputs are simple. Add more complex scenarios for thorough testing.")
        
        # Quality insights
        avg_response_time = quality.get("response_time_analysis", {}).get("mean", 0)
        if avg_response_time > 5:
            insights.append(f"High average response time ({avg_response_time:.2f}s): Consider optimizing API calls or implementing caching.")
        
        # Score insights
        improvement_areas = scores.get("improvement_areas", [])
        if improvement_areas:
            areas = ", ".join([area["criterion"] for area in improvement_areas])
            insights.append(f"Improvement needed in: {areas}. Focus on enhancing these aspects of the output.")
        
        overall_mean = scores.get("overall_statistics", {}).get("mean", 0)
        if overall_mean < 6:
            insights.append("Overall quality below expectations: Review prompt engineering and model configuration.")
        elif overall_mean > 8:
            insights.append("Excellent overall performance: The current configuration is producing high-quality outputs.")
        
        # Feedback insights
        negative_sentiment = feedback.get("feedback_sentiment", {}).get("negative", 0)
        total_sentiment = sum(feedback.get("feedback_sentiment", {}).values())
        if total_sentiment > 0 and negative_sentiment / total_sentiment > 0.3:
            insights.append("High negative feedback ratio: Review common failure patterns and address systematic issues.")
        
        # Correlation insights
        correlations = scores.get("correlation_analysis", {})
        for correlation_pair, value in correlations.items():
            if abs(value) > 0.7:
                insights.append(f"Strong correlation between {correlation_pair} ({value:.2f}): These criteria are closely related.")
        
        return insights