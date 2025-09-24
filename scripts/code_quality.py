#!/usr/bin/env python3
"""
Code Quality Management Script

This script provides comprehensive code quality checks, formatting, and reporting
for the SAT Report Generator application.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class CodeQualityManager:
    """Manages code quality checks and reporting."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.reports_dir = self.project_root / "quality_reports"
        self.reports_dir.mkdir(exist_ok=True)
        
    def run_black(self, check_only: bool = False) -> Tuple[bool, str]:
        """Run Black code formatter."""
        cmd = ["black"]
        if check_only:
            cmd.extend(["--check", "--diff"])
        cmd.extend(["--line-length", "127", "."])
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=self.project_root,
                capture_output=True, 
                text=True, 
                timeout=300
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Black formatting timed out"
        except Exception as e:
            return False, f"Black formatting failed: {str(e)}"
    
    def run_isort(self, check_only: bool = False) -> Tuple[bool, str]:
        """Run isort import sorter."""
        cmd = ["isort"]
        if check_only:
            cmd.extend(["--check-only", "--diff"])
        cmd.extend(["--profile", "black", "--line-length", "127", "."])
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "isort timed out"
        except Exception as e:
            return False, f"isort failed: {str(e)}"
    
    def run_flake8(self) -> Tuple[bool, str]:
        """Run Flake8 linting."""
        cmd = [
            "flake8", ".",
            "--max-line-length=127",
            "--extend-ignore=E203,W503",
            "--exclude=migrations,venv,env,.git,__pycache__,build,dist,.eggs,*.egg-info",
            "--format=json",
            "--output-file", str(self.reports_dir / "flake8_report.json")
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Flake8 returns non-zero if issues found, but that's expected
            output = result.stdout + result.stderr
            
            # Try to read the JSON report
            report_file = self.reports_dir / "flake8_report.json"
            if report_file.exists():
                with open(report_file) as f:
                    try:
                        issues = json.load(f)
                        return len(issues) == 0, f"Found {len(issues)} issues"
                    except json.JSONDecodeError:
                        pass
            
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, "Flake8 timed out"
        except Exception as e:
            return False, f"Flake8 failed: {str(e)}"
    
    def run_pylint(self) -> Tuple[bool, str]:
        """Run Pylint analysis."""
        cmd = [
            "pylint", ".",
            "--output-format=json",
            "--reports=no",
            "--score=yes"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            # Save pylint report
            report_file = self.reports_dir / "pylint_report.json"
            with open(report_file, "w") as f:
                f.write(result.stdout)
            
            # Extract score from stderr (pylint outputs score to stderr)
            score_line = [line for line in result.stderr.split('\n') if 'rated at' in line]
            score = "Unknown"
            if score_line:
                try:
                    score = score_line[0].split('rated at ')[1].split('/')[0]
                except (IndexError, ValueError):
                    pass
            
            return result.returncode == 0, f"Pylint score: {score}/10"
        except subprocess.TimeoutExpired:
            return False, "Pylint timed out"
        except Exception as e:
            return False, f"Pylint failed: {str(e)}"
    
    def run_mypy(self) -> Tuple[bool, str]:
        """Run mypy type checking."""
        cmd = [
            "mypy", ".",
            "--ignore-missing-imports",
            "--no-strict-optional",
            "--json-report", str(self.reports_dir / "mypy_report")
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "mypy timed out"
        except Exception as e:
            return False, f"mypy failed: {str(e)}"
    
    def run_bandit(self) -> Tuple[bool, str]:
        """Run Bandit security analysis."""
        cmd = [
            "bandit", "-r", ".",
            "-f", "json",
            "-o", str(self.reports_dir / "bandit_report.json"),
            "--exclude", "tests,migrations,venv,env"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Read the report to get issue count
            report_file = self.reports_dir / "bandit_report.json"
            if report_file.exists():
                with open(report_file) as f:
                    try:
                        report = json.load(f)
                        issues = len(report.get('results', []))
                        return issues == 0, f"Found {issues} security issues"
                    except json.JSONDecodeError:
                        pass
            
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Bandit timed out"
        except Exception as e:
            return False, f"Bandit failed: {str(e)}"
    
    def run_radon(self) -> Tuple[bool, str]:
        """Run Radon complexity analysis."""
        # Cyclomatic complexity
        cc_cmd = [
            "radon", "cc", ".",
            "--json",
            "--exclude", "tests,migrations,venv,env"
        ]
        
        # Maintainability index
        mi_cmd = [
            "radon", "mi", ".",
            "--json",
            "--exclude", "tests,migrations,venv,env"
        ]
        
        try:
            # Run cyclomatic complexity
            cc_result = subprocess.run(
                cc_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Save CC report
            with open(self.reports_dir / "radon_cc_report.json", "w") as f:
                f.write(cc_result.stdout)
            
            # Run maintainability index
            mi_result = subprocess.run(
                mi_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Save MI report
            with open(self.reports_dir / "radon_mi_report.json", "w") as f:
                f.write(mi_result.stdout)
            
            return True, "Complexity analysis completed"
        except subprocess.TimeoutExpired:
            return False, "Radon timed out"
        except Exception as e:
            return False, f"Radon failed: {str(e)}"
    
    def generate_quality_report(self) -> Dict:
        """Generate comprehensive quality report."""
        report = {
            "timestamp": subprocess.run(
                ["date", "-Iseconds"], capture_output=True, text=True
            ).stdout.strip(),
            "checks": {}
        }
        
        checks = [
            ("formatting_black", lambda: self.run_black(check_only=True)),
            ("imports_isort", lambda: self.run_isort(check_only=True)),
            ("linting_flake8", self.run_flake8),
            ("analysis_pylint", self.run_pylint),
            ("typing_mypy", self.run_mypy),
            ("security_bandit", self.run_bandit),
            ("complexity_radon", self.run_radon),
        ]
        
        for check_name, check_func in checks:
            print(f"Running {check_name}...")
            success, message = check_func()
            report["checks"][check_name] = {
                "passed": success,
                "message": message
            }
        
        # Save comprehensive report
        with open(self.reports_dir / "quality_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def fix_issues(self) -> None:
        """Automatically fix code quality issues where possible."""
        print("Fixing formatting with Black...")
        self.run_black(check_only=False)
        
        print("Fixing import order with isort...")
        self.run_isort(check_only=False)
        
        print("Auto-fixes completed. Please review changes.")
    
    def print_summary(self, report: Dict) -> None:
        """Print quality report summary."""
        print("\n" + "="*60)
        print("CODE QUALITY REPORT SUMMARY")
        print("="*60)
        
        total_checks = len(report["checks"])
        passed_checks = sum(1 for check in report["checks"].values() if check["passed"])
        
        print(f"Total checks: {total_checks}")
        print(f"Passed: {passed_checks}")
        print(f"Failed: {total_checks - passed_checks}")
        print(f"Success rate: {(passed_checks/total_checks)*100:.1f}%")
        
        print("\nDetailed Results:")
        print("-" * 40)
        
        for check_name, result in report["checks"].items():
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            print(f"{check_name:20} {status:8} {result['message']}")
        
        print(f"\nReports saved to: {self.reports_dir}")
        print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Code Quality Management")
    parser.add_argument(
        "--action",
        choices=["check", "fix", "report"],
        default="check",
        help="Action to perform"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )
    
    args = parser.parse_args()
    
    manager = CodeQualityManager(args.project_root)
    
    if args.action == "fix":
        manager.fix_issues()
    elif args.action == "report":
        report = manager.generate_quality_report()
        manager.print_summary(report)
    else:  # check
        report = manager.generate_quality_report()
        manager.print_summary(report)
        
        # Exit with error code if any checks failed
        failed_checks = [
            name for name, result in report["checks"].items() 
            if not result["passed"]
        ]
        if failed_checks:
            print(f"\nFailed checks: {', '.join(failed_checks)}")
            sys.exit(1)


if __name__ == "__main__":
    main()