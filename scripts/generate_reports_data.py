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

def generate_reports_data():
    """Generate reports_data.json from HTML reports."""
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
    reports_data = []
    
    # Find all comparison report files
    report_files = glob.glob(os.path.join(reports_dir, 'comparison_report_*.html'))
    
    for report_file in report_files:
        filename = os.path.basename(report_file)
        
        # Extract feature and date from filename
        # Format: comparison_report_<feature>_<YYYYMMDD>_<HHMMSS>.html
        parts = filename.replace('.html', '').split('_')
        feature = parts[2]
        date_str = parts[3]
        
        # Convert date string to formatted date
        date = datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
        
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