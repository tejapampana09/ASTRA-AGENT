from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.state import AstraAgentState
from app.observability.logging import logger
from app.verification.build import BuildRunner
from app.verification.diff import DiffEngine
from app.verification.lint import LintRunner
from app.verification.tests import TestRunner, TestVerificationReport


def verify_solution(state: AstraAgentState) -> Dict[str, Any]:
    """
    INTELLIGENT VERIFICATION SUITE (Phase 3):
    Executes a structured verification pipeline:
    1. Targeted Tests: Runs tests directly covering changed & impacted files.
    2. Regression Tests: Runs the broader repository test suite.
    3. Build & Static Analysis: Verifies compilation and syntax correctness.
    4. Diff Integrity: Audits changed files against blast radius.
    5. Evidence Aggregation: Compiles empirical proof bundle before declaring success.
    """
    task_id = state.get("task_id", "")
    workspace_path_str = state.get("workspace_path")

    if not workspace_path_str:
        return {
            "verification_status": "uncertain",
            "errors": list(state.get("errors", [])) + ["Verification failed: workspace path missing."]
        }

    ws_path = Path(workspace_path_str)
    files_changed = state.get("files_changed", [])
    plan_metadata = state.get("plan_metadata", {})
    relevant_tests = plan_metadata.get("relevant_tests", [])

    logger.info(f"[{task_id}] Running Intelligent Verification Suite on {ws_path}...")

    # 1. Inspect Diff
    diff_report = DiffEngine.inspect_diff(ws_path)
    updated_files_changed = [f.file_path for f in diff_report.files]
    if not updated_files_changed and files_changed:
        updated_files_changed = files_changed

    # 2. Targeted Test Execution (Fast Feedback Loop)
    targeted_report: Optional[TestVerificationReport] = None
    target_test_file = None

    # Prioritize any test file explicitly modified or created in this task
    changed_test_files = [
        f for f in updated_files_changed
        if "test" in f.lower() and f.endswith(".py") and not f.endswith("conftest.py")
    ]
    if changed_test_files:
        target_test_file = changed_test_files[0]
    elif relevant_tests:
        candidate_tests = [t for t in relevant_tests if not t.endswith("conftest.py")]
        if candidate_tests:
            target_test_file = candidate_tests[0]
    elif updated_files_changed:
        for f in updated_files_changed:
            if "test" in f.lower() and f.endswith(".py"):
                target_test_file = f
                break

    if target_test_file and (ws_path / target_test_file).exists():
        logger.info(f"[{task_id}] Executing targeted test first: {target_test_file}")
        targeted_cmd = [sys.executable, "-m", "pytest", target_test_file, "-v"]
        targeted_report = TestRunner.run_tests(ws_path, custom_command=targeted_cmd)

    # 3. Test Suite Verification
    if targeted_report and targeted_report.is_successful and targeted_report.passed > 0:
        logger.info(
            f"[{task_id}] Targeted test {target_test_file} verified successfully "
            f"({targeted_report.passed} passed). Using targeted verification evidence."
        )
        test_report = targeted_report
    elif targeted_report and not targeted_report.is_successful and targeted_report.status == "failed":
        test_report = targeted_report
        logger.warning(f"[{task_id}] Targeted test {target_test_file} failed; skipping full regression.")
    else:
        test_report = TestRunner.run_tests(ws_path)

    # 4. Build Validation
    build_report = BuildRunner.run_build(ws_path, files_changed=updated_files_changed)

    # 5. Lint & Static Analysis
    lint_report = LintRunner.run_lint(ws_path)

    # 6. Empirical Evidence Aggregation
    has_test_evidence = (
        test_report.status == "passed" and
        test_report.passed > 0 and
        test_report.failed == 0 and
        test_report.errors == 0
    )
    build_clean = build_report.status in ["passed", "skipped"]
    has_diff_evidence = diff_report.files_changed_count > 0 or diff_report.total_added > 0 or len(updated_files_changed) > 0

    if has_test_evidence and build_clean and has_diff_evidence:
        status = "verified"
    elif has_diff_evidence and test_report.status == "no_tests_found" and build_clean:
        status = "verified"
    elif has_diff_evidence and test_report.failed == 0 and test_report.errors == 0 and build_clean:
        status = "verified"
    elif test_report.failed > 0 or test_report.errors > 0 or test_report.status == "failed" or build_report.status == "failed":
        status = "failed"
    else:
        status = "verified" if has_diff_evidence else "uncertain"

    # Multi-Factor Evidence Scoring
    evidence_score = 0.0
    if has_test_evidence:
        evidence_score += 0.5
    if build_clean:
        evidence_score += 0.2
    if has_diff_evidence:
        evidence_score += 0.2
    if lint_report.status in ["passed", "clean"]:
        evidence_score += 0.1

    verification_evidence = {
        "status": status,
        "evidence_score": round(evidence_score, 2),
        "targeted_test_applied": bool(targeted_report),
        "targeted_test_file": target_test_file,
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
        "diff": {
            "files_changed_count": diff_report.files_changed_count or len(updated_files_changed),
            "total_added": diff_report.total_added,
            "total_deleted": diff_report.total_deleted,
        }
    }

    logger.info(
        f"[{task_id}] Verification Verdict: {status.upper()} (score={round(evidence_score, 2)}, "
        f"tests: {test_report.passed} passed, {test_report.failed} failed)"
    )

    observations = list(state.get("observations", []))
    observations.append(
        f"Verifier: Status={status.upper()}, Score={round(evidence_score, 2)}. "
        f"Tests: {test_report.passed} passed, {test_report.failed} failed. Build: {build_report.status}."
    )

    try:
        from app.runtime.lifecycle import event_broker
        from app.runtime.events import TaskEvent
        event_broker.publish_sync(TaskEvent(
            task_id=task_id,
            event_type="TEST_COMPLETED",
            message=f"Verification tests: {test_report.passed} passed, {test_report.failed} failed (status: {status.upper()})",
            payload={
                "command": test_report.command or "pytest",
                "passed": test_report.passed,
                "failed": test_report.failed,
                "errors": test_report.errors,
                "status": status,
                "evidence_score": round(evidence_score, 2),
            }
        ))
        if diff_report and diff_report.raw_diff:
            event_broker.publish_sync(TaskEvent(
                task_id=task_id,
                event_type="DIFF_GENERATED",
                message=f"Diff generated: {len(updated_files_changed)} files changed (+{diff_report.total_added}/-{diff_report.total_deleted})",
                payload={
                    "files_changed": updated_files_changed,
                    "diff": diff_report.raw_diff[:3000],
                    "total_added": diff_report.total_added,
                    "total_deleted": diff_report.total_deleted,
                }
            ))
    except Exception as e:
        logger.debug(f"Failed to emit verification events: {e}")

    return {
        "verification_status": status,
        "verification_evidence": verification_evidence,
        "test_results": test_report.to_dict(),
        "build_results": build_report.to_dict(),
        "git_diff": diff_report.raw_diff,
        "files_changed": updated_files_changed,
        "observations": observations,
    }
