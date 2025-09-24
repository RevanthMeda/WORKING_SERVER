#!/usr/bin/env python3
"""
Code Quality Automation Script

This script provides automated code quality management including:
- Continuous quality monitoring
- Automated reporting
- Quality gate enforcement
- Technical debt tracking
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class QualityAutomation:
    """Automated code quality management system."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.config_file = self.project_root / "quality_config.yaml"
        self.reports_dir = self.project_root / "quality_reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load quality automation configuration."""
        default_config = {
            "quality_gates": {
                "min_coverage": 80.0,
                "min_pylint_score": 8.0,
                "max_complexity": 10,
                "max_security_issues": 0,
                "max_type_errors": 5,
                "min_overall_score": 70.0
            },
            "monitoring": {
                "enabled": True,
                "interval_hours": 24,
                "alert_threshold": 60.0
            },
            "reporting": {
                "generate_dashboard": True,
                "send_notifications": False,
                "notification_email": "",
                "slack_webhook": ""
            },
            "automation": {
                "auto_fix_formatting": True,
                "auto_create_issues": False,
                "auto_update_docs": True
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    user_config = yaml.safe_load(f)
                    # Merge with defaults
                    for section, values in user_config.items():
                        if section in default_config:
                            default_config[section].update(values)
                        else:
                            default_config[section] = values
            except (yaml.YAMLError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
        else:
            # Create default config file
            with open(self.config_file, "w") as f:
                yaml.dump(default_config, f, default_flow_style=False)
            print(f"Created default configuration: {self.config_file}")
        
        return default_config
    
    def run_quality_checks(self) -> Dict:
        """Run comprehensive quality checks."""
        print("Running comprehensive quality checks...")
        
        # Run quality metrics collection
        try:
            result = subprocess.run([
                sys.executable, "scripts/quality_metrics.py"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=1800)
            
            if result.returncode != 0:
                print(f"Quality metrics collection failed: {result.stderr}")
                return {"error": "Quality metrics collection failed"}
        
        except subprocess.TimeoutExpired:
            print("Quality metrics collection timed out")
            return {"error": "Quality metrics collection timed out"}
        
        # Load latest quality report
        latest_report_file = self.reports_dir / "quality_metrics_latest.json"
        if latest_report_file.exists():
            with open(latest_report_file) as f:
                return json.load(f)
        
        return {"error": "No quality report found"}
    
    def run_debt_analysis(self) -> Dict:
        """Run technical debt analysis."""
        print("Running technical debt analysis...")
        
        try:
            result = subprocess.run([
                sys.executable, "scripts/technical_debt_tracker.py"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                print(f"Technical debt analysis failed: {result.stderr}")
                return {"error": "Technical debt analysis failed"}
        
        except subprocess.TimeoutExpired:
            print("Technical debt analysis timed out")
            return {"error": "Technical debt analysis timed out"}
        
        # Load debt report
        debt_report_file = self.reports_dir / "technical_debt_report.json"
        if debt_report_file.exists():
            with open(debt_report_file) as f:
                return json.load(f)
        
        return {"error": "No debt report found"}
    
    def check_quality_gates(self, quality_report: Dict) -> Tuple[bool, List[str]]:
        """Check if quality gates are met."""
        gates = self.config["quality_gates"]
        failures = []
        
        metrics = quality_report.get("metrics", {})
        quality_score = quality_report.get("quality_score", {})
        
        # Check coverage
        coverage = metrics.get("coverage", {}).get("total_coverage", 0)
        if coverage < gates["min_coverage"]:
            failures.append(f"Coverage {coverage:.1f}% below minimum {gates['min_coverage']}%")
        
        # Check pylint score
        pylint_score = metrics.get("linting", {}).get("pylint", {}).get("score", 0)
        if pylint_score < gates["min_pylint_score"]:
            failures.append(f"Pylint score {pylint_score:.1f} below minimum {gates['min_pylint_score']}")
        
        # Check complexity
        avg_complexity = metrics.get("complexity", {}).get("cyclomatic_complexity", {}).get("average_complexity", 0)
        if avg_complexity > gates["max_complexity"]:
            failures.append(f"Average complexity {avg_complexity:.1f} above maximum {gates['max_complexity']}")
        
        # Check security issues
        security_issues = metrics.get("security", {}).get("total_issues", 0)
        if security_issues > gates["max_security_issues"]:
            failures.append(f"Security issues {security_issues} above maximum {gates['max_security_issues']}")
        
        # Check type errors
        type_errors = metrics.get("type_checking", {}).get("total_errors", 0)
        if type_errors > gates["max_type_errors"]:
            failures.append(f"Type errors {type_errors} above maximum {gates['max_type_errors']}")
        
        # Check overall score
        overall_score = quality_score.get("overall_score", 0)
        if overall_score < gates["min_overall_score"]:
            failures.append(f"Overall score {overall_score:.1f} below minimum {gates['min_overall_score']}")
        
        return len(failures) == 0, failures
    
    def auto_fix_issues(self) -> None:
        """Automatically fix issues where possible."""
        if not self.config["automation"]["auto_fix_formatting"]:
            return
        
        print("Auto-fixing formatting issues...")
        
        try:
            # Run Black
            subprocess.run([
                "black", ".", "--line-length", "127"
            ], cwd=self.project_root, timeout=300)
            
            # Run isort
            subprocess.run([
                "isort", ".", "--profile", "black", "--line-length", "127"
            ], cwd=self.project_root, timeout=300)
            
            print("Formatting fixes applied")
        
        except subprocess.TimeoutExpired:
            print("Auto-fix timed out")
        except Exception as e:
            print(f"Auto-fix failed: {e}")
    
    def generate_dashboard(self) -> Optional[str]:
        """Generate quality dashboard."""
        if not self.config["reporting"]["generate_dashboard"]:
            return None
        
        print("Generating quality dashboard...")
        
        try:
            result = subprocess.run([
                sys.executable, "scripts/debt_dashboard.py"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                dashboard_path = self.project_root / "dashboard" / "index.html"
                if dashboard_path.exists():
                    return str(dashboard_path)
        
        except subprocess.TimeoutExpired:
            print("Dashboard generation timed out")
        except Exception as e:
            print(f"Dashboard generation failed: {e}")
        
        return None
    
    def send_notifications(self, quality_report: Dict, gate_failures: List[str]) -> None:
        """Send quality notifications."""
        if not self.config["reporting"]["send_notifications"]:
            return
        
        # Prepare notification content
        quality_score = quality_report.get("quality_score", {}).get("overall_score", 0)
        grade = quality_report.get("quality_score", {}).get("grade", "N/A")
        
        subject = f"Code Quality Report - Score: {quality_score:.1f} (Grade: {grade})"
        
        message = f"""
Code Quality Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Overall Quality Score: {quality_score:.1f}/100 (Grade: {grade})

Quality Gate Status: {'✅ PASSED' if not gate_failures else '❌ FAILED'}
"""
        
        if gate_failures:
            message += "\nQuality Gate Failures:\n"
            for failure in gate_failures:
                message += f"  • {failure}\n"
        
        # Add metrics summary
        metrics = quality_report.get("metrics", {})
        message += f"""
Metrics Summary:
  • Test Coverage: {metrics.get('coverage', {}).get('total_coverage', 0):.1f}%
  • Pylint Score: {metrics.get('linting', {}).get('pylint', {}).get('score', 0):.1f}/10
  • Security Issues: {metrics.get('security', {}).get('total_issues', 0)}
  • Type Errors: {metrics.get('type_checking', {}).get('total_errors', 0)}
"""
        
        # Send email notification
        email = self.config["reporting"]["notification_email"]
        if email:
            self.send_email_notification(email, subject, message)
        
        # Send Slack notification
        webhook = self.config["reporting"]["slack_webhook"]
        if webhook:
            self.send_slack_notification(webhook, subject, message)
    
    def send_email_notification(self, email: str, subject: str, message: str) -> None:
        """Send email notification."""
        # This is a placeholder - implement actual email sending
        print(f"Email notification would be sent to: {email}")
        print(f"Subject: {subject}")
        print(f"Message: {message[:100]}...")
    
    def send_slack_notification(self, webhook: str, subject: str, message: str) -> None:
        """Send Slack notification."""
        # This is a placeholder - implement actual Slack webhook
        print(f"Slack notification would be sent to: {webhook}")
        print(f"Subject: {subject}")
        print(f"Message: {message[:100]}...")
    
    def run_full_analysis(self) -> Dict:
        """Run full quality analysis and reporting."""
        print("Starting full quality analysis...")
        
        start_time = time.time()
        
        # Auto-fix issues first
        self.auto_fix_issues()
        
        # Run quality checks
        quality_report = self.run_quality_checks()
        if "error" in quality_report:
            return quality_report
        
        # Run debt analysis
        debt_report = self.run_debt_analysis()
        
        # Check quality gates
        gates_passed, gate_failures = self.check_quality_gates(quality_report)
        
        # Generate dashboard
        dashboard_path = self.generate_dashboard()
        
        # Send notifications
        self.send_notifications(quality_report, gate_failures)
        
        # Prepare summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": time.time() - start_time,
            "quality_score": quality_report.get("quality_score", {}),
            "quality_gates": {
                "passed": gates_passed,
                "failures": gate_failures
            },
            "dashboard_path": dashboard_path,
            "debt_summary": debt_report.get("summary", {}) if "error" not in debt_report else None
        }
        
        # Save summary
        with open(self.reports_dir / "automation_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        return summary
    
    def print_summary(self, summary: Dict) -> None:
        """Print analysis summary."""
        print("\n" + "="*60)
        print("QUALITY AUTOMATION SUMMARY")
        print("="*60)
        
        quality_score = summary.get("quality_score", {})
        print(f"Overall Quality Score: {quality_score.get('overall_score', 0):.1f}/100 (Grade: {quality_score.get('grade', 'N/A')})")
        
        gates = summary.get("quality_gates", {})
        status = "✅ PASSED" if gates.get("passed", False) else "❌ FAILED"
        print(f"Quality Gates: {status}")
        
        if not gates.get("passed", False):
            print("\nQuality Gate Failures:")
            for failure in gates.get("failures", []):
                print(f"  • {failure}")
        
        debt_summary = summary.get("debt_summary", {})
        if debt_summary:
            print(f"\nTechnical Debt: {debt_summary.get('total_debt_items', 0)} items")
            print(f"High Priority: {debt_summary.get('high_priority_items', 0)} items")
        
        dashboard_path = summary.get("dashboard_path")
        if dashboard_path:
            print(f"\nDashboard: file://{Path(dashboard_path).absolute()}")
        
        duration = summary.get("duration_seconds", 0)
        print(f"\nAnalysis completed in {duration:.1f} seconds")
        print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Code Quality Automation")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "check", "fix", "dashboard"],
        default="full",
        help="Automation mode"
    )
    
    args = parser.parse_args()
    
    automation = QualityAutomation(args.project_root)
    
    if args.mode == "fix":
        automation.auto_fix_issues()
    elif args.mode == "check":
        quality_report = automation.run_quality_checks()
        if "error" not in quality_report:
            gates_passed, failures = automation.check_quality_gates(quality_report)
            if not gates_passed:
                print("Quality gates failed:")
                for failure in failures:
                    print(f"  • {failure}")
                sys.exit(1)
    elif args.mode == "dashboard":
        dashboard_path = automation.generate_dashboard()
        if dashboard_path:
            print(f"Dashboard generated: file://{Path(dashboard_path).absolute()}")
    else:  # full
        summary = automation.run_full_analysis()
        automation.print_summary(summary)
        
        # Exit with error code if quality gates failed
        if not summary.get("quality_gates", {}).get("passed", False):
            sys.exit(1)


if __name__ == "__main__":
    main()