#!/usr/bin/env python3
"""
Technical Debt Dashboard Generator

This script generates an HTML dashboard for visualizing technical debt
and code quality metrics over time.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import seaborn as sns


class TechnicalDebtDashboard:
    """Generates technical debt dashboard and visualizations."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.reports_dir = self.project_root / "quality_reports"
        self.dashboard_dir = self.project_root / "dashboard"
        self.dashboard_dir.mkdir(exist_ok=True)
        
        # Set up plotting style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
    
    def load_historical_data(self) -> List[Dict]:
        """Load historical quality metrics data."""
        historical_data = []
        
        # Load all quality metrics files
        for report_file in self.reports_dir.glob("quality_metrics_*.json"):
            if "latest" in report_file.name:
                continue
                
            try:
                with open(report_file) as f:
                    data = json.load(f)
                    historical_data.append(data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load {report_file}: {e}")
        
        # Sort by timestamp
        historical_data.sort(key=lambda x: x.get("timestamp", ""))
        
        return historical_data
    
    def load_debt_data(self) -> Optional[Dict]:
        """Load latest technical debt data."""
        debt_file = self.reports_dir / "technical_debt_report.json"
        if debt_file.exists():
            try:
                with open(debt_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load debt data: {e}")
        return None
    
    def generate_quality_trend_chart(self, historical_data: List[Dict]) -> str:
        """Generate quality score trend chart."""
        if not historical_data:
            return ""
        
        dates = []
        scores = []
        
        for data in historical_data:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                score = data.get("quality_score", {}).get("overall_score", 0)
                dates.append(timestamp)
                scores.append(score)
            except (ValueError, KeyError):
                continue
        
        if not dates:
            return ""
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dates, scores, marker='o', linewidth=2, markersize=6)
        ax.set_title("Code Quality Score Trend", fontsize=16, fontweight='bold')
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Quality Score", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
        plt.xticks(rotation=45)
        
        # Add trend line
        if len(dates) > 1:
            z = np.polyfit(range(len(scores)), scores, 1)
            p = np.poly1d(z)
            ax.plot(dates, p(range(len(scores))), "--", alpha=0.7, color='red')
        
        plt.tight_layout()
        
        chart_path = self.dashboard_dir / "quality_trend.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path.name)
    
    def generate_debt_distribution_chart(self, debt_data: Dict) -> str:
        """Generate technical debt distribution chart."""
        if not debt_data or "summary" not in debt_data:
            return ""
        
        debt_by_type = debt_data["summary"].get("debt_by_type", {})
        if not debt_by_type:
            return ""
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Pie chart for debt types
        types = list(debt_by_type.keys())
        counts = list(debt_by_type.values())
        
        ax1.pie(counts, labels=types, autopct='%1.1f%%', startangle=90)
        ax1.set_title("Technical Debt by Type", fontsize=14, fontweight='bold')
        
        # Bar chart for debt severity
        debt_by_severity = debt_data["summary"].get("debt_by_severity", {})
        if debt_by_severity:
            severities = list(debt_by_severity.keys())
            severity_counts = list(debt_by_severity.values())
            
            colors = {'high': 'red', 'medium': 'orange', 'low': 'green'}
            bar_colors = [colors.get(sev, 'blue') for sev in severities]
            
            ax2.bar(severities, severity_counts, color=bar_colors, alpha=0.7)
            ax2.set_title("Technical Debt by Severity", fontsize=14, fontweight='bold')
            ax2.set_xlabel("Severity")
            ax2.set_ylabel("Count")
        
        plt.tight_layout()
        
        chart_path = self.dashboard_dir / "debt_distribution.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path.name)
    
    def generate_complexity_heatmap(self, historical_data: List[Dict]) -> str:
        """Generate complexity heatmap."""
        if not historical_data:
            return ""
        
        # Get latest complexity data
        latest_data = historical_data[-1]
        complexity_data = latest_data.get("metrics", {}).get("complexity", {}).get("cyclomatic_complexity", {}).get("details", {})
        
        if not complexity_data:
            return ""
        
        # Prepare data for heatmap
        files = []
        complexities = []
        
        for file_path, functions in complexity_data.items():
            for func in functions:
                files.append(f"{Path(file_path).name}::{func.get('name', 'unknown')}")
                complexities.append(func.get('complexity', 0))
        
        if not files:
            return ""
        
        # Sort by complexity and take top 20
        sorted_data = sorted(zip(files, complexities), key=lambda x: x[1], reverse=True)[:20]
        files, complexities = zip(*sorted_data)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create heatmap data
        heatmap_data = [[comp] for comp in complexities]
        
        im = ax.imshow(heatmap_data, cmap='RdYlGn_r', aspect='auto')
        
        # Set ticks and labels
        ax.set_yticks(range(len(files)))
        ax.set_yticklabels(files, fontsize=8)
        ax.set_xticks([0])
        ax.set_xticklabels(['Complexity'])
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Cyclomatic Complexity', rotation=270, labelpad=15)
        
        # Add text annotations
        for i, comp in enumerate(complexities):
            ax.text(0, i, str(comp), ha='center', va='center', fontweight='bold')
        
        ax.set_title("Top 20 Most Complex Functions", fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        
        chart_path = self.dashboard_dir / "complexity_heatmap.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path.name)
    
    def generate_coverage_chart(self, historical_data: List[Dict]) -> str:
        """Generate test coverage trend chart."""
        if not historical_data:
            return ""
        
        dates = []
        coverages = []
        
        for data in historical_data:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                coverage = data.get("metrics", {}).get("coverage", {}).get("total_coverage", 0)
                dates.append(timestamp)
                coverages.append(coverage)
            except (ValueError, KeyError):
                continue
        
        if not dates:
            return ""
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dates, coverages, marker='s', linewidth=2, markersize=6, color='green')
        ax.set_title("Test Coverage Trend", fontsize=16, fontweight='bold')
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Coverage %", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)
        
        # Add target line
        ax.axhline(y=80, color='red', linestyle='--', alpha=0.7, label='Target (80%)')
        ax.legend()
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        chart_path = self.dashboard_dir / "coverage_trend.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path.name)
    
    def generate_html_dashboard(self, historical_data: List[Dict], debt_data: Optional[Dict]) -> str:
        """Generate HTML dashboard."""
        # Generate charts
        quality_chart = self.generate_quality_trend_chart(historical_data)
        debt_chart = self.generate_debt_distribution_chart(debt_data) if debt_data else ""
        complexity_chart = self.generate_complexity_heatmap(historical_data)
        coverage_chart = self.generate_coverage_chart(historical_data)
        
        # Get latest metrics
        latest_metrics = historical_data[-1] if historical_data else {}
        quality_score = latest_metrics.get("quality_score", {})
        metrics = latest_metrics.get("metrics", {})
        
        # Generate HTML
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Technical Debt Dashboard</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #007acc;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            border-left: 4px solid #007acc;
            padding-left: 15px;
            margin-top: 30px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .metric-label {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .chart-container {{
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background-color: #fafafa;
            border-radius: 8px;
        }}
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .debt-summary {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .debt-item {{
            background-color: white;
            border-left: 4px solid #dc3545;
            padding: 15px;
            margin: 10px 0;
            border-radius: 0 5px 5px 0;
        }}
        .debt-item.medium {{
            border-left-color: #ffc107;
        }}
        .debt-item.low {{
            border-left-color: #28a745;
        }}
        .grade {{
            display: inline-block;
            padding: 10px 20px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 1.2em;
        }}
        .grade-A {{ background-color: #28a745; color: white; }}
        .grade-B {{ background-color: #17a2b8; color: white; }}
        .grade-C {{ background-color: #ffc107; color: black; }}
        .grade-D {{ background-color: #fd7e14; color: white; }}
        .grade-F {{ background-color: #dc3545; color: white; }}
        .timestamp {{
            text-align: center;
            color: #666;
            font-style: italic;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Technical Debt Dashboard</h1>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Overall Quality Score</div>
                <div class="metric-value">{quality_score.get('overall_score', 0):.1f}</div>
                <div class="grade grade-{quality_score.get('grade', 'F')}">{quality_score.get('grade', 'N/A')}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Test Coverage</div>
                <div class="metric-value">{metrics.get('coverage', {}).get('total_coverage', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Pylint Score</div>
                <div class="metric-value">{metrics.get('linting', {}).get('pylint', {}).get('score', 0):.1f}/10</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Security Issues</div>
                <div class="metric-value">{metrics.get('security', {}).get('total_issues', 0)}</div>
            </div>
        </div>
        
        <h2>📈 Quality Trends</h2>
        {f'<div class="chart-container"><img src="{quality_chart}" alt="Quality Trend Chart"></div>' if quality_chart else '<p>No quality trend data available.</p>'}
        
        <h2>📊 Test Coverage</h2>
        {f'<div class="chart-container"><img src="{coverage_chart}" alt="Coverage Trend Chart"></div>' if coverage_chart else '<p>No coverage trend data available.</p>'}
        
        <h2>🔥 Code Complexity</h2>
        {f'<div class="chart-container"><img src="{complexity_chart}" alt="Complexity Heatmap"></div>' if complexity_chart else '<p>No complexity data available.</p>'}
        """
        
        # Add technical debt section if data is available
        if debt_data:
            debt_summary = debt_data.get("summary", {})
            debt_items = debt_data.get("debt_items", [])[:10]  # Top 10 items
            
            html_content += f"""
        <h2>⚠️ Technical Debt</h2>
        {f'<div class="chart-container"><img src="{debt_chart}" alt="Debt Distribution Chart"></div>' if debt_chart else ''}
        
        <div class="debt-summary">
            <h3>Summary</h3>
            <p><strong>Total Debt Items:</strong> {debt_summary.get('total_debt_items', 0)}</p>
            <p><strong>High Priority Items:</strong> {debt_summary.get('high_priority_items', 0)}</p>
        </div>
        
        <h3>Top Priority Items</h3>
        """
            
            for item in debt_items:
                html_content += f"""
        <div class="debt-item {item.get('severity', 'medium')}">
            <strong>{item.get('debt_type', 'Unknown')}</strong> in {item.get('file_path', 'Unknown')}:{item.get('line_number', 0)}
            <br>
            <em>{item.get('description', 'No description')}</em>
            <br>
            <small>Priority: {item.get('priority', 0)} | Effort: {item.get('estimated_effort', 'Unknown')}</small>
        </div>
                """
        
        html_content += f"""
        <div class="timestamp">
            Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
        """
        
        # Save HTML dashboard
        dashboard_path = self.dashboard_dir / "index.html"
        with open(dashboard_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return str(dashboard_path)
    
    def generate_dashboard(self) -> str:
        """Generate complete technical debt dashboard."""
        print("Generating technical debt dashboard...")
        
        # Load data
        historical_data = self.load_historical_data()
        debt_data = self.load_debt_data()
        
        if not historical_data:
            print("Warning: No historical quality data found. Run quality metrics collection first.")
            return ""
        
        # Generate dashboard
        dashboard_path = self.generate_html_dashboard(historical_data, debt_data)
        
        print(f"Dashboard generated: {dashboard_path}")
        return dashboard_path


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Technical Debt Dashboard Generator")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )
    
    args = parser.parse_args()
    
    # Check if required packages are available
    try:
        import numpy as np
        global np
    except ImportError:
        print("Warning: numpy not available. Some charts may not work properly.")
        import sys
        sys.exit(1)
    
    dashboard = TechnicalDebtDashboard(args.project_root)
    dashboard_path = dashboard.generate_dashboard()
    
    if dashboard_path:
        print(f"\nDashboard available at: file://{Path(dashboard_path).absolute()}")


if __name__ == "__main__":
    main()