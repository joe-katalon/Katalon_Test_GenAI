"""Module for generating HTML comparison reports."""

import os
import json
from datetime import datetime
from typing import Dict, Any
from jinja2 import Template
from dotenv import load_dotenv

class ReportGenerator:
    """Generates HTML reports for comparison results."""
    
    def __init__(self, config):
        """Initialize with config instance."""
        self.config = config
    
    def _get_report_data(self, comparison_data: Dict[str, Any], baseline_info: Dict[str, Any], target_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and structure report data consistently for both print and HTML output.
        
        Args:
            comparison_data: Raw comparison data from LLM3
            baseline_info: Information about the baseline dataset
            target_info: Information about the target dataset
            
        Returns:
            Dict containing structured report data
        """
        raw_eval = comparison_data.get("raw_evaluation", {})
        metrics = comparison_data.get("metrics", {})
        
        # Get user and organization info from environment
        user_info = {
            "user_id": os.getenv("KATALON_USER_ID", "unknown"),
            "user_id_numeric": os.getenv("KATALON_USER_ID_NUMERIC", "unknown"),
            "account_id": os.getenv("KATALON_ACCOUNT_ID", "unknown"),
            "org_id": os.getenv("KATALON_ORG_ID", "unknown")
        }
        
        # Format dataset summary with passed in data
        dataset_summary = (
            f"📌 Baseline (LL1) results: {baseline_info.get('num_inputs', 'unknown')}\n"
            f"🎯 Target (LL2) results: {target_info.get('num_inputs', 'unknown')}\n"
        )
        
        # Get consistency scores
        consistency_scores = raw_eval.get("consistency_scores", {})
        output_stability = consistency_scores.get('output_stability', 0)
        behavior_consistency = consistency_scores.get('behavior_consistency', 0)
        style_consistency = consistency_scores.get('style_consistency', 0)
        
        # Get accuracy scores
        accuracy_scores = raw_eval.get("accuracy_scores", {})
        functional = accuracy_scores.get('functional_correctness', 0)
        code_quality = accuracy_scores.get('code_quality', 0)
        test_coverage = accuracy_scores.get('test_coverage', 0)
        
        # Format consistency scores
        detailed_scores_consistency = (
            f"{'🟢' if output_stability >= 0.8 else '🟡' if output_stability >= 0.6 else '🔴'} Output Stability: {output_stability:.2f}\n"
            f"{'🟢' if behavior_consistency >= 0.8 else '🟡' if behavior_consistency >= 0.6 else '🔴'} Behavior Consistency: {behavior_consistency:.2f}\n"
            f"{'🟢' if style_consistency >= 0.8 else '🟡' if style_consistency >= 0.6 else '🔴'} Style Consistency: {style_consistency:.2f}"
        )
        
        # Format accuracy scores
        detailed_scores_accuracy = (
            f"{'🟢' if functional >= 0.8 else '🟡' if functional >= 0.6 else '🔴'} Functional Correctness: {functional:.2f}\n"
            f"{'🟢' if code_quality >= 0.8 else '🟡' if code_quality >= 0.6 else '🔴'} Code Quality: {code_quality:.2f}\n"
            f"{'🟢' if test_coverage >= 0.8 else '🟡' if test_coverage >= 0.6 else '🔴'} Test Coverage: {test_coverage:.2f}"
        )
        
        # Get performance metrics
        perf_metrics = raw_eval.get("performance_metrics", {})
        time_diff = perf_metrics.get('time_difference', 0)
        
        # Get analysis details
        analysis = raw_eval.get("analysis", {})
        
        # Format detailed scores
        detailed_scores = (
            "🎯 Consistency Metrics:\n"
            f"  {'🟢' if output_stability >= 0.8 else '🟡' if output_stability >= 0.6 else '🔴'} Output Stability: {output_stability:.2f}\n"
            f"  {'🟢' if behavior_consistency >= 0.8 else '🟡' if behavior_consistency >= 0.6 else '🔴'} Behavior Consistency: {behavior_consistency:.2f}\n"
            f"  {'🟢' if style_consistency >= 0.8 else '🟡' if style_consistency >= 0.6 else '🔴'} Style Consistency: {style_consistency:.2f}\n\n"
            "✅ Accuracy Metrics:\n"
            f"  {'🟢' if functional >= 0.8 else '🟡' if functional >= 0.6 else '🔴'} Functional Correctness: {functional:.2f}\n"
            f"  {'🟢' if code_quality >= 0.8 else '🟡' if code_quality >= 0.6 else '🔴'} Code Quality: {code_quality:.2f}\n"
            f"  {'🟢' if test_coverage >= 0.8 else '🟡' if test_coverage >= 0.6 else '🔴'} Test Coverage: {test_coverage:.2f}"
        )
        
        # Format performance analysis
        performance_analysis = (
            f"⏱️ Baseline Avg Time: {perf_metrics.get('baseline_avg_time', 0):.3f}s\n"
            f"⏱️ Target Avg Time: {perf_metrics.get('target_avg_time', 0):.3f}s\n"
            f"{'🟢' if time_diff < 0 else '🔴' if time_diff > 0 else '⚪'} Time Difference: {time_diff:+.3f}s"
        )
        
        # Format detailed analysis sections
        key_differences = "\n".join(f"• {diff}" for diff in analysis.get("key_differences", []))
        improvements = "\n".join(f"✅ {imp}" for imp in analysis.get("improvements", []))
        regressions = "\n".join(f"❌ {reg}" for reg in analysis.get("regressions", []))
        concerns = "\n".join(f"⚠️ {concern}" for concern in analysis.get("concerns", []))
        
        # Format recommendations
        recommendations = "\n".join(f"{i}. {rec}" for i, rec in enumerate(raw_eval.get("recommendations", []), 1))
        
        # Get final recommendation and confidence
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
        
        final_assessment = (
            f"{rec_emoji.get(final_rec, '❓')} Decision: {final_rec}\n"
            f"{conf_emoji.get(confidence, '❓')} Confidence Level: {confidence}"
        )
        
        return {
            "dataset_summary": dataset_summary,
            "detailed_scores": detailed_scores,
            "detailed_scores_consistency": detailed_scores_consistency,
            "detailed_scores_accuracy": detailed_scores_accuracy,
            "performance_analysis": performance_analysis,
            "detailed_analysis": key_differences,
            "improvements": improvements,
            "regressions": regressions,
            "concerns": concerns,
            "recommendations": recommendations,
            "final_assessment": final_assessment,
            "detailed_explanation": raw_eval.get("detailed_explanation", ""),
            "decision": comparison_data.get("decision", ""),
            "confidence": comparison_data.get("confidence", ""),
            "llm_configs": {
                "ll1": {
                    "type": os.getenv("LL1_CONFIG_TYPE", "unknown"),
                    "model": os.getenv("LL1_MODEL", "unknown"),
                    "description": "Baseline Model"
                },
                "ll2": {
                    "type": os.getenv("LL2_CONFIG_TYPE", "unknown"),
                    "model": os.getenv("LL2_MODEL", "unknown"),
                    "description": "Target Model"
                },
                "llm3": {
                    "provider": os.getenv("LLM3_PROVIDER", "unknown"),
                    "model": os.getenv("LLM3_MODEL", "unknown"),
                    "type": "evaluation"
                }
            },
            "user_info": user_info
        }
    
    def generate_html_report(self, feature: str, comparison_data: Dict[str, Any], baseline_info: Dict[str, Any], 
                         target_info: Dict[str, Any]) -> str:
        """Generate an HTML report from comparison data."""
        # Load environment variables
        load_dotenv()
        
        # Load the full dataset content from referenced files
        baseline_dataset = {}
        target_dataset = {}
        
        # Get the baseline dataset file path and load content
        baseline_file = baseline_info.get("filename")
        if baseline_file and os.path.exists(baseline_file):
            try:
                with open(baseline_file, 'r') as f:
                    baseline_dataset = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load baseline dataset file {baseline_file}: {e}")
        
        # Get the target dataset file path and load content
        target_file = target_info.get("filename")
        if target_file and os.path.exists(target_file):
            try:
                with open(target_file, 'r') as f:
                    target_dataset = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load target dataset file {target_file}: {e}")
        
        # Format JSON data for display - use full dataset content
        baseline_json = json.dumps(baseline_dataset if baseline_dataset else {"error": "Could not load baseline dataset", "file": baseline_file}, indent=2)
        target_json = json.dumps(target_dataset if target_dataset else {"error": "Could not load target dataset", "file": target_file}, indent=2)
        
        # Get structured report data
        report_data = self._get_report_data(comparison_data, baseline_info, target_info)
        
        # Get LLM configurations directly from environment
        llm_configs = {
            "ll1": {
                "type": os.getenv("LL1_CONFIG_TYPE", "unknown"),
                "model": os.getenv("LL1_MODEL", "unknown"),
                "description": "Baseline Model"
            },
            "ll2": {
                "type": os.getenv("LL2_CONFIG_TYPE", "unknown"),
                "model": os.getenv("LL2_MODEL", "unknown"),
                "description": "Target Model"
            },
            "llm3": {
                "provider": os.getenv("LLM3_PROVIDER", "unknown"),
                "model": os.getenv("LLM3_MODEL", "unknown"),
                "type": "evaluation"
            }
        }
        
        # Prepare template data
        template_data = {
            "feature": feature,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_year": datetime.now().year,
            "katalon_version": self.config.katalon_version,
            "baseline_info": baseline_info,
            "target_info": target_info,
            "report_data": report_data,
            "baseline_json": baseline_json,
            "target_json": target_json,
            "test_mode": comparison_data.get("test_mode", "unknown"),
            "detailed_results": comparison_data.get("detailed_results", []),
            "llm_configs": llm_configs,
            "baseline_file": baseline_file,
            "target_file": target_file
        }
        
        # Generate report
        template = Template('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta name="referrer" content="origin">
            <title>StudioAssist Comparison Report - {{ feature }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 0;
                    background: #f5f5f5;
                }
                .header {
                    background: #fff;
                    padding: 20px;
                    border-bottom: 1px solid #dee2e6;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    position: sticky;
                    top: 0;
                    z-index: 100;
                }
                .header-content {
                    max-width: 1200px;
                    margin: 0 auto;
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    padding: 10px 20px;
                }
                .logo {
                    height: 32px;
                    width: auto;
                    margin-right: 15px;
                }
                .header-title {
                    font-size: 1.5em;
                    color: #333;
                    margin: 0;
                    flex: 1;
                }
                .container {
                    max-width: 1200px;
                    margin: 20px auto;
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                h1, h2 {
                    color: #333;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                }
                .summary-box {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 15px;
                    margin: 10px 0;
                }
                .metric {
                    display: flex;
                    justify-content: space-between;
                    margin: 5px 0;
                    padding: 5px 0;
                    border-bottom: 1px solid #eee;
                }
                .metric-label {
                    font-weight: bold;
                }
                .score {
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                .good { background: #d4edda; color: #155724; }
                .warning { background: #fff3cd; color: #856404; }
                .poor { background: #f8d7da; color: #721c24; }
                .comparison-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }
                .comparison-table th, .comparison-table td {
                    padding: 12px;
                    border: 1px solid #dee2e6;
                    text-align: left;
                }
                .comparison-table th {
                    background: #f8f9fa;
                }
                .timestamp {
                    color: #6c757d;
                    font-size: 0.9em;
                }
                .decision {
                    font-size: 1.2em;
                    font-weight: bold;
                    padding: 10px;
                    margin: 10px 0;
                    border-radius: 4px;
                }
                .decision.promote { background: #d4edda; color: #155724; }
                .decision.keep { background: #f8d7da; color: #721c24; }
                .decision.testing { background: #fff3cd; color: #856404; }
                .insights li {
                    margin-bottom: 8px;
                }
                .json-view {
                    font-family: monospace;
                    white-space: pre;
                    background: #f8f9fa;
                    padding: 10px;
                    border-radius: 4px;
                    max-height: 400px;
                    overflow: auto;
                    display: none;
                }
                .json-container {
                    background: #fff;
                    border: 1px solid #dee2e6;
                    border-radius: 0 0 4px 4px;
                    padding: 15px;
                    height: 400px; /* Increased height for better visibility */
                    min-height: 400px; /* Ensure minimum height */
                    max-height: 400px; /* Ensure maximum height */
                    overflow: auto; /* Always show scrollbar when needed */
                    position: relative;
                }
                .json-tree {
                    height: 100%;
                    overflow: auto;
                    padding-right: 10px;
                }
                .json-tree .hidden {
                    display: none;
                }
                .json-tree .expanded {
                    display: block;
                }
                /* Ensure long content wraps and scrolls */
                .json-tree .json-string,
                .json-tree .json-key,
                .json-tree .preview {
                    word-break: break-all;
                    white-space: pre-wrap;
                }
                /* Make indent consistent */
                .json-tree .indent {
                    margin-left: 20px;
                    padding-left: 10px;
                    border-left: 1px dotted #ddd;
                }
                /* Custom scrollbar styling for JSON containers */
                .json-container::-webkit-scrollbar,
                .json-tree::-webkit-scrollbar {
                    width: 8px;
                    height: 8px;
                }
                .json-container::-webkit-scrollbar-track,
                .json-tree::-webkit-scrollbar-track {
                    background: #f1f1f1;
                    border-radius: 4px;
                }
                .json-container::-webkit-scrollbar-thumb,
                .json-tree::-webkit-scrollbar-thumb {
                    background: #888;
                    border-radius: 4px;
                }
                .json-container::-webkit-scrollbar-thumb:hover,
                .json-tree::-webkit-scrollbar-thumb:hover {
                    background: #555;
                }
                .json-comparison {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin: 20px 0;
                    overflow-x: auto;
                }
                .json-column {
                    background: #ffffff;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 15px;
                    min-width: 400px;
                }
                .json-column h3 {
                    margin-top: 0;
                    color: #007bff;
                    border-bottom: 2px solid #dee2e6;
                    padding-bottom: 10px;
                    margin-bottom: 15px;
                }
                .json-preview {
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
                    font-size: 13px;
                    line-height: 1.5;
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 4px;
                    overflow-x: auto;
                    max-height: 400px;
                    overflow-y: auto;
                }
                .summary-insights {
                    background: #fff;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 20px;
                    margin: 20px 0;
                }
                .summary-insights h3 {
                    color: #007bff;
                    margin-top: 0;
                }
                .insights-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-top: 15px;
                }
                .insight-card {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 15px;
                }
                .insight-card h4 {
                    margin-top: 0;
                    color: #495057;
                    border-bottom: 2px solid #dee2e6;
                    padding-bottom: 8px;
                    margin-bottom: 12px;
                }
                .insight-list {
                    list-style-type: none;
                    padding: 0;
                    margin: 0;
                }
                .insight-list li {
                    margin-bottom: 8px;
                    padding-left: 20px;
                    position: relative;
                }
                .insight-list li:before {
                    content: "•";
                    position: absolute;
                    left: 0;
                    color: #007bff;
                }
                @media (max-width: 1200px) {
                    .json-comparison {
                        grid-template-columns: 1fr;
                    }
                    .json-column {
                        min-width: 100%;
                    }
                }
                .detailed-insights {
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
                    white-space: pre-wrap;
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    border: 1px solid #dee2e6;
                    line-height: 1.5;
                    overflow-x: auto;
                    margin: 20px 0;
                }
                .insights-section {
                    margin: 20px 0;
                }
                .insights-section h2 {
                    font-family: Arial, sans-serif;
                    color: #333;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                    margin-bottom: 15px;
                }
                .insights-content {
                    font-family: Arial, sans-serif;
                    white-space: pre-wrap;
                    line-height: 1.5;
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    border: 1px solid #dee2e6;
                    overflow-x: auto;
                }
                .metrics-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin: 20px 0;
                }
                .metrics-column {
                    background: #fff;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 20px;
                }
                .metrics-column h3 {
                    color: #007bff;
                    margin-top: 0;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #eee;
                }
                @media (max-width: 768px) {
                    .metrics-grid {
                        grid-template-columns: 1fr;
                    }
                }
                /* JSON Tree View Styles */
                .json-tree {
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                    line-height: 1.5;
                    margin: 10px 0;
                }
                .json-tree .collapsible {
                    cursor: pointer;
                    user-select: none;
                }
                .json-tree .collapsible::before {
                    content: '▶';
                    display: inline-block;
                    margin-right: 5px;
                    font-size: 10px;
                    transition: transform 0.2s;
                }
                .json-tree .expanded::before {
                    transform: rotate(90deg);
                }
                .json-tree .json-key {
                    color: #881391;
                    font-weight: bold;
                }
                .json-tree .json-string {
                    color: #268bd2;
                }
                .json-tree .json-number {
                    color: #b58900;
                }
                .json-tree .json-boolean {
                    color: #b58900;
                }
                .json-tree .json-null {
                    color: #808080;
                }
                .json-tree .bracket {
                    color: #333;
                }
                .json-tree .hidden {
                    display: none;
                }
                .json-tree .indent {
                    margin-left: 20px;
                }
                .json-tree .preview {
                    color: #666;
                    font-style: italic;
                }
                .json-container {
                    background: #fff;
                    border: 1px solid #dee2e6;
                    border-radius: 0 0 4px 4px;
                    padding: 15px;
                    height: 400px; /* Increased height for better visibility */
                    min-height: 400px; /* Ensure minimum height */
                    max-height: 400px; /* Ensure maximum height */
                    overflow: auto; /* Always show scrollbar when needed */
                    position: relative;
                }
                .json-tree {
                    height: 100%;
                    overflow: auto;
                    padding-right: 10px;
                }
                .json-comparison {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    max-width: 100%;
                    overflow: hidden;
                }
                /* Ensure long content wraps and scrolls */
                .json-tree .json-string,
                .json-tree .json-key,
                .json-tree .preview {
                    word-break: break-all;
                    white-space: pre-wrap;
                }
                /* Make indent consistent */
                .json-tree .indent {
                    margin-left: 20px;
                    padding-left: 10px;
                    border-left: 1px dotted #ddd;
                }
                /* Custom scrollbar styling */
                .json-tree::-webkit-scrollbar {
                    width: 8px;
                    height: 8px;
                }
                .json-tree::-webkit-scrollbar-track {
                    background: #f1f1f1;
                    border-radius: 4px;
                }
                .json-tree::-webkit-scrollbar-thumb {
                    background: #888;
                    border-radius: 4px;
                }
                .json-tree::-webkit-scrollbar-thumb:hover {
                    background: #555;
                }
                /* Ensure content doesn't overflow horizontally */
                @media screen and (max-width: 1200px) {
                    .json-comparison {
                        grid-template-columns: 1fr;
                    }
                }
                .config-grid {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 15px;
                    margin-top: 15px;
                }
                .config-item {
                    background: #fff;
                    padding: 15px;
                    border-radius: 4px;
                    border: 1px solid #dee2e6;
                }
                .config-item h3 {
                    margin: 0 0 10px 0;
                    color: #007bff;
                    font-size: 1.1em;
                }
                .footer {
                    background: #333;
                    color: #fff;
                    padding: 20px;
                    margin-top: 40px;
                    text-align: center;
                }
                .footer p {
                    margin: 5px 0;
                    font-size: 0.9em;
                }
                @media (max-width: 768px) {
                    .config-grid {
                        grid-template-columns: 1fr;
                    }
                }
                .dataset-header {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-bottom: none;
                    border-radius: 4px 4px 0 0;
                    padding: 12px 15px;
                    position: sticky;
                    top: 0;
                    z-index: 1;
                }
                .dataset-header h3 {
                    font-family: Arial, sans-serif;
                    font-size: 16px;
                    font-weight: bold;
                    color: #333;
                    margin: 0;
                }
                .dataset-header .file-info {
                    font-size: 12px;
                    color: #666;
                    margin-top: 4px;
                    font-family: monospace;
                }
            </style>
            <script>
                function toggleJson(id) {
                    const element = document.getElementById(id);
                    if (element.style.display === 'none') {
                        element.style.display = 'block';
                    } else {
                        element.style.display = 'none';
                    }
                }

                function formatJSON(obj, level = 0) {
                    const indent = '  '.repeat(level);
                    
                    if (obj === null) return '<span class="json-null">null</span>';
                    if (typeof obj === 'string') return `<span class="json-string">"${obj}"</span>`;
                    if (typeof obj === 'number') return `<span class="json-number">${obj}</span>`;
                    if (typeof obj === 'boolean') return `<span class="json-boolean">${obj}</span>`;
                    
                    if (Array.isArray(obj)) {
                        if (obj.length === 0) return '[]';
                        
                        const preview = obj.length > 3 
                            ? `Array(${obj.length})` 
                            : obj.slice(0, 3).map(item => {
                                if (typeof item === 'object' && item !== null) return '{ ... }';
                                return JSON.stringify(item);
                              }).join(', ');
                        
                        const id = 'array_' + Math.random().toString(36).substr(2, 9);
                        return `
                            <div class="collapsible" onclick="toggleNode(this, '${id}')">
                                <span class="bracket">[</span><span class="preview">${preview}</span><span class="bracket">]</span>
                            </div>
                            <div id="${id}" class="hidden indent">
                                ${obj.map((item, index) => `${formatJSON(item, level + 1)}${index < obj.length - 1 ? ',' : ''}`).join('<br>')}
                            </div>
                        `;
                    }
                    
                    if (typeof obj === 'object') {
                        const keys = Object.keys(obj);
                        if (keys.length === 0) return '{}';
                        
                        const preview = keys.length > 3 
                            ? `Object {${keys.length} properties}` 
                            : `{${keys.slice(0, 3).map(k => ` ${k}: ...`).join(',')} }`;
                        
                        const id = 'obj_' + Math.random().toString(36).substr(2, 9);
                        return `
                            <div class="collapsible" onclick="toggleNode(this, '${id}')">
                                <span class="bracket">{</span><span class="preview">${preview}</span><span class="bracket">}</span>
                            </div>
                            <div id="${id}" class="hidden indent">
                                ${Object.entries(obj).map(([key, value], index) => `
                                    <span class="json-key">"${key}"</span>: ${formatJSON(value, level + 1)}${index < keys.length - 1 ? ',' : ''}
                                `).join('<br>')}
                            </div>
                        `;
                    }
                    
                    return String(obj);
                }

                function toggleNode(element, id) {
                    element.classList.toggle('expanded');
                    const content = document.getElementById(id);
                    content.classList.toggle('hidden');
                    
                    // Find the closest json-container and adjust its height
                    const container = element.closest('.json-container');
                    if (container) {
                        if (content.classList.contains('hidden')) {
                            container.style.height = '50px'; // Collapsed height
                        } else {
                            container.style.height = Math.min(content.scrollHeight + 30, 200) + 'px'; // Expanded height
                        }
                    }
                }

                window.onload = function() {
                    // Format baseline data
                    const baselineData = JSON.parse(document.getElementById('baseline-data').textContent);
                    document.getElementById('baseline-json').innerHTML = formatJSON(baselineData);
                    
                    // Format target data
                    const targetData = JSON.parse(document.getElementById('target-data').textContent);
                    document.getElementById('target-json').innerHTML = formatJSON(targetData);
                    
                    // Set initial collapsed state
                    document.querySelectorAll('.json-container').forEach(container => {
                        container.style.height = '50px';
                    });
                }
            </script>
        </head>
        <body>
            <header class="header">
                <div class="header-content">
                    <img 
                        src="https://katalon.com/hubfs/katalon_logo%20(1).svg" 
                        alt="Katalon Logo" 
                        class="logo"
                    >
                    <h1 class="header-title">StudioAssist Comparison Report - {{ feature }}</h1>
                </div>
            </header>
            <div class="container">
                <p class="timestamp">Generated on: {{ timestamp }}</p>
                
                <div class="summary-box">
                    <h2>Test Information</h2>
                    <div class="config-grid">
                        <div class="config-item">
                            <h3>Feature Details</h3>
                            <div class="metric">
                                <span class="metric-label">Feature:</span>
                                <span>{{ feature }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Test Mode:</span>
                                <span>{{ test_mode }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Katalon Version:</span>
                                <span>{{ katalon_version }}</span>
                            </div>
                        </div>
                        <div class="config-item">
                            <h3>User Details</h3>
                            <div class="metric">
                                <span class="metric-label">User ID:</span>
                                <span>{{ report_data.user_info.user_id }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">User ID (Numeric):</span>
                                <span>{{ report_data.user_info.user_id_numeric }}</span>
                            </div>
                        </div>
                        <div class="config-item">
                            <h3>Organization Details</h3>
                            <div class="metric">
                                <span class="metric-label">Account ID:</span>
                                <span>{{ report_data.user_info.account_id }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Organization ID:</span>
                                <span>{{ report_data.user_info.org_id }}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="summary-box">
                    <h2>Test Configuration</h2>
                    <div class="config-grid">
                        <div class="config-item">
                            <h3>Baseline (LL1)</h3>
                            <div class="metric">
                                <span class="metric-label">Type:</span>
                                <span>{{ llm_configs.ll1.type }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Model:</span>
                                <span>{{ llm_configs.ll1.model }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Description:</span>
                                <span>{{ llm_configs.ll1.description }}</span>
                            </div>
                        </div>
                        <div class="config-item">
                            <h3>Target (LL2)</h3>
                            <div class="metric">
                                <span class="metric-label">Type:</span>
                                <span>{{ llm_configs.ll2.type }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Model:</span>
                                <span>{{ llm_configs.ll2.model }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Description:</span>
                                <span>{{ llm_configs.ll2.description }}</span>
                            </div>
                        </div>
                        <div class="config-item">
                            <h3>Evaluation (LL3)</h3>
                            <div class="metric">
                                <span class="metric-label">Provider:</span>
                                <span>{{ llm_configs.llm3.provider }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Model:</span>
                                <span>{{ llm_configs.llm3.model }}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Type:</span>
                                <span>{{ llm_configs.llm3.type }}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="insights-section">
                    <h2>📑 Dataset Summary</h2>
                    <div class="insights-content">{{ report_data.dataset_summary }}</div>
                </div>

                <div class="insights-section">
                    <h2>📊 Detailed Scores</h2>
                    <div class="metrics-grid">
                        <div class="metrics-column">
                            <h3>🎯 Consistency Metrics</h3>
                            <div class="insights-content">{{ report_data.detailed_scores_consistency }}</div>
                        </div>
                        <div class="metrics-column">
                            <h3>✅ Accuracy Metrics</h3>
                            <div class="insights-content">{{ report_data.detailed_scores_accuracy }}</div>
                        </div>
                    </div>
                </div>

                <div class="insights-section">
                    <h2>⚡ Performance Analysis</h2>
                    <div class="insights-content">{{ report_data.performance_analysis }}</div>
                </div>

                <div class="insights-section">
                    <h2>🔬 Detailed Analysis</h2>
                    <div class="insights-content">{{ report_data.detailed_analysis }}</div>
                </div>

                <div class="insights-section">
                    <h2>✨ Improvements</h2>
                    <div class="insights-content">{{ report_data.improvements }}</div>
                </div>

                <div class="insights-section">
                    <h2>⚠️ Regressions</h2>
                    <div class="insights-content">{{ report_data.regressions }}</div>
                </div>

                <div class="insights-section">
                    <h2>⚠️ Concerns</h2>
                    <div class="insights-content">{{ report_data.concerns }}</div>
                </div>

                <div class="insights-section">
                    <h2>💡 Recommendations</h2>
                    <div class="insights-content">{{ report_data.recommendations }}</div>
                </div>

                <div class="insights-section">
                    <h2>🎯 Final Assessment</h2>
                    <div class="insights-content">{{ report_data.final_assessment }}</div>
                </div>

                <div class="insights-section">
                    <h2>📝 Detailed Explanation</h2>
                    <div class="insights-content">{{ report_data.detailed_explanation }}</div>
                </div>

                <div class="summary-box">
                    <h2>Dataset Comparison</h2>
                    <div class="json-comparison">
                        <div class="dataset-section">
                            <div class="dataset-header">
                                <h3>Baseline Dataset</h3>
                            </div>
                            <div class="json-container">
                                <script type="application/json" id="baseline-data">{{ baseline_json | safe }}</script>
                                <div id="baseline-json" class="json-tree"></div>
                            </div>
                        </div>
                        <div class="dataset-section">
                            <div class="dataset-header">
                                <h3>Target Dataset</h3>
                            </div>
                            <div class="json-container">
                                <script type="application/json" id="target-data">{{ target_json | safe }}</script>
                                <div id="target-json" class="json-tree"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <footer class="footer">
                <p>Generated by Katalon StudioAssist</p>
                <p>{{ timestamp }}</p>
                <p>© {{ current_year }} Katalon LLC. All rights reserved.</p>
            </footer>
        </body>
        </html>
        ''')
        
        html_content = template.render(**template_data)
        
        # Create reports directory if it doesn't exist
        reports_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate report filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"comparison_report_{feature}_{timestamp}.html"
        report_path = os.path.join(reports_dir, report_filename)
        
        # Write report to file
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content.encode('utf-8').decode('utf-8'))
            
        return report_path 