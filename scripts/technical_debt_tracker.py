#!/usr/bin/env python3
"""
Technical Debt Tracker

This script analyzes the codebase for technical debt indicators and generates
reports to help prioritize refactoring efforts.
"""

import ast
import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


@dataclass
class TechnicalDebtItem:
    """Represents a technical debt item."""
    file_path: str
    line_number: int
    debt_type: str
    severity: str
    description: str
    estimated_effort: str
    priority: int


class TechnicalDebtTracker:
    """Tracks and analyzes technical debt in the codebase."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.debt_items: List[TechnicalDebtItem] = []
        self.reports_dir = self.project_root / "quality_reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Technical debt patterns
        self.debt_patterns = {
            "TODO": {
                "pattern": r"#\s*TODO:?\s*(.+)",
                "severity": "medium",
                "effort": "small"
            },
            "FIXME": {
                "pattern": r"#\s*FIXME:?\s*(.+)",
                "severity": "high",
                "effort": "medium"
            },
            "HACK": {
                "pattern": r"#\s*HACK:?\s*(.+)",
                "severity": "high",
                "effort": "medium"
            },
            "XXX": {
                "pattern": r"#\s*XXX:?\s*(.+)",
                "severity": "high",
                "effort": "medium"
            },
            "DEPRECATED": {
                "pattern": r"#\s*DEPRECATED:?\s*(.+)",
                "severity": "medium",
                "effort": "large"
            }
        }
    
    def scan_code_comments(self) -> None:
        """Scan code for technical debt comments."""
        python_files = list(self.project_root.rglob("*.py"))
        
        for file_path in python_files:
            # Skip certain directories
            if any(skip in str(file_path) for skip in ["venv", "env", "__pycache__", ".git", "migrations"]):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    for debt_type, config in self.debt_patterns.items():
                        match = re.search(config["pattern"], line, re.IGNORECASE)
                        if match:
                            description = match.group(1).strip()
                            
                            debt_item = TechnicalDebtItem(
                                file_path=str(file_path.relative_to(self.project_root)),
                                line_number=line_num,
                                debt_type=debt_type,
                                severity=config["severity"],
                                description=description,
                                estimated_effort=config["effort"],
                                priority=self._calculate_priority(config["severity"], debt_type)
                            )
                            self.debt_items.append(debt_item)
            
            except (UnicodeDecodeError, IOError) as e:
                print(f"Warning: Could not read {file_path}: {e}")
    
    def analyze_complexity(self) -> Dict:
        """Analyze code complexity using radon."""
        try:
            # Cyclomatic complexity
            cc_result = subprocess.run(
                ["radon", "cc", ".", "--json", "--exclude", "tests,migrations,venv,env"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if cc_result.returncode == 0:
                cc_data = json.loads(cc_result.stdout)
                
                # Find high complexity functions
                for file_path, functions in cc_data.items():
                    for func in functions:
                        if func.get('complexity', 0) > 10:  # High complexity threshold
                            debt_item = TechnicalDebtItem(
                                file_path=file_path,
                                line_number=func.get('lineno', 0),
                                debt_type="HIGH_COMPLEXITY",
                                severity="medium",
                                description=f"Function '{func.get('name')}' has high cyclomatic complexity: {func.get('complexity')}",
                                estimated_effort="medium",
                                priority=self._calculate_priority("medium", "HIGH_COMPLEXITY")
                            )
                            self.debt_items.append(debt_item)
                
                return cc_data
            
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not analyze complexity: {e}")
        
        return {}
    
    def analyze_maintainability(self) -> Dict:
        """Analyze maintainability index using radon."""
        try:
            mi_result = subprocess.run(
                ["radon", "mi", ".", "--json", "--exclude", "tests,migrations,venv,env"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if mi_result.returncode == 0:
                mi_data = json.loads(mi_result.stdout)
                
                # Find low maintainability files
                for file_path, mi_info in mi_data.items():
                    mi_score = mi_info.get('mi', 100)
                    if mi_score < 20:  # Low maintainability threshold
                        debt_item = TechnicalDebtItem(
                            file_path=file_path,
                            line_number=1,
                            debt_type="LOW_MAINTAINABILITY",
                            severity="high" if mi_score < 10 else "medium",
                            description=f"Low maintainability index: {mi_score:.2f}",
                            estimated_effort="large",
                            priority=self._calculate_priority("high" if mi_score < 10 else "medium", "LOW_MAINTAINABILITY")
                        )
                        self.debt_items.append(debt_item)
                
                return mi_data
            
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not analyze maintainability: {e}")
        
        return {}
    
    def analyze_code_duplication(self) -> None:
        """Analyze code duplication."""
        # This is a simplified duplication detector
        # In a real implementation, you might use tools like jscpd or similar
        
        python_files = list(self.project_root.rglob("*.py"))
        function_signatures = defaultdict(list)
        
        for file_path in python_files:
            if any(skip in str(file_path) for skip in ["venv", "env", "__pycache__", ".git", "migrations"]):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse AST to find function definitions
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Create a simple signature
                            args = [arg.arg for arg in node.args.args]
                            signature = f"{node.name}({', '.join(args)})"
                            function_signatures[signature].append((file_path, node.lineno))
                
                except SyntaxError:
                    continue
                    
            except (UnicodeDecodeError, IOError):
                continue
        
        # Find potential duplicates
        for signature, locations in function_signatures.items():
            if len(locations) > 1:
                for file_path, line_num in locations:
                    debt_item = TechnicalDebtItem(
                        file_path=str(file_path.relative_to(self.project_root)),
                        line_number=line_num,
                        debt_type="POTENTIAL_DUPLICATION",
                        severity="low",
                        description=f"Potential duplicate function signature: {signature}",
                        estimated_effort="small",
                        priority=self._calculate_priority("low", "POTENTIAL_DUPLICATION")
                    )
                    self.debt_items.append(debt_item)
    
    def analyze_large_files(self) -> None:
        """Identify large files that might need refactoring."""
        python_files = list(self.project_root.rglob("*.py"))
        
        for file_path in python_files:
            if any(skip in str(file_path) for skip in ["venv", "env", "__pycache__", ".git", "migrations"]):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                line_count = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
                
                if line_count > 500:  # Large file threshold
                    debt_item = TechnicalDebtItem(
                        file_path=str(file_path.relative_to(self.project_root)),
                        line_number=1,
                        debt_type="LARGE_FILE",
                        severity="medium" if line_count > 1000 else "low",
                        description=f"Large file with {line_count} lines of code",
                        estimated_effort="large",
                        priority=self._calculate_priority("medium" if line_count > 1000 else "low", "LARGE_FILE")
                    )
                    self.debt_items.append(debt_item)
                    
            except (UnicodeDecodeError, IOError):
                continue
    
    def _calculate_priority(self, severity: str, debt_type: str) -> int:
        """Calculate priority score for debt item."""
        severity_scores = {"low": 1, "medium": 2, "high": 3}
        type_multipliers = {
            "FIXME": 3,
            "HACK": 3,
            "XXX": 3,
            "HIGH_COMPLEXITY": 2,
            "LOW_MAINTAINABILITY": 3,
            "TODO": 1,
            "DEPRECATED": 2,
            "POTENTIAL_DUPLICATION": 1,
            "LARGE_FILE": 2
        }
        
        base_score = severity_scores.get(severity, 1)
        multiplier = type_multipliers.get(debt_type, 1)
        
        return base_score * multiplier
    
    def generate_report(self) -> Dict:
        """Generate comprehensive technical debt report."""
        # Run all analyses
        self.debt_items.clear()
        self.scan_code_comments()
        complexity_data = self.analyze_complexity()
        maintainability_data = self.analyze_maintainability()
        self.analyze_code_duplication()
        self.analyze_large_files()
        
        # Sort by priority
        self.debt_items.sort(key=lambda x: x.priority, reverse=True)
        
        # Generate summary statistics
        debt_by_type = defaultdict(int)
        debt_by_severity = defaultdict(int)
        debt_by_file = defaultdict(int)
        
        for item in self.debt_items:
            debt_by_type[item.debt_type] += 1
            debt_by_severity[item.severity] += 1
            debt_by_file[item.file_path] += 1
        
        # Create report
        report = {
            "timestamp": subprocess.run(
                ["date", "-Iseconds"], capture_output=True, text=True
            ).stdout.strip(),
            "summary": {
                "total_debt_items": len(self.debt_items),
                "high_priority_items": len([item for item in self.debt_items if item.priority >= 6]),
                "debt_by_type": dict(debt_by_type),
                "debt_by_severity": dict(debt_by_severity),
                "most_problematic_files": dict(sorted(debt_by_file.items(), key=lambda x: x[1], reverse=True)[:10])
            },
            "debt_items": [
                {
                    "file_path": item.file_path,
                    "line_number": item.line_number,
                    "debt_type": item.debt_type,
                    "severity": item.severity,
                    "description": item.description,
                    "estimated_effort": item.estimated_effort,
                    "priority": item.priority
                }
                for item in self.debt_items
            ],
            "complexity_analysis": complexity_data,
            "maintainability_analysis": maintainability_data
        }
        
        # Save report
        with open(self.reports_dir / "technical_debt_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def generate_action_plan(self, report: Dict) -> Dict:
        """Generate an action plan for addressing technical debt."""
        high_priority_items = [
            item for item in report["debt_items"] 
            if item["priority"] >= 6
        ]
        
        # Group by estimated effort
        effort_groups = defaultdict(list)
        for item in high_priority_items:
            effort_groups[item["estimated_effort"]].append(item)
        
        action_plan = {
            "quick_wins": effort_groups.get("small", [])[:10],  # Top 10 small effort items
            "medium_effort": effort_groups.get("medium", [])[:5],  # Top 5 medium effort items
            "large_refactoring": effort_groups.get("large", [])[:3],  # Top 3 large effort items
            "recommendations": self._generate_recommendations(report)
        }
        
        # Save action plan
        with open(self.reports_dir / "debt_action_plan.json", "w") as f:
            json.dump(action_plan, f, indent=2)
        
        return action_plan
    
    def _generate_recommendations(self, report: Dict) -> List[str]:
        """Generate recommendations based on debt analysis."""
        recommendations = []
        
        summary = report["summary"]
        
        if summary["debt_by_type"].get("HIGH_COMPLEXITY", 0) > 5:
            recommendations.append(
                "Consider refactoring high-complexity functions to improve maintainability"
            )
        
        if summary["debt_by_type"].get("LARGE_FILE", 0) > 3:
            recommendations.append(
                "Break down large files into smaller, more focused modules"
            )
        
        if summary["debt_by_severity"].get("high", 0) > 10:
            recommendations.append(
                "Prioritize addressing high-severity technical debt items"
            )
        
        if summary["debt_by_type"].get("POTENTIAL_DUPLICATION", 0) > 10:
            recommendations.append(
                "Review and eliminate code duplication to improve maintainability"
            )
        
        if summary["total_debt_items"] > 50:
            recommendations.append(
                "Consider implementing regular technical debt reduction sprints"
            )
        
        return recommendations
    
    def print_summary(self, report: Dict) -> None:
        """Print technical debt report summary."""
        print("\n" + "="*60)
        print("TECHNICAL DEBT ANALYSIS REPORT")
        print("="*60)
        
        summary = report["summary"]
        
        print(f"Total debt items: {summary['total_debt_items']}")
        print(f"High priority items: {summary['high_priority_items']}")
        
        print("\nDebt by Type:")
        print("-" * 30)
        for debt_type, count in summary["debt_by_type"].items():
            print(f"{debt_type:25} {count:5}")
        
        print("\nDebt by Severity:")
        print("-" * 30)
        for severity, count in summary["debt_by_severity"].items():
            print(f"{severity:25} {count:5}")
        
        print("\nMost Problematic Files:")
        print("-" * 40)
        for file_path, count in list(summary["most_problematic_files"].items())[:5]:
            print(f"{file_path:35} {count:5}")
        
        print(f"\nReports saved to: {self.reports_dir}")
        print("="*60)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Technical Debt Tracker")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )
    parser.add_argument(
        "--action-plan",
        action="store_true",
        help="Generate action plan"
    )
    
    args = parser.parse_args()
    
    tracker = TechnicalDebtTracker(args.project_root)
    report = tracker.generate_report()
    tracker.print_summary(report)
    
    if args.action_plan:
        action_plan = tracker.generate_action_plan(report)
        print("\nAction plan generated: debt_action_plan.json")


if __name__ == "__main__":
    main()