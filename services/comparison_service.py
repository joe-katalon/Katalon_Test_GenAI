"""Comparison service for analyzing baseline vs target datasets."""

import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import asdict
import statistics
from collections import defaultdict

from models import StudioAssistTestResult
from constants import FEATURE_CONFIGS

logger = logging.getLogger(__name__)

class DatasetComparisonService:
    """Service for comparing baseline (LL1) and target (LL2) datasets."""
    
    def __init__(self, file_manager):
        self.file_manager = file_manager
    
    def compare_datasets(self, baseline_data: Dict, target_data: Dict, 
                        feature: str, mode: str = "consistency") -> Dict[str, Any]:
        """Compare baseline and target datasets comprehensively."""
        logger.info(f"Comparing datasets for {feature} in {mode} mode")
        
        comparison_result = {
            "metadata": {
                "feature": feature,
                "comparison_mode": mode,
                "timestamp": datetime.now().isoformat(),
                "baseline_info": baseline_data.get("metadata", {}),
                "target_info": target_data.get("metadata", {})
            },
            "summary": self._generate_summary(baseline_data, target_data, mode),
            "quality_comparison": self._compare_quality_scores(baseline_data, target_data, feature),
            "output_comparison": self._compare_outputs(baseline_data, target_data, mode),
            "performance_comparison": self._compare_performance(baseline_data, target_data),
            "consistency_metrics": self._calculate_consistency_metrics(baseline_data, target_data) if mode == "consistency" else None,
            "insights": [],
            "recommendation": {}
        }
        
        # Generate insights based on comparison
        comparison_result["insights"] = self._generate_insights(comparison_result)
        
        # Generate recommendation
        comparison_result["recommendation"] = self._generate_recommendation(comparison_result)
        
        # Save comparison report
        filename = self.file_manager.generate_filename("comparison_report", f"{mode}_ll1_vs_ll2")
        self.file_manager.save_json(comparison_result, filename)
        
        return comparison_result
    
    def _generate_summary(self, baseline_data: Dict, target_data: Dict, mode: str) -> Dict:
        """Generate comparison summary."""
        baseline_results = baseline_data.get("results", {})
        target_results = target_data.get("results", {})
        
        if mode == "consistency":
            # Same inputs, check overlap
            common_inputs = set(baseline_results.keys()) & set(target_results.keys())
            return {
                "baseline_count": len(baseline_results),
                "target_count": len(target_results),
                "common_inputs": len(common_inputs),
                "comparison_coverage": len(common_inputs) / len(baseline_results) if baseline_results else 0
            }
        else:
            # Different inputs for accuracy testing
            return {
                "baseline_count": len(baseline_results),
                "target_count": len(target_results),
                "input_overlap": len(set(baseline_results.keys()) & set(target_results.keys()))
            }
    
    def _compare_quality_scores(self, baseline_data: Dict, target_data: Dict, feature: str) -> Dict:
        """Compare quality scores between datasets."""
        criteria = FEATURE_CONFIGS[feature]["evaluation_criteria"]
        
        baseline_scores = self._extract_scores(baseline_data.get("results", {}))
        target_scores = self._extract_scores(target_data.get("results", {}))
        
        comparison = {
            "criteria_comparison": {},
            "overall_comparison": {},
            "improvement_analysis": {}
        }
        
        # Compare each criterion
        for criterion in criteria:
            baseline_criterion_scores = baseline_scores.get(criterion, [])
            target_criterion_scores = target_scores.get(criterion, [])
            
            if baseline_criterion_scores and target_criterion_scores:
                baseline_mean = statistics.mean(baseline_criterion_scores)
                target_mean = statistics.mean(target_criterion_scores)
                
                comparison["criteria_comparison"][criterion] = {
                    "baseline_mean": baseline_mean,
                    "target_mean": target_mean,
                    "difference": target_mean - baseline_mean,
                    "percent_change": ((target_mean - baseline_mean) / baseline_mean * 100) if baseline_mean > 0 else 0,
                    "improved": target_mean > baseline_mean
                }
        
        # Overall comparison
        baseline_overall = baseline_scores.get("overall", [])
        target_overall = target_scores.get("overall", [])
        
        if baseline_overall and target_overall:
            comparison["overall_comparison"] = {
                "baseline_mean": statistics.mean(baseline_overall),
                "target_mean": statistics.mean(target_overall),
                "baseline_std": statistics.stdev(baseline_overall) if len(baseline_overall) > 1 else 0,
                "target_std": statistics.stdev(target_overall) if len(target_overall) > 1 else 0,
                "statistical_significance": self._calculate_statistical_significance(baseline_overall, target_overall)
            }
        
        # Improvement analysis
        improvements = sum(1 for c in comparison["criteria_comparison"].values() if c["improved"])
        comparison["improvement_analysis"] = {
            "improved_criteria": improvements,
            "degraded_criteria": len(criteria) - improvements,
            "improvement_rate": improvements / len(criteria) if criteria else 0
        }
        
        return comparison
    
    def _extract_scores(self, results: Dict) -> Dict[str, List[float]]:
        """Extract scores from results."""
        scores = defaultdict(list)
        
        for result_data in results.values():
            if isinstance(result_data, dict) and "ll3_evaluation" in result_data:
                eval_data = result_data["ll3_evaluation"]
                if eval_data and "scores" in eval_data:
                    for criterion, score in eval_data["scores"].items():
                        scores[criterion].append(score)
                if eval_data and "overall_score" in eval_data:
                    scores["overall"].append(eval_data["overall_score"])
        
        return dict(scores)
    
    def _compare_outputs(self, baseline_data: Dict, target_data: Dict, mode: str) -> Dict:
        """Compare the actual outputs between datasets."""
        comparison = {
            "length_comparison": {},
            "similarity_metrics": {},
            "keyword_analysis": {}
        }
        
        baseline_results = baseline_data.get("results", {})
        target_results = target_data.get("results", {})
        
        if mode == "consistency":
            # Compare same inputs
            common_inputs = set(baseline_results.keys()) & set(target_results.keys())
            
            similarities = []
            length_diffs = []
            
            for input_id in common_inputs:
                baseline_output = baseline_results[input_id].get("api_output", "")
                target_output = target_results[input_id].get("api_output", "")
                
                # Calculate similarity
                similarity = self._calculate_text_similarity(baseline_output, target_output)
                similarities.append(similarity)
                
                # Calculate length difference
                length_diff = len(target_output) - len(baseline_output)
                length_diffs.append(length_diff)
            
            if similarities:
                comparison["similarity_metrics"] = {
                    "mean_similarity": statistics.mean(similarities),
                    "min_similarity": min(similarities),
                    "max_similarity": max(similarities),
                    "high_similarity_count": sum(1 for s in similarities if s > 0.8)
                }
            
            if length_diffs:
                comparison["length_comparison"] = {
                    "mean_difference": statistics.mean(length_diffs),
                    "longer_outputs": sum(1 for d in length_diffs if d > 0),
                    "shorter_outputs": sum(1 for d in length_diffs if d < 0),
                    "same_length": sum(1 for d in length_diffs if d == 0)
                }
        
        return comparison
    
    def _compare_performance(self, baseline_data: Dict, target_data: Dict) -> Dict:
        """Compare performance metrics between datasets."""
        baseline_times = []
        target_times = []
        
        for result in baseline_data.get("results", {}).values():
            if "response_time" in result:
                baseline_times.append(result["response_time"])
        
        for result in target_data.get("results", {}).values():
            if "response_time" in result:
                target_times.append(result["response_time"])
        
        comparison = {}
        
        if baseline_times and target_times:
            comparison = {
                "baseline_avg_time": statistics.mean(baseline_times),
                "target_avg_time": statistics.mean(target_times),
                "time_difference": statistics.mean(target_times) - statistics.mean(baseline_times),
                "baseline_p95": sorted(baseline_times)[int(len(baseline_times) * 0.95)] if baseline_times else 0,
                "target_p95": sorted(target_times)[int(len(target_times) * 0.95)] if target_times else 0
            }
        
        return comparison
    
    def _calculate_consistency_metrics(self, baseline_data: Dict, target_data: Dict) -> Dict:
        """Calculate consistency metrics for same inputs."""
        baseline_results = baseline_data.get("results", {})
        target_results = target_data.get("results", {})
        
        common_inputs = set(baseline_results.keys()) & set(target_results.keys())
        
        consistency_scores = []
        output_variations = []
        
        for input_id in common_inputs:
            baseline_result = baseline_results[input_id]
            target_result = target_results[input_id]
            
            # Compare outputs
            baseline_output = baseline_result.get("api_output", "")
            target_output = target_result.get("api_output", "")
            
            # Calculate consistency score
            similarity = self._calculate_text_similarity(baseline_output, target_output)
            consistency_scores.append(similarity)
            
            # Track variations
            if similarity < 0.9:  # Significant variation threshold
                output_variations.append({
                    "input_id": input_id,
                    "similarity": similarity,
                    "baseline_length": len(baseline_output),
                    "target_length": len(target_output)
                })
        
        return {
            "overall_consistency": statistics.mean(consistency_scores) if consistency_scores else 0,
            "consistency_std": statistics.stdev(consistency_scores) if len(consistency_scores) > 1 else 0,
            "high_consistency_rate": sum(1 for s in consistency_scores if s > 0.9) / len(consistency_scores) if consistency_scores else 0,
            "significant_variations": len(output_variations),
            "variation_details": output_variations[:5]  # Top 5 variations
        }
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1 scale)."""
        if not text1 or not text2:
            return 0.0 if text1 != text2 else 1.0
        
        # Simple character-based Jaccard similarity
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())
        
        intersection = set1 & set2
        union = set1 | set2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_statistical_significance(self, scores1: List[float], scores2: List[float]) -> Dict:
        """Calculate statistical significance of score differences."""
        if len(scores1) < 2 or len(scores2) < 2:
            return {"significant": False, "p_value": None}
        
        # Simple t-test approximation
        mean1 = statistics.mean(scores1)
        mean2 = statistics.mean(scores2)
        std1 = statistics.stdev(scores1)
        std2 = statistics.stdev(scores2)
        n1 = len(scores1)
        n2 = len(scores2)
        
        # Pooled standard error
        se = ((std1**2 / n1) + (std2**2 / n2)) ** 0.5
        
        if se == 0:
            return {"significant": False, "p_value": None}
        
        # t-statistic
        t_stat = (mean2 - mean1) / se
        
        # Approximate p-value (simplified)
        p_value = 2 * (1 - min(0.99, abs(t_stat) / 4))  # Rough approximation
        
        return {
            "significant": p_value < 0.05,
            "p_value": p_value,
            "t_statistic": t_stat
        }
    
    def _generate_insights(self, comparison: Dict) -> List[str]:
        """Generate insights from comparison results."""
        insights = []
        
        # Quality insights
        quality_comp = comparison.get("quality_comparison", {})
        if quality_comp.get("overall_comparison", {}):
            overall = quality_comp["overall_comparison"]
            if overall.get("target_mean", 0) > overall.get("baseline_mean", 0):
                improvement = overall["target_mean"] - overall["baseline_mean"]
                insights.append(f"LL2 shows {improvement:.1f} point improvement in overall quality score")
            else:
                degradation = overall["baseline_mean"] - overall["target_mean"]
                insights.append(f"LL2 shows {degradation:.1f} point degradation in overall quality score")
        
        # Consistency insights
        if comparison.get("consistency_metrics"):
            consistency = comparison["consistency_metrics"]["overall_consistency"]
            if consistency > 0.9:
                insights.append(f"High consistency between LL1 and LL2 outputs ({consistency:.1%})")
            elif consistency < 0.7:
                insights.append(f"Low consistency between LL1 and LL2 outputs ({consistency:.1%}) - significant variations detected")
        
        # Performance insights
        perf_comp = comparison.get("performance_comparison", {})
        if perf_comp:
            time_diff = perf_comp.get("time_difference", 0)
            if abs(time_diff) > 0.5:
                if time_diff > 0:
                    insights.append(f"LL2 is {time_diff:.1f}s slower on average than LL1")
                else:
                    insights.append(f"LL2 is {abs(time_diff):.1f}s faster on average than LL1")
        
        # Improvement insights
        improvement_analysis = quality_comp.get("improvement_analysis", {})
        if improvement_analysis:
            improved = improvement_analysis.get("improved_criteria", 0)
            total = improvement_analysis.get("improved_criteria", 0) + improvement_analysis.get("degraded_criteria", 0)
            if total > 0:
                insights.append(f"{improved}/{total} evaluation criteria showed improvement with LL2")
        
        return insights
    
    def _generate_recommendation(self, comparison: Dict) -> Dict:
        """Generate recommendation based on comparison results."""
        recommendation = {
            "decision": "UNDECIDED",
            "confidence": "low",
            "reasons": [],
            "risks": [],
            "benefits": []
        }
        
        # Decision logic
        quality_comp = comparison.get("quality_comparison", {})
        overall_comp = quality_comp.get("overall_comparison", {})
        consistency = comparison.get("consistency_metrics", {}).get("overall_consistency", 0)
        
        baseline_score = overall_comp.get("baseline_mean", 0)
        target_score = overall_comp.get("target_mean", 0)
        score_improvement = target_score - baseline_score
        
        # Decision criteria
        if score_improvement > 0.5 and consistency > 0.8:
            recommendation["decision"] = "RECOMMEND_LL2"
            recommendation["confidence"] = "high"
            recommendation["reasons"].append(f"Significant quality improvement ({score_improvement:.1f} points)")
            recommendation["reasons"].append(f"High output consistency ({consistency:.1%})")
            recommendation["benefits"].append("Better quality outputs while maintaining consistency")
        elif score_improvement > 0 and consistency > 0.7:
            recommendation["decision"] = "CONSIDER_LL2"
            recommendation["confidence"] = "medium"
            recommendation["reasons"].append(f"Moderate quality improvement ({score_improvement:.1f} points)")
            recommendation["reasons"].append(f"Acceptable output consistency ({consistency:.1%})")
            recommendation["risks"].append("Some output variations may affect user experience")
        elif score_improvement < -0.5 or consistency < 0.6:
            recommendation["decision"] = "KEEP_LL1"
            recommendation["confidence"] = "high"
            recommendation["reasons"].append("Quality degradation or low consistency detected")
            recommendation["risks"].append("LL2 may produce inconsistent or lower quality outputs")
        else:
            recommendation["decision"] = "NEEDS_MORE_TESTING"
            recommendation["confidence"] = "low"
            recommendation["reasons"].append("Inconclusive results - marginal differences detected")
            recommendation["risks"].append("More comprehensive testing needed for confident decision")
        
        return recommendation