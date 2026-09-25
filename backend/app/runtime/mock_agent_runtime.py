"""
MockAgentRuntime — Deterministic Agent Adapter for Hermetic E2E Testing
=======================================================================

Purpose
-------
This module provides a drop-in replacement for AgentRuntime that exercises the
*exact same execution path* through the ASTRA graph without requiring:
  - A real OpenHands SDK installation
  - A live LLM API key (Gemini / OpenAI / Anthropic)
  - A network connection

What it proves
--------------
The mock deliberately performs REAL work at every layer the production agent would:
  1. Reads the goal and broken file list from the workspace (real filesystem)
  2. Runs pytest to confirm tests currently FAIL (real subprocess)
  3. Parses failure output to identify root cause (real parsing)
  4. Writes the corrected source file (real file write)
  5. Runs pytest again to confirm tests now PASS (real subprocess)
  6. Returns AstraExecutionResult with real modified_files list

What it does NOT prove (LLM boundary — clearly marked)
-------------------------------------------------------
  ✗ LLM reasoning to generate the fix — replaced by a registry of deterministic
    fix strategies keyed on the test name / error keyword
  ✗ OpenHands tool-call protocol (FileEditorTool / TerminalTool events)

Design contract: ASTRA's orchestration, verification, debug, replan, commit, PR,
security, and audit layers are all exercised against REAL artifacts. The only
synthetic component is the fix-generation logic.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.observability.logging import logger
from app.runtime.agent_runtime import AstraAgentEvent, AstraExecutionResult, AstraToolCall
from app.runtime.workspace import IsolatedWorkspace


# ---------------------------------------------------------------------------
# Deterministic fix strategies
# Each strategy key is matched against the pytest failure output (lowercase).
# The value is a callable(workspace_path) -> None that writes the fix.
# ---------------------------------------------------------------------------

def _fix_authenticate_false(workspace_path: Path) -> None:
    """Fix: authenticate() always returns False → fix to check token prefix."""
    auth_file = workspace_path / "auth.py"
    auth_file.write_text(
        'def authenticate(token: str) -> bool:\n'
        '    """Return True for tokens with the valid_token prefix."""\n'
        '    return token.startswith("valid_token")\n',
        encoding="utf-8",
    )


_FIX_REGISTRY: List[tuple[str, Callable[[Path], None]]] = [
    # (substring to match in pytest stdout/stderr, fix function)
    ("authenticate", _fix_authenticate_false),
    ("assert authenticate", _fix_authenticate_false),
]


def _run_pytest(workspace_path: Path, test_file: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run pytest in the workspace, optionally scoped to a single test file."""
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    if test_file:
        cmd.append(test_file)
    return subprocess.run(
        cmd,
        cwd=workspace_path,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _find_test_files(workspace_path: Path) -> List[str]:
    """Return relative paths of all test files in the workspace."""
    return [
        str(p.relative_to(workspace_path))
        for p in workspace_path.rglob("test_*.py")
        if ".git" not in p.parts and "__pycache__" not in p.parts
    ]


class MockAgentRuntime:
    """
    Deterministic agent runtime for hermetic E2E tests.

    Usage (test only):
        runtime = MockAgentRuntime()
        result = runtime.execute_task(workspace=ws, prompt=goal)

    See module docstring for the explicit LLM boundary.
    """

    def execute_task(
        self,
        workspace: IsolatedWorkspace,
        prompt: str,
        on_event: Optional[Callable[[AstraAgentEvent], None]] = None,
        max_iterations: Optional[int] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> AstraExecutionResult:
        start = datetime.now(timezone.utc)
        tool_calls: List[AstraToolCall] = []

        def emit(event_type: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
            ev = AstraAgentEvent(event_type=event_type, message=message, payload=payload or {})
            if on_event:
                try:
                    on_event(ev)
                except Exception as cb_err:
                    logger.warning(f"[MockAgent] on_event callback error: {cb_err}")

        emit("TASK_STARTED", f"[MockAgent] Starting deterministic execution for: {prompt[:80]}")
        ws_path = workspace.path

        # ------------------------------------------------------------------ #
        # Step 1: Run tests — expect them to FAIL (broken repo)               #
        # ------------------------------------------------------------------ #
        test_files = _find_test_files(ws_path)
        if not test_files:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return AstraExecutionResult(
                success=False,
                task_id=workspace.task_id,
                message="[MockAgent] No test files found in workspace.",
                error="no_tests_found",
                duration_seconds=duration,
            )

        emit("TOOL_EVENT", f"[MockAgent] Running initial tests to confirm failure", {"cmd": "pytest"})
        initial_run = _run_pytest(ws_path)
        tool_calls.append(AstraToolCall(
            id="mock-tc-01",
            name="terminal:pytest",
            arguments={"cwd": str(ws_path)},
            result=initial_run.stdout[:1000],
        ))

        initial_passed = initial_run.returncode == 0
        combined_initial_output = initial_run.stdout + initial_run.stderr
        emit(
            "OBSERVATION",
            f"[MockAgent] Initial test run exit={initial_run.returncode} — "
            f"{'PASSING (no fix needed)' if initial_passed else 'FAILING (fix required)'}",
        )

        # If tests already pass, nothing to fix
        if initial_passed:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            modified_files = workspace.get_modified_files()
            emit("TASK_COMPLETED", "[MockAgent] Tests already passing — no code change required.")
            return AstraExecutionResult(
                success=True,
                task_id=workspace.task_id,
                message="Tests already passing. No modifications required.",
                tool_calls=tool_calls,
                modified_files=modified_files,
                duration_seconds=duration,
                total_iterations=1,
            )

        # ------------------------------------------------------------------ #
        # Step 2: Select and apply a deterministic fix strategy               #
        # [LLM BOUNDARY] — production code uses OpenHands + LLM here          #
        # ------------------------------------------------------------------ #
        fix_applied = False
        fix_description = "no fix strategy matched"

        for keyword, fix_fn in _FIX_REGISTRY:
            if keyword.lower() in combined_initial_output.lower() or keyword.lower() in prompt.lower():
                emit("TOOL_EVENT", f"[MockAgent] Applying fix strategy for keyword='{keyword}'",
                     {"file": "auth.py", "strategy": fix_fn.__name__})
                tool_calls.append(AstraToolCall(
                    id="mock-tc-02",
                    name="file_editor:write",
                    arguments={"file": "auth.py", "strategy": fix_fn.__name__},
                    result="fix written",
                ))
                fix_fn(ws_path)
                fix_applied = True
                fix_description = f"Applied fix strategy '{fix_fn.__name__}' for keyword '{keyword}'"
                break

        if not fix_applied:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return AstraExecutionResult(
                success=False,
                task_id=workspace.task_id,
                message=f"[MockAgent] No fix strategy matched prompt/output. Escalating.",
                error="no_fix_strategy_matched",
                tool_calls=tool_calls,
                duration_seconds=duration,
            )

        # ------------------------------------------------------------------ #
        # Step 3: Run tests again — must PASS to declare success              #
        # ------------------------------------------------------------------ #
        emit("TOOL_EVENT", "[MockAgent] Running tests post-fix to verify correction", {"cmd": "pytest"})
        post_run = _run_pytest(ws_path)
        tool_calls.append(AstraToolCall(
            id="mock-tc-03",
            name="terminal:pytest",
            arguments={"cwd": str(ws_path), "phase": "post_fix"},
            result=post_run.stdout[:1000],
        ))
        emit(
            "OBSERVATION",
            f"[MockAgent] Post-fix test run exit={post_run.returncode} — "
            f"{'PASSING ✅' if post_run.returncode == 0 else 'STILL FAILING ❌'}",
        )

        duration = (datetime.now(timezone.utc) - start).total_seconds()
        modified_files = workspace.get_modified_files()
        success = post_run.returncode == 0

        if success:
            emit("TASK_COMPLETED", f"[MockAgent] Fix verified. {fix_description}")
        else:
            emit("ERROR", f"[MockAgent] Fix did not resolve failures. Needs escalation.")

        return AstraExecutionResult(
            success=success,
            task_id=workspace.task_id,
            message=(
                f"[MockAgent] {fix_description}. "
                f"Post-fix pytest exit={post_run.returncode}.\n"
                f"Output: {post_run.stdout[-600:]}"
            ),
            tool_calls=tool_calls,
            modified_files=modified_files,
            duration_seconds=duration,
            total_iterations=len(tool_calls),
            error=None if success else f"Post-fix tests still failing (exit {post_run.returncode})",
        )
