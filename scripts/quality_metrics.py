#!/usr/bin/env python3
"""
Code Quality Metrics Collection and Reporting

This script collects various code quality metrics and generates comprehensive
reports for tracking code quality over time.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class QualityMetricsCollector:
    """Collects and analyzes code quality metrics."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.reports_dir = self.project_root / "quality_reports"
        self.reports_dir.mkdir(exist_ok=True)
        
    def collect_coverage_metrics(self) -> Dict:
        """Collect test coverage metrics."""
        try:
            # Run pytest with coverage
            result = subprocess.run([
                "python", "-m", "pytest", "tests/",
                "--cov=.", "--cov-report=json",
                "--cov-report=term-missing:skip-covered",
                "--quiet"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=300)
            
            # Read coverage report
            coverage_file = self.project_root / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                
                return {
                    "total_coverage": coverage_data["totals"]["percent_covered"],
                    "lines_covered": coverage_data["totals"]["covered_lines"],
                    "lines_missing": coverage_data["totals"]["missing_lines"],
                    "total_lines": coverage_data["totals"]["num_statements"],
                    "files": {
                        file_path: {
                            "coverage": file_data["summary"]["percent_covered"],
                            "lines_covered": file_data["summary"]["covered_lines"],
                            "lines_missing": file_data["summary"]["missing_lines"]
                        }
                        for file_path, file_data in coverage_data["files"].items()
                    }
                }
        except Exception as e:
            print(f"Warning: Could not collect coverage metrics: {e}")
        
        return {"total_coverage": 0, "error": "Could not collect coverage data"}
    
    def collect_complexity_metrics(self) -> Dict:
        """Collect code complexity metrics using radon."""
        metrics = {}
        
        try:
            # Cyclomatic complexity
            cc_result = subprocess.run([
                "radon", "cc", ".", "--json",
                "--exclude", "tests,migrations,venv,env"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=300)
            
            if cc_result.returncode == 0:
                cc_data = json.loads(cc_result.stdout)
                
                # Calculate aggregate metrics
                total_functions = 0
                complexity_sum = 0
                high_complexity_count = 0
                
                for file_path, functions in cc_data.items():
                    for func in functions:
                        total_functions += 1
                        complexity = func.get("complexity", 0)
                        complexity_sum += complexity
                        if complexity > 10:
                            high_complexity_count += 1
                
                metrics["cyclomatic_complexity"] = {
                    "average_complexity": complexity_sum / total_functions if total_functions > 0 else 0,
                    "total_functions": total_functions,
                    "high_complexity_functions": high_complexity_count,
                    "high_complexity_percentage": (high_complexity_count / total_functions * 100) if total_functions > 0 else 0,
                    "details": cc_data
                }
        
        except Exception as e:
            print(f"Warning: Could not collect complexity metrics: {e}")
            metrics["cyclomatic_complexity"] = {"error": str(e)}
        
        try:
            # Maintainability index
            mi_result = subprocess.run([
                "radon", "mi", ".", "--json",
                "--exclude", "tests,migrations,venv,env"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=300)
            
            if mi_result.returncode == 0:
                mi_data = json.loads(mi_result.stdout)
                
                # Calculate aggregate metrics
                mi_scores = []
                low_maintainability_count = 0
                
                for file_path, mi_info in mi_data.items():
                    mi_score = mi_info.get("mi", 0)
                    mi_scores.append(mi_score)
                    if mi_score < 20:
                        low_maintainability_count += 1
                
                metrics["maintainability_index"] = {
                    "average_mi": sum(mi_scores) / len(mi_scores) if mi_scores else 0,
                    "total_files": len(mi_scores),
                    "low_maintainability_files": low_maintainability_count,
                    "low_maintainability_percentage": (low_maintainability_count / len(mi_scores) * 100) if mi_scores else 0,
                    "details": mi_data
                }
        
        except Exception as e:
            print(f"Warning: Could not collect maintainability metrics: {e}")
            metrics["maintainability_index"] = {"error": str(e)}
        
        return metrics
    
    def collect_linting_metrics(self) -> Dict:
        """Collect linting metrics from flake8 and pylint."""
        metrics = {}
        
        # Flake8 metrics
        try:
            flake8_result = subprocess.run([
                "flake8", ".", "--format=json",
                "--output-file", str(self.reports_dir / "flake8_detailed.json")
            ], cwd=self.project_root, capture_output=True, text=True, timeout=300)
            
            # Read flake8 report
            flake8_file = self.reports_dir / "flake8_detailed.json"
            if flake8_file.exists():
                with open(flake8_file) as f:
                    try:
                        flake8_data = json.load(f)
                        
                        # Categorize issues
                        error_counts = {}
                        severity_counts = {"error": 0, "warning": 0, "info": 0}
                        
                        for issue in flake8_data:
                            code = issue.get("code", "unknown")
                            error_counts[code] = error_counts.get(code, 0) + 1
                            
                            # Categorize by severity (simplified)
                            if code.startswith("E"):
                                severity_counts["error"] += 1
                            elif code.startswith("W"):
                                severity_counts["warning"] += 1
                            else:
                                severity_counts["info"] += 1
                        
                        metrics["flake8"] = {
                            "total_issues": len(flake8_data),
                            "error_counts": error_counts,
                            "severity_counts": severity_counts
                        }
                    except json.JSONDecodeError:
                        metrics["flake8"] = {"total_issues": 0}
            else:
                metrics["flake8"] = {"total_issues": 0}
        
        except Exception as e:
            print(f"Warning: Could not collect flake8 metrics: {e}")
            metrics["flake8"] = {"error": str(e)}
        
        # Pylint metrics
        try:
            pylint_result = subprocess.run([
                "pylint", ".", "--output-format=json",
                "--reports=yes", "--score=yes"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=600)
            
            # Parse pylint output
            if pylint_result.stdout:
                try:
                    pylint_data = json.loads(pylint_result.stdout)
                    
                    # Categorize messages
                    message_counts = {}
                    category_counts = {"error": 0, "warning": 0, "refactor": 0, "convention": 0}
                    
                    for message in pylint_data:
                        msg_type = message.get("type", "unknown")
                        msg_id = message.get("message-id", "unknown")
                        
                        message_counts[msg_id] = message_counts.get(msg_id, 0) + 1
                        category_counts[msg_type] = category_counts.get(msg_type, 0) + 1
                    
                    # Extract score from stderr
                    score = 0.0
                    if pylint_result.stderr:
                        for line in pylint_result.stderr.split('\n'):
                            if 'rated at' in line:
                                try:
                                    score = float(line.split('rated at ')[1].split('/')[0])
                                    break
                                except (IndexError, ValueError):
                                    pass
                    
                    metrics["pylint"] = {
                        "score": score,
                        "total_messages": len(pylint_data),
                        "message_counts": message_counts,
                        "category_counts": category_counts
                    }
                
                except json.JSONDecodeError:
                    # Fallback: just extract score
                    score = 0.0
                    if pylint_result.stderr:
                        for line in pylint_result.stderr.split('\n'):
                            if 'rated at' in line:
                                try:
                                    score = float(line.split('rated at ')[1].split('/')[0])
                                    break
                                except (IndexError, ValueError):
                                    pass
                    
                    metrics["pylint"] = {"score": score, "total_messages": 0}
        
        except Exception as e:
            print(f"Warning: Could not collect pylint metrics: {e}")
            metrics["pylint"] = {"error": str(e)}
        
        return metrics
    
    def collect_security_metrics(self) -> Dict:
        """Collect security metrics from bandit."""
        try:
            bandit_result = subprocess.run([
                "bandit", "-r", ".", "-f", "json",
                "--exclude", "tests,migrations,venv,env"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=300)
            
            if bandit_result.stdout:
                bandit_data = json.loads(bandit_result.stdout)
                
                # Categorize issues by severity
                severity_counts = {"high": 0, "medium": 0, "low": 0}
                confidence_counts = {"high": 0, "medium": 0, "low": 0}
                
                for result in bandit_data.get("results", []):
                    severity = result.get("issue_severity", "").lower()
                    confidence = result.get("issue_confidence", "").lower()
                    
                    if severity in severity_counts:
                        severity_counts[severity] += 1
                    if confidence in confidence_counts:
                        confidence_counts[confidence] += 1
                
                return {
                    "total_issues": len(bandit_data.get("results", [])),
                    "severity_counts": severity_counts,
                    "confidence_counts": confidence_counts,
                    "files_scanned": len(bandit_data.get("metrics", {}).get("_totals", {}).get("loc", 0))
                }
        
        except Exception as e:
            print(f"Warning: Could not collect security metrics: {e}")
        
        return {"total_issues": 0, "error": "Could not collect security data"}
    
    def collect_type_checking_metrics(self) -> Dict:
        """Collect type checking metrics from mypy."""
        try:
            mypy_result = subprocess.run([
                "mypy", ".", "--ignore-missing-imports",
                "--no-strict-optional", "--show-error-codes"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=300)
            
            # Parse mypy output
            error_lines = mypy_result.stdout.split('\n')
            error_counts = {}
            total_errors = 0
            
            for line in error_lines:
                if ': error:' in line:
                    total_errors += 1
                    # Extract error code if present
                    if '[' in line and ']' in line:
                        error_code = line.split('[')[1].split(']')[0]
                        error_counts[error_code] = error_counts.get(error_code, 0) + 1
            
            return {
                "total_errors": total_errors,
                "error_counts": error_counts,
                "success": mypy_result.returncode == 0
            }
        
        except Exception as e:
            print(f"Warning: Could not collect type checking metrics: {e}")
        
        return {"total_errors": 0, "error": str(e)}
    
    def collect_documentation_metrics(self) -> Dict:
        """Collect documentation metrics."""
        try:
            # Count Python files and their docstrings
            python_files = list(self.project_root.rglob("*.py"))
            python_files = [f for f in python_files if not any(
                skip in str(f) for skip in ["venv", "env", "__pycache__", ".git", "migrations"]
            )]
            
            total_files = len(python_files)
            documented_files = 0
            total_functions = 0
            documented_functions = 0
            
            for file_path in python_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Simple check for module docstring
                    if '"""' in content or "'''" in content:
                        documented_files += 1
                    
                    # Count functions and their docstrings (simplified)
                    import ast
                    try:
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                total_functions += 1
                                if ast.get_docstring(node):
                                    documented_functions += 1
                    except SyntaxError:
                        continue
                
                except (UnicodeDecodeError, IOError):
                    continue
            
            return {
                "total_files": total_files,
                "documented_files": documented_files,
                "file_documentation_percentage": (documented_files / total_files * 100) if total_files > 0 else 0,
                "total_functions": total_functions,
                "documented_functions": documented_functions,
                "function_documentation_percentage": (documented_functions / total_functions * 100) if total_functions > 0 else 0
            }
        
        except Exception as e:
            print(f"Warning: Could not collect documentation metrics: {e}")
        
        return {"error": str(e)}
    
    def generate_comprehensive_report(self) -> Dict:
        """Generate comprehensive quality metrics report."""
        print("Collecting code quality metrics...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "metrics": {}
        }
        
        # Collect all metrics
        print("  - Coverage metrics...")
        report["metrics"]["coverage"] = self.collect_coverage_metrics()
        
        print("  - Complexity metrics...")
        report["metrics"]["complexity"] = self.collect_complexity_metrics()
        
        print("  - Linting metrics...")
        report["metrics"]["linting"] = self.collect_linting_metrics()
        
        print("  - Security metrics...")
        report["metrics"]["security"] = self.collect_security_metrics()
        
        print("  - Type checking metrics...")
        report["metrics"]["type_checking"] = self.collect_type_checking_metrics()
        
        print("  - Documentation metrics...")
        report["metrics"]["documentation"] = self.collect_documentation_metrics()
        
        # Calculate overall quality score
        report["quality_score"] = self._calculate_quality_score(report["metrics"])
        
        # Save report
        report_file = self.reports_dir / f"quality_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        # Also save as latest
        with open(self.reports_dir / "quality_metrics_latest.json", "w") as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def _calculate_quality_score(self, metrics: Dict) -> Dict:
        """Calculate overall quality score based on metrics."""
        scores = {}
        weights = {}
        
        # Coverage score (0-100)
        if "coverage" in metrics and "total_coverage" in metrics["coverage"]:
            scores["coverage"] = min(100, metrics["coverage"]["total_coverage"])
            weights["coverage"] = 0.25
        
        # Complexity score (inverse of complexity)
        if "complexity" in metrics and "cyclomatic_complexity" in metrics["complexity"]:
            cc = metrics["complexity"]["cyclomatic_complexity"]
            if "average_complexity" in cc:
                # Score decreases as complexity increases
                complexity_score = max(0, 100 - (cc["average_complexity"] - 1) * 10)
                scores["complexity"] = complexity_score
                weights["complexity"] = 0.20
        
        # Linting score (based on pylint score)
        if "linting" in metrics and "pylint" in metrics["linting"]:
            pylint_data = metrics["linting"]["pylint"]
            if "score" in pylint_data:
                scores["linting"] = max(0, pylint_data["score"] * 10)  # Convert to 0-100 scale
                weights["linting"] = 0.20
        
        # Security score (inverse of issues)
        if "security" in metrics and "total_issues" in metrics["security"]:
            security_issues = metrics["security"]["total_issues"]
            # Score decreases with more security issues
            security_score = max(0, 100 - security_issues * 5)
            scores["security"] = security_score
            weights["security"] = 0.15
        
        # Type checking score (inverse of errors)
        if "type_checking" in metrics and "total_errors" in metrics["type_checking"]:
            type_errors = metrics["type_checking"]["total_errors"]
            # Score decreases with more type errors
            type_score = max(0, 100 - type_errors * 2)
            scores["type_checking"] = type_score
            weights["type_checking"] = 0.10
        
        # Documentation score
        if "documentation" in metrics:
            doc_data = metrics["documentation"]
            if "file_documentation_percentage" in doc_data:
                scores["documentation"] = doc_data["file_documentation_percentage"]
                weights["documentation"] = 0.10
        
        # Calculate weighted average
        if scores and weights:
            total_weight = sum(weights.values())
            weighted_sum = sum(score * weights.get(category, 0) for category, score in scores.items())
            overall_score = weighted_sum / total_weight if total_weight > 0 else 0
        else:
            overall_score = 0
        
        return {
            "overall_score": round(overall_score, 2),
            "category_scores": scores,
            "weights": weights,
            "grade": self._score_to_grade(overall_score)
        }
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def print_summary(self, report: Dict) -> None:
        """Print quality metrics summary."""
        print("\n" + "="*60)
        print("CODE QUALITY METRICS REPORT")
        print("="*60)
        
        quality_score = report.get("quality_score", {})
        print(f"Overall Quality Score: {quality_score.get('overall_score', 0):.1f}/100 (Grade: {quality_score.get('grade', 'N/A')})")
        
        print("\nCategory Scores:")
        print("-" * 30)
        for category, score in quality_score.get("category_scores", {}).items():
            print(f"{category.title():20} {score:6.1f}/100")
        
        metrics = report.get("metrics", {})
        
        # Coverage summary
        if "coverage" in metrics:
            cov = metrics["coverage"]
            print(f"\nTest Coverage: {cov.get('total_coverage', 0):.1f}%")
        
        # Complexity summary
        if "complexity" in metrics and "cyclomatic_complexity" in metrics["complexity"]:
            cc = metrics["complexity"]["cyclomatic_complexity"]
            print(f"Average Complexity: {cc.get('average_complexity', 0):.1f}")
            print(f"High Complexity Functions: {cc.get('high_complexity_functions', 0)}")
        
        # Linting summary
        if "linting" in metrics:
            lint = metrics["linting"]
            if "pylint" in lint:
                print(f"Pylint Score: {lint['pylint'].get('score', 0):.1f}/10")
            if "flake8" in lint:
                print(f"Flake8 Issues: {lint['flake8'].get('total_issues', 0)}")
        
        # Security summary
        if "security" in metrics:
            sec = metrics["security"]
            print(f"Security Issues: {sec.get('total_issues', 0)}")
        
        print(f"\nReport saved to: {self.reports_dir}")
        print("="*60)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Code Quality Metrics Collector")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )
    
    args = parser.parse_args()
    
    collector = QualityMetricsCollector(args.project_root)
    report = collector.generate_comprehensive_report()
    collector.print_summary(report)
    
    # Exit with error code if quality score is too low
    quality_score = report.get("quality_score", {}).get("overall_score", 0)
    if quality_score < 70:  # Minimum acceptable quality score
        print(f"\nWarning: Quality score ({quality_score:.1f}) is below acceptable threshold (70)")
        sys.exit(1)


if __name__ == "__main__":
    main()