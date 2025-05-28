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
            'stability': 0.0,
            'consistency': 0.0,
            'quality': 0.0,
            'performance': 0.0,
            'overall': 0.0
        }
        
        try:
            # Find metrics in the HTML
            metric_elements = soup.find_all(class_='metric-value')
            for element in metric_elements:
                metric_name = element.get('data-metric', '').lower()
                if metric_name in metrics:
                    metrics[metric_name] = float(element.text.strip())
            
            # Calculate overall score
            metrics['overall'] = sum(metrics.values()) / len(metrics)
            
        except Exception as e:
            print(f"Error extracting metrics from {html_file}: {e}")
        
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
            # Try to find a date part (8 digits)
            date_part = next((p for p in parts[3:] if p.isdigit() and len(p) == 8), None)
            
            if date_part:
                date = datetime.strptime(date_part, '%Y%m%d').strftime('%Y-%m-%d')
            else:
                # If no valid date found, use current date
                date = datetime.now().strftime('%Y-%m-%d')
                print(f"Warning: No valid date found in {filename}, using current date")
            
            return feature, date
        else:
            # Default values if filename doesn't match expected format
            return "unknown", datetime.now().strftime('%Y-%m-%d')
            
    except Exception as e:
        print(f"Error parsing filename {filename}: {e}")
        return "unknown", datetime.now().strftime('%Y-%m-%d')

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
            'date': datetime.now().strftime('%Y-%m-%d'),
            'url': '#',
            'metrics': {
                'stability': 0.85,
                'consistency': 0.92,
                'quality': 0.88,
                'performance': 0.90,
                'overall': 0.89
            }
        }]
    else:
        for report_file in report_files:
            filename = os.path.basename(report_file)
            feature, date = parse_report_filename(filename)
            
            # Extract metrics from report
            metrics = extract_metrics_from_report(report_file)
            
            # Create report entry
            report_entry = {
                'feature': feature,
                'date': date,
                'url': f'reports/{filename}',
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