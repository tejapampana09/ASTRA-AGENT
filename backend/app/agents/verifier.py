from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.agents.state import AstraAgentState
from app.observability.logging import logger
from app.verification.build import BuildRunner
from app.verification.diff import DiffEngine
from app.verification.lint import LintRunner
from app.verification.tests import TestRunner


def verify_solution(state: AstraAgentState) -> Dict[str, Any]:
    """
    Rigorously verifies the task implementation using autonomous test runner,
    build validation, linter, and git diff inspection.
    Never claims success without evidence!
    """
    task_id = state.get("task_id", "")
    workspace_path_str = state.get("workspace_path")

    if not workspace_path_str:
        return {
            "verification_status": "uncertain",
            "errors": list(state.get("errors", [])) + ["Verification failed: workspace path missing."]
        }

    ws_path = Path(workspace_path_str)

    logger.info(f"[{task_id}] Running rigorous verification suite...")

    # 1. Run Tests
    test_report = TestRunner.run_tests(ws_path)

    # 2. Run Build
    build_report = BuildRunner.run_build(ws_path)

    # 3. Run Lint
    lint_report = LintRunner.run_lint(ws_path)

    # 4. Inspect Diff
    diff_report = DiffEngine.inspect_diff(ws_path)

    # Determine status based on empirical evidence
    status = "failed"
    if test_report.status == "passed" and test_report.passed > 0 and build_report.status != "failed":
        status = "verified"
    elif test_report.status == "no_tests_found":
        # If no tests exist, cannot establish verified correctness -> UNCERTAIN
        status = "uncertain"
    elif test_report.failed > 0 or test_report.status == "failed" or build_report.status == "failed":
        status = "failed"

    verification_evidence = {
        "status": status,
        "tests": {
            "passed": test_report.passed,
            "failed": test_report.failed,
            "errors": test_report.errors,
            "skipped": test_report.skipped,
            "total": test_report.total,
            "status": test_report.status,
            "failures": [
                {"test": f.test_name, "error": f.error_message}
                for f in test_report.failures
            ]
        },
        "build": build_report.status,
        "lint": lint_report.status,
        "files_changed": diff_report.files_changed_count,
        "total_added": diff_report.total_added,
        "total_deleted": diff_report.total_deleted,
    }

    logger.info(f"[{task_id}] Verification result: {status} (tests: {test_report.passed} passed, {test_report.failed} failed)")

    return {
        "verification_status": status,
        "test_results": test_report.to_dict(),
        "build_results": build_report.to_dict(),
        "git_diff": diff_report.raw_diff,
        "files_changed": [f.file_path for f in diff_report.files],
        "observations": list(state.get("observations", [])) + [
            f"Verification: {status} (Tests passed: {test_report.passed}, failed: {test_report.failed})"
        ]
    }
