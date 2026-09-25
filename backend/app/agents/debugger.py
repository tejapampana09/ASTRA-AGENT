from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.agents.state import AstraAgentState
from app.observability.logging import logger


class FailureCategory(str, Enum):
    SYNTAX = "syntax"
    TYPE = "type"
    DEPENDENCY = "dependency"
    RUNTIME = "runtime"
    TEST_ASSERTION = "test_assertion"
    INTEGRATION = "integration"
    ENVIRONMENT = "environment"
    UNKNOWN = "unknown"


class AutonomousDebugger:
    """
    AUTONOMOUS DEBUGGER & ROOT CAUSE ANALYZER (Phase 3):
    Replaces blind retries with systematic triage:
    1. Categorizes failure into 7-tier taxonomy.
    2. Parses stack traces to isolate suspect user code (file & line).
    3. Analyzes root cause and formulates concrete fix hypothesis.
    4. Compares against previous failed hypotheses to prevent regression cycles.
    """

    @staticmethod
    def classify_failure(error_msg: str, traceback_str: str = "") -> FailureCategory:
        """Classifies the failure into one of 7 distinct categories."""
        combined = f"{error_msg}\n{traceback_str}".lower()

        # 1. Syntax Errors
        if any(w in combined for w in ["syntaxerror", "indentationerror", "taberror", "invalid syntax"]):
            return FailureCategory.SYNTAX

        # 2. Type / Attribute Errors
        if any(w in combined for w in ["typeerror", "attributeerror", "has no attribute", "unexpected keyword argument", "missing required positional argument"]):
            return FailureCategory.TYPE

        # 3. Dependency / Import Errors
        if any(w in combined for w in ["modulenotfounderror", "importerror", "no module named", "cannot import name"]):
            return FailureCategory.DEPENDENCY

        # 4. Integration / Service Errors
        if any(w in combined for w in ["connectionrefused", "connection refused", "500 internal server error", "operationalerror", "database error", "sqlalchemy.exc"]):
            return FailureCategory.INTEGRATION

        # 5. Environment / OS / Permission Errors
        if any(w in combined for w in ["permissionerror", "permission denied", "filenotfounderror", "no such file or directory", "environmentvariable"]):
            return FailureCategory.ENVIRONMENT

        # 6. Test Assertion Failures
        if any(w in combined for w in ["assertionerror", "assert ", "failed (failures=", "failed (errors="]):
            return FailureCategory.TEST_ASSERTION

        # 7. General Runtime Exceptions
        if any(w in combined for w in ["keyerror", "indexerror", "valueerror", "zerodivisionerror", "runtimeerror"]):
            return FailureCategory.RUNTIME

        return FailureCategory.UNKNOWN

    @staticmethod
    def locate_root_cause(
        traceback_str: str,
        error_msg: str = "",
        workspace_path: Optional[Path] = None
    ) -> Tuple[Optional[str], Optional[int], str]:
        """
        Parses python traceback frames and error text, filtering out library frames
        to pinpoint the user code file and line number where the fault originated.
        """
        suspect_file = None
        suspect_line = None
        suspect_func = None

        if traceback_str:
            # 1. Regex to match standard Python traceback frames: File "path", line 123, in func
            frame_pattern = re.compile(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([^\n]+))?')
            matches = frame_pattern.findall(traceback_str)

            for f_path, line_no, func_name in reversed(matches):
                f_norm = f_path.replace("\\", "/")
                if any(ign in f_norm.lower() for ign in ["site-packages", "lib/python", "pytest", "pluggy", "unittest"]):
                    continue
                suspect_file = f_norm
                suspect_line = int(line_no)
                suspect_func = func_name
                break

            if not suspect_file and matches:
                last_match = matches[-1]
                suspect_file = last_match[0].replace("\\", "/")
                suspect_line = int(last_match[1])
                suspect_func = last_match[2]

        # 2. Regex to match file.py:line or path/file.py:line (pytest short output / compiler style)
        if not suspect_file:
            combined = f"{error_msg}\n{traceback_str}"
            path_line_pattern = re.compile(r'([a-zA-Z0-9_\-\\/]+\.(?:py|ts|js|jsx|tsx)):(\d+)')
            pl_matches = path_line_pattern.findall(combined)
            for f_path, line_no in pl_matches:
                f_norm = f_path.replace("\\", "/")
                if not any(ign in f_norm.lower() for ign in ["site-packages", "lib/python", "pytest"]):
                    suspect_file = f_norm
                    suspect_line = int(line_no)
                    break

        if suspect_file:
            explanation = f"Failure originated in {suspect_file}:{suspect_line}" + (f" ({suspect_func})" if suspect_func else "")
        else:
            explanation = "No specific code location isolated from traceback."

        return suspect_file, suspect_line, explanation

    @classmethod
    def generate_fix_hypothesis(
        cls,
        category: FailureCategory,
        error_msg: str,
        suspect_file: Optional[str],
        suspect_line: Optional[int],
        failure_history: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Generates a structured fix hypothesis avoiding repeat mistakes from prior iterations.
        """
        prior_hypotheses = [f.get("hypothesis", "") for f in failure_history if f.get("hypothesis")]

        if category == FailureCategory.SYNTAX:
            hypothesis = f"Correct invalid syntax, brackets, or indentation around {suspect_file or 'modified code'} line {suspect_line or 'unknown'}."
            fix = "Inspect syntax tree around the flagged line and restore valid Python syntax structure."

        elif category == FailureCategory.TYPE:
            hypothesis = f"Method argument or object attribute mismatch in {suspect_file or 'target module'}. Verify function signatures and object types."
            fix = "Check class/function definition signature and adjust invocation arguments or add type guard."

        elif category == FailureCategory.DEPENDENCY:
            missing_mod = re.findall(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
            mod_name = missing_mod[0] if missing_mod else "dependency"
            hypothesis = f"Module '{mod_name}' is missing or import path is incorrect in {suspect_file or 'source files'}."
            fix = f"Ensure '{mod_name}' is imported using correct package path or declare in pyproject/requirements."

        elif category == FailureCategory.TEST_ASSERTION:
            hypothesis = f"Test assertion violated in {suspect_file or 'test suite'}. Expected return value or HTTP status differs from actual output."
            fix = "Align implementation logic with test expectations or update assertions if requirement changed."

        elif category == FailureCategory.INTEGRATION:
            hypothesis = "Subsystem integration or connection failure. Component failed to communicate with peer service or schema."
            fix = "Verify endpoint path, request payload schema, and mock/fallback configuration for external services."

        elif category == FailureCategory.ENVIRONMENT:
            hypothesis = "Environment configuration or file path resolution error."
            fix = "Use relative pathing or ensure required configuration environment variables have defaults."

        else:
            hypothesis = f"Runtime error in {suspect_file or 'code'}: {error_msg[:120]}."
            fix = "Add boundary checks, handle null/None values, or wrap volatile logic in appropriate exception handling."

        # Anti-cycle protection: ensure this hypothesis doesn't repeat an identical prior failed fix
        if any(h == hypothesis for h in prior_hypotheses):
            hypothesis = f"[Alternative Hypothesis] Prior hypothesis failed. Shift strategy: inspect upstream callers and data flow for {suspect_file or 'system'}."
            fix = "Refactor integration contract instead of patching local line."

        return {
            "hypothesis": hypothesis,
            "proposed_fix": fix
        }


def debug_failure(state: AstraAgentState) -> Dict[str, Any]:
    """
    AUTONOMOUS DEBUGGER NODE (Phase 3):
    Invoked when verification fails. Performs classification, root-cause localization,
    and hypothesis generation, appending findings to `failure_history`.
    """
    task_id = state.get("task_id", "")
    test_results = state.get("test_results", {})
    build_results = state.get("build_results", {})
    failure_history = list(state.get("failure_history", []))
    workspace_path_str = state.get("workspace_path")
    ws_p = Path(workspace_path_str) if workspace_path_str else None

    # Extract primary failure signal
    failures = test_results.get("failures", [])
    failure_summary = "Unknown verification failure"
    traceback_sample = ""

    if failures:
        primary_failure = failures[0]
        t_name = primary_failure.get("test_name", "Test")
        e_msg = primary_failure.get("error", "Failed")
        failure_summary = f"{t_name}: {e_msg}"
        traceback_sample = primary_failure.get("traceback", "")
    elif build_results.get("status") == "failed":
        failure_summary = f"Build failure: {build_results.get('stderr', '')[:200]}"
        traceback_sample = build_results.get("stderr", "")
    elif test_results.get("status") == "no_tests_found":
        failure_summary = "Verification uncertain: No executable tests identified in workspace."
    elif test_results.get("output"):
        failure_summary = test_results.get("output")[:300]
        traceback_sample = test_results.get("output")

    # 1. Categorize Failure
    category = AutonomousDebugger.classify_failure(failure_summary, traceback_sample)

    # 2. Pinpoint Root Cause Location
    suspect_file, suspect_line, location_explanation = AutonomousDebugger.locate_root_cause(
        traceback_str=traceback_sample,
        error_msg=failure_summary,
        workspace_path=ws_p
    )

    # 3. Formulate Fix Hypothesis
    fix_data = AutonomousDebugger.generate_fix_hypothesis(
        category=category,
        error_msg=failure_summary,
        suspect_file=suspect_file,
        suspect_line=suspect_line,
        failure_history=failure_history
    )

    failure_record = {
        "iteration": state.get("iteration_count", 0),
        "retry": state.get("retry_count", 0),
        "error": failure_summary,
        "category": category.value,
        "suspect_file": suspect_file,
        "suspect_line": suspect_line,
        "root_cause": location_explanation,
        "hypothesis": fix_data["hypothesis"],
        "proposed_fix": fix_data["proposed_fix"],
        "result": "failed",
        "traceback": traceback_sample[:600],
    }
    failure_history.append(failure_record)

    logger.warning(
        f"[{task_id}] Autonomous Debugger Triaged: [{category.value.upper()}] "
        f"{location_explanation} -> Hypothesis: {fix_data['hypothesis']}"
    )

    observations = list(state.get("observations", []))
    observations.append(
        f"Debugger: Triaged failure #{len(failure_history)} as [{category.value.upper()}]. "
        f"Root Cause: {location_explanation}. Fix Hypothesis: {fix_data['hypothesis']}"
    )

    return {
        "failure_history": failure_history,
        "last_failure_diagnosis": failure_record,
        "observations": observations,
    }
