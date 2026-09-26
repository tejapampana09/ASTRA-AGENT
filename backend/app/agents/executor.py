from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.agents.state import AstraAgentState
from app.observability.logging import logger
from app.runtime.agent_runtime import AgentRuntime
from app.runtime.workspace import IsolatedWorkspace


def execute_step(state: AstraAgentState) -> Dict[str, Any]:
    """
    Executes the next planned action using the ASTRA OpenHands Agent Runtime adapter.
    """
    task_id = state.get("task_id", "default_task")
    workspace_path_str = state.get("workspace_path")
    goal = state.get("user_goal", "")
    iteration_count = state.get("iteration_count", 0) + 1

    logger.info(f"[{task_id}] Executing agent step (iteration {iteration_count})")

    # If approval is required and still pending, pause execution
    if state.get("approval_required") and state.get("approval_status") == "pending":
        logger.warning(f"[{task_id}] Execution paused pending human approval.")
        return {
            "iteration_count": iteration_count,
            "observations": list(state.get("observations", [])) + ["Waiting for human approval before execution."]
        }

    if not workspace_path_str:
        return {
            "errors": list(state.get("errors", [])) + ["Workspace path not specified in state."],
            "iteration_count": iteration_count
        }

    ws_path = Path(workspace_path_str)
    workspace = IsolatedWorkspace(task_id=task_id, path=ws_path, is_git_repo=(ws_path / ".git").exists())

    # Build prompt combining goal and failure feedback if replanning
    prompt_lines = [
        f"Task Goal: {goal}",
        "Execute the necessary modifications in the workspace.",
        "Ensure tests are created or modified to verify your solution.",
        "IMPORTANT: You are already in the repository root directory. Always use relative paths for all commands and file operations (e.g. `research/utils/io.py`, `tests/test_io.py`, `pytest tests/test_audit.py`). Avoid unquoted absolute paths containing spaces.",
    ]

    failure_history = state.get("failure_history", [])
    if failure_history:
        latest_failure = failure_history[-1]
        prompt_lines.append("\nPREVIOUS ATTEMPT FAILED WITH:")
        prompt_lines.append(f"Failing tests / errors: {latest_failure.get('error', 'unknown error')}")
        prompt_lines.append(f"Traceback snippet: {latest_failure.get('traceback', '')[:400]}")
        prompt_lines.append("Analyze this failure, fix the root cause, and do not repeat the exact same approach.")

    prompt = "\n".join(prompt_lines)

    # ------------------------------------------------------------------
    # Runtime selection: ASTRA_MOCK_AGENT=1 → MockAgentRuntime (tests)
    # Production: AgentRuntime (OpenHands SDK + real LLM)
    # ------------------------------------------------------------------
    import os
    if os.environ.get("ASTRA_MOCK_AGENT") == "1":
        from app.runtime.mock_agent_runtime import MockAgentRuntime
        runtime: Any = MockAgentRuntime()
    else:
        runtime = AgentRuntime()

    # Stream real-time events to event_broker so UI activity feed updates live
    import asyncio
    from app.runtime.lifecycle import event_broker
    from app.runtime.events import TaskEvent

    def on_agent_event(ev):
        try:
            event_broker.publish_sync(
                TaskEvent(
                    task_id=task_id,
                    event_type=ev.event_type,
                    message=ev.message,
                    payload=ev.payload or {}
                )
            )
        except Exception as err:
            logger.warning(f"Failed to stream agent event: {err}")

    task_model = state.get("model")
    if not task_model or task_model in ["gemini", "cloud", "flash"]:
        task_model = "gemini/gemini-3.8-flash"
    elif task_model in ["ollama", "local", "qwen"]:
        task_model = "ollama/qwen2.5-coder:3b"

    result = runtime.execute_task(
        workspace=workspace,
        prompt=prompt,
        on_event=on_agent_event,
        model=task_model
    )

    tool_calls_dict = [
        {"id": tc.id, "name": tc.name, "arguments": tc.arguments, "result": tc.result}
        for tc in result.tool_calls
    ]

    observations = list(state.get("observations", []))
    observations.append(f"Iteration {iteration_count}: {result.message[:200]}")

    errors = list(state.get("errors", []))
    if result.error:
        errors.append(result.error)

    return {
        "iteration_count": iteration_count,
        "tool_calls": list(state.get("tool_calls", [])) + tool_calls_dict,
        "observations": observations,
        "errors": errors,
        "files_changed": result.modified_files,
    }


def observe_step(state: AstraAgentState) -> Dict[str, Any]:
    """
    Observes the workspace state following tool execution.
    Inspects changed files and git status.
    """
    task_id = state.get("task_id", "")
    workspace_path_str = state.get("workspace_path")
    observations = list(state.get("observations", []))

    if workspace_path_str:
        ws_path = Path(workspace_path_str)
        workspace = IsolatedWorkspace(task_id=task_id, path=ws_path, is_git_repo=(ws_path / ".git").exists())
        diff = workspace.get_git_diff()
        observations.append(f"Post-execution diff captured ({len(diff)} characters).")
        return {
            "observations": observations,
            "git_diff": diff
        }

    return {"observations": observations}
