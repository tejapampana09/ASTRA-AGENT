from __future__ import annotations

from typing import Any, Dict, List

from app.agents.state import AstraAgentState
from app.observability.logging import logger


def debug_failure(state: AstraAgentState) -> Dict[str, Any]:
    """
    Analyzes test/build failures, extracts tracebacks, identifies failing components,
    and updates failure history to prevent repetitive cycles.
    """
    task_id = state.get("task_id", "")
    test_results = state.get("test_results", {})
    build_results = state.get("build_results", {})
    failure_history = list(state.get("failure_history", []))

    failures = test_results.get("failures", [])
    failure_summary = "Unknown failure"
    traceback_sample = ""

    if failures:
        primary_failure = failures[0]
        failure_summary = f"{primary_failure.get('test_name')}: {primary_failure.get('error')}"
        traceback_sample = primary_failure.get("traceback", "")
    elif build_results.get("status") == "failed":
        failure_summary = f"Build failure: {build_results.get('stderr', '')[:200]}"
        traceback_sample = build_results.get("stderr", "")
    elif test_results.get("status") == "no_tests_found":
        failure_summary = "Verification uncertain: No test suite or assertions found in workspace."

    failure_record = {
        "iteration": state.get("iteration_count", 0),
        "error": failure_summary,
        "traceback": traceback_sample[:600],
        "exit_code": test_results.get("exit_code", -1),
    }
    failure_history.append(failure_record)

    logger.warning(f"[{task_id}] Autonomous Debugger analyzed failure: {failure_summary}")

    observations = list(state.get("observations", []))
    observations.append(f"Debugger: Recorded failure #{len(failure_history)}: {failure_summary}")

    return {
        "failure_history": failure_history,
        "observations": observations,
    }
