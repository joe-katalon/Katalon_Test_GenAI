#!/usr/bin/env python3
"""Generate reports data for the reports dashboard."""

import os
import json
import glob
from datetime import datetime
from bs4 import BeautifulSoup

def extract_metrics_from_report(html_file):
    """Extract metrics from an HTML report file."""
    with open(html_file, 'r') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
        
        # Extract metrics from the report
        metrics = {
            'consistency': 0.0,
            'accuracy': 0.0,
            'overall': 0.0
        }
        
        try:
            # Find metrics columns
            metrics_columns = soup.select('.metrics-grid .metrics-column')
            if not metrics_columns:
                print(f"Warning: No metrics columns found in {html_file}")
                # Try alternative selectors
                metrics_columns = soup.select('.detailed-scores .metrics-column')
                if not metrics_columns:
                    print(f"Warning: No metrics found with alternative selector in {html_file}")
                    return metrics
            
            found_consistency = False
            found_accuracy = False
            
            for column in metrics_columns:
                header = column.select_one('h3')
                if not header:
                    print(f"Warning: Found column but no header in {html_file}")
                    continue
                
                content = column.select_one('.insights-content')
                if not content:
                    print(f"Warning: Found header '{header.text}' but no content in {html_file}")
                    continue
                
                # Extract all numbers from the content
                scores = []
                content_text = content.text.strip()
                print(f"Debug: Processing content for {header.text}:")
                print(content_text)
                
                for line in content_text.split('\n'):
                    # Extract number from strings like "🟢 Output Stability: 0.85"
                    try:
                        if ':' in line:
                            score_text = line.split(':')[-1].strip()
                            score = float(score_text)
                            scores.append(score)
                            print(f"Debug: Extracted score {score} from line: {line}")
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Could not extract score from line '{line}': {e}")
                        continue
                
                # Calculate average if we found any scores
                if scores:
                    if '🎯 Consistency Metrics' in header.text or 'Consistency' in header.text:
                        metrics['consistency'] = sum(scores) / len(scores)
                        found_consistency = True
                        print(f"Debug: Found consistency metrics, average: {metrics['consistency']}")
                    elif '✅ Accuracy Metrics' in header.text or 'Accuracy' in header.text:
                        metrics['accuracy'] = sum(scores) / len(scores)
                        found_accuracy = True
                        print(f"Debug: Found accuracy metrics, average: {metrics['accuracy']}")
                else:
                    print(f"Warning: No scores found in content for {header.text}")
            
            # Calculate overall score if we have both metrics
            if found_consistency and found_accuracy:
                metrics['overall'] = (metrics['consistency'] + metrics['accuracy']) / 2
                print(f"Debug: Calculated overall score: {metrics['overall']}")
            else:
                missing = []
                if not found_consistency:
                    missing.append("consistency")
                if not found_accuracy:
                    missing.append("accuracy")
                print(f"Warning: Missing metrics in {html_file}: {', '.join(missing)}")
            
        except Exception as e:
            print(f"Warning: Error processing {html_file}: {str(e)}")
        
        return metrics

def parse_report_filename(filename):
    """Parse feature and date from report filename."""
    try:
        # Remove .html extension
        base_name = filename.replace('.html', '')
        parts = base_name.split('_')
        
        # Expected format: comparison_report_<feature>_<YYYYMMDD>_<HHMMSS>.html
        if len(parts) >= 4:
            feature = parts[2]
            # Try to find a date part (8 digits for date)
            date_part = next((p for p in parts[3:] if p.isdigit() and len(p) == 8), None)
            time_part = next((p for p in parts[4:] if p.isdigit() and len(p) == 6), None)
            
            if date_part:
                if time_part:
                    # If we have both date and time, format as YYYY-MM-DD HH:MM
                    date = datetime.strptime(f"{date_part}_{time_part}", '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M')
                else:
                    # If we only have date, try to find time in the next part
                    time_part = next((p for p in parts[4:] if p.isdigit() and len(p) >= 4), None)
                    if time_part:
                        # Handle both HHMM and HHMMSS formats
                        time_format = '%H%M%S' if len(time_part) == 6 else '%H%M'
                        date = datetime.strptime(f"{date_part}_{time_part}", f'%Y%m%d_{time_format}').strftime('%Y-%m-%d %H:%M')
                    else:
                        # If no time found, use file's modification time
                        file_mtime = os.path.getmtime(filename)
                        date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')
            else:
                # If no valid date found, use file's modification time
                file_mtime = os.path.getmtime(filename)
                date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')
                print(f"Warning: No valid date found in {filename}, using file modification time")
            
            return feature, date
        else:
            # Default values if filename doesn't match expected format
            file_mtime = os.path.getmtime(filename)
            return "unknown", datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')
            
    except Exception as e:
        print(f"Error parsing filename {filename}: {e}")
        file_mtime = os.path.getmtime(filename)
        return "unknown", datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')

def generate_reports_data():
    """Generate reports_data.json from HTML reports."""
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
    reports_data = []
    
    # Create reports directory if it doesn't exist
    os.makedirs(reports_dir, exist_ok=True)
    
    # Find all comparison report files
    report_files = glob.glob(os.path.join(reports_dir, 'comparison_report_*.html'))
    
    # If no reports found, create a sample report
    if not report_files:
        print("No reports found, creating sample data")
        reports_data = [{
            'feature': 'sample',
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'url': '#',
            'models': {
                'll1': {
                    'type': 'gpt-3.5-turbo',
                    'model': 'baseline',
                    'description': 'Baseline Model'
                },
                'll2': {
                    'type': 'gpt-4',
                    'model': 'target',
                    'description': 'Target Model'
                }
            },
            'metrics': {
                'consistency': 0.85,  # Average of Output Stability, Behavior Consistency, Style Consistency
                'accuracy': 0.83,     # Average of Functional Correctness, Code Quality, Test Coverage
                'overall': 0.84       # Average of consistency and accuracy
            }
        }]
    else:
        for report_file in report_files:
            filename = os.path.basename(report_file)
            feature, date = parse_report_filename(filename)
            
            # Read the HTML file
            with open(report_file, 'r') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            # Extract LLM configurations
            models = {
                'll1': {'type': 'unknown', 'model': 'unknown', 'description': 'Baseline Model'},
                'll2': {'type': 'unknown', 'model': 'unknown', 'description': 'Target Model'}
            }
            
            try:
                # Find the config items
                config_items = soup.select('.config-item')
                for item in config_items:
                    title = item.select_one('h3')
                    if not title:
                        continue
                        
                    if 'Baseline (LL1)' in title.text:
                        metrics = item.select('.metric')
                        for metric in metrics:
                            label = metric.select_one('.metric-label')
                            value = metric.select_one('span:last-child')
                            if label and value:
                                label_text = label.text.strip().lower().replace(':', '')
                                if label_text in ['type', 'model', 'description']:
                                    models['ll1'][label_text] = value.text.strip()
                                    
                    elif 'Target (LL2)' in title.text:
                        metrics = item.select('.metric')
                        for metric in metrics:
                            label = metric.select_one('.metric-label')
                            value = metric.select_one('span:last-child')
                            if label and value:
                                label_text = label.text.strip().lower().replace(':', '')
                                if label_text in ['type', 'model', 'description']:
                                    models['ll2'][label_text] = value.text.strip()
            
            except Exception as e:
                print(f"Warning: Error extracting model configurations from {filename}: {e}")
            
            # Extract metrics from the comparison table
            metrics = {
                'completeness': 0.0,
                'accuracy': 0.0,
                'clarity': 0.0,
                'context': 0.0,
                'overall': 0.0
            }
            
            try:
                # Find all rows in the comparison table
                rows = soup.select('.comparison-table tbody tr')
                valid_metrics = 0
                
                for row in rows:
                    # Get criterion name from first column
                    criterion_cell = row.select_one('td:first-child .tooltip-trigger')
                    if not criterion_cell:
                        continue
                        
                    criterion = criterion_cell.text.strip().lower()
                    
                    # Get LL2 score from third column (index 2)
                    score_cell = row.select_one('td:nth-child(3)')
                    if not score_cell:
                        continue
                        
                    try:
                        score = float(score_cell.text.strip())
                        if criterion in metrics:
                            metrics[criterion] = score
                            valid_metrics += 1
                    except (ValueError, TypeError):
                        print(f"Warning: Invalid score for {criterion} in {filename}")
                
                # Calculate overall score
                if valid_metrics > 0:
                    metrics['overall'] = sum(v for v in metrics.values() if isinstance(v, (int, float))) / valid_metrics
                    
            except Exception as e:
                print(f"Warning: Error extracting metrics from {filename}: {e}")
            
            # Create report entry
            report_entry = {
                'feature': feature,
                'date': date,
                'url': f'reports/{filename}',
                'models': models,
                'metrics': metrics
            }
            
            reports_data.append(report_entry)
    
    # Sort reports by date (newest first)
    reports_data.sort(key=lambda x: x['date'], reverse=True)
    
    # Save to JSON file
    output_file = os.path.join(reports_dir, 'reports_data.json')
    with open(output_file, 'w') as f:
        json.dump(reports_data, f, indent=2)
    
    print(f"Generated reports data: {output_file}")
    print(f"Found {len(reports_data)} reports")

if __name__ == '__main__':
    generate_reports_data() 