"""MCP Test Executor — runs all tests, collects data, analyzes failures.

Designed to be called via MCP terminal tool.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import subprocess
# Suppress CLI console windows on Windows
CREATE_NO_WINDOW = 0x08000000
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Test result data classes
@dataclass
class TestResult:
    """Result of a single test."""
    test_id: str
    name: str
    category: str
    command: str
    expected: str
    actual: str = ""
    passed: bool = False
    duration_ms: float = 0.0
    error: str = ""
    output: str = ""

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "category": self.category,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass 
class TestRunSummary:
    """Summary of a test run."""
    run_id: str
    timestamp: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total_duration_ms: float = 0.0
    results: list[TestResult] = field(default_factory=list)
    failures: list[TestResult] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    bugs: list[str] = field(default_factory=list)
    fixes_needed: list[str] = field(default_factory=list)


class MCPTestExecutor:
    """Execute MCP tests and collect results."""

    def __init__(self, project_dir: str = "C:/Projects/VM-Harness"):
        self._project_dir = Path(project_dir)
        self._venv_py = Path("/c/Users/Server/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe")
        self._results_dir = self._project_dir / "test-results"
        self._results_dir.mkdir(exist_ok=True)
        self._logger = logging.getLogger("mcp-test")

    def run_command(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """Run a shell command and return stdout, stderr, returncode."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._project_dir),
                env={
                    **os.environ,
                    "QT_QPA_PLATFORM": "offscreen",
                    "VENV_PY": str(self._venv_py),
                },
                shell=True,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "TIMEOUT", 124
        except Exception as e:
            return "", str(e), 1

    def run_test(self, test: dict) -> TestResult:
        """Run a single test."""
        result = TestResult(
            test_id=test["id"],
            name=test["name"],
            category=test["category"],
            command=test["command"],
            expected=test["expected"],
        )
        
        start = time.time()
        stdout, stderr, returncode = self.run_command(test["command"])
        result.duration_ms = (time.time() - start) * 1000
        result.output = stdout + stderr
        
        # Determine pass/fail
        if returncode == 0 and test["expected"].lower() in result.output.lower():
            result.passed = True
        else:
            result.passed = False
            result.error = stderr or stdout
        
        return result

    def run_category(self, category_name: str, tests: list[dict]) -> list[TestResult]:
        """Run all tests in a category."""
        results = []
        for test in tests:
            result = self.run_test(test)
            results.append(result)
            self._logger.info(
                "%s: %s - %s",
                test["id"],
                test["name"],
                "PASS" if result.passed else "FAIL",
            )
        return results

    def run_all_tests(self) -> TestRunSummary:
        """Run all tests and generate summary."""
        summary = TestRunSummary(
            run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now().isoformat(),
        )
        
        # Define all test categories
        categories = self._get_all_tests()
        
        for category_name, tests in categories.items():
            self._logger.info("Running category: %s", category_name)
            results = self._run_category_tests(category_name, tests)
            summary.results.extend(results)
            
            for r in results:
                if r.passed:
                    summary.passed += 1
                else:
                    summary.failed += 1
                    summary.failures.append(r)
        
        summary.total_tests = len(summary.results)
        summary.total_duration_ms = sum(r.duration_ms for r in summary.results)
        
        # Analyze failures
        self._analyze_failures(summary)
        
        # Save results
        self._save_results(summary)
        
        return summary

    def _get_all_tests(self) -> dict:
        """Get all test definitions."""
        return {
            "PANEL_INIT": [
                {
                    "id": "PANEL-001",
                    "name": "All 23 panels instantiate",
                    "category": "initialization",
                    "command": f'{self._venv_py} -c "import sys; sys.path.insert(0, 'src'); from gui.main_window import MainWindow; from PyQt5.QtWidgets import QApplication; app = QApplication.instance() or QApplication([]); w = MainWindow(); print(f'PASS: {len(w.panels)} panels')"',
                    "expected": "PASS: 23 panels",
                },
            ],
            "QMP": [
                {
                    "id": "QMP-001",
                    "name": "QMP connection",
                    "category": "connectivity",
                    "command": f'{self._venv_py} -c "import sys, asyncio; sys.path.insert(0, 'src'); from vm_harness.setup import QMPClient; async def t(): c = QMPClient('tcp:127.0.0.1:4444'); await c.connect(); print('PASS')"',
                    "expected": "PASS",
                },
            ],
            "CLI": [
                {
                    "id": "CLI-001",
                    "name": "CLI status command",
                    "category": "cli",
                    "command": f'{self._venv_py} gui/cli.py status',
                    "expected": "qemu-mcp",
                },
            ],
        }

    def _run_category_tests(self, category_name: str, tests: list[dict]) -> list[TestResult]:
        """Run tests for a category."""
        results = []
        for test in tests:
            result = self.run_test(test)
            results.append(result)
        return results

    def _analyze_failures(self, summary: TestRunSummary):
        """Analyze failures and identify gaps/bugs/fixes."""
        for failure in summary.failures:
            # Classify failure
            if "ModuleNotFoundError" in failure.output:
                summary.gaps.append(f"{failure.test_id}: Missing module - {failure.output[:100]}")
            elif "ConnectionRefusedError" in failure.output:
                summary.bugs.append(f"{failure.test_id}: Connection refused - {failure.name}")
            elif "TIMEOUT" in failure.output:
                summary.bugs.append(f"{failure.test_id}: Timeout - {failure.name}")
            elif "AssertionError" in failure.output:
                summary.bugs.append(f"{failure.test_id}: Assertion failed - {failure.name}")
            else:
                summary.gaps.append(f"{failure.test_id}: Unknown failure - {failure.output[:100]}")
            
            # Suggest fix
            summary.fixes_needed.append(f"{failure.test_id}: {failure.name} - {failure.error[:50]}")

    def _save_results(self, summary: TestRunSummary):
        """Save test results to files."""
        # JSON report
        report_file = self._results_dir / f"test-run-{summary.run_id}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "run_id": summary.run_id,
                "timestamp": summary.timestamp,
                "total": summary.total_tests,
                "passed": summary.passed,
                "failed": summary.failed,
                "pass_rate": f"{(summary.passed / summary.total_tests * 100):.1f}%" if summary.total_tests > 0 else "0%",
                "duration_ms": summary.total_duration_ms,
                "failures": [r.to_dict() for r in summary.failures],
                "gaps": summary.gaps,
                "bugs": summary.bugs,
                "fixes_needed": summary.fixes_needed,
            }, f, indent=2)
        
        # CSV report
        csv_file = self._results_dir / f"test-run-{summary.run_id}.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Test ID", "Name", "Category", "Passed", "Duration (ms)", "Error"])
            for r in summary.results:
                writer.writerow([r.test_id, r.name, r.category, r.passed, f"{r.duration_ms:.0f}", r.error])
        
        self._logger.info("Results saved to %s", report_file)


def main():
    """Run all tests."""
    logging.basicConfig(level=logging.INFO)
    executor = MCPTestExecutor()
    summary = executor.run_all_tests()
    
    print(f"
{'='*60}")
    print(f"Test Run: {summary.run_id}")
    print(f"Total: {summary.total_tests} | Passed: {summary.passed} | Failed: {summary.failed}")
    print(f"Pass Rate: {(summary.passed / summary.total_tests * 100):.1f}%" if summary.total_tests > 0 else "N/A")
    print(f"Duration: {summary.total_duration_ms:.0f}ms")
    print(f"{'='*60}")
    
    if summary.failures:
        print("
FAILURES:")
        for f in summary.failures:
            print(f"  {f.test_id}: {f.name}")
    
    if summary.gaps:
        print("
GAPS IDENTIFIED:")
        for g in summary.gaps:
            print(f"  - {g}")
    
    if summary.bugs:
        print("
BUGS FOUND:")
        for b in summary.bugs:
            print(f"  - {b}")
    
    if summary.fixes_needed:
        print("
FIXES NEEDED:")
        for fix in summary.fixes_needed:
            print(f"  - {fix}")


if __name__ == "__main__":
    main()
