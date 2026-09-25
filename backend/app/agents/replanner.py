from __future__ import annotations

from typing import Any, Dict

from app.agents.state import AstraAgentState
from app.config import settings
from app.observability.logging import logger


def replan_step(state: AstraAgentState) -> Dict[str, Any]:
    """
    Replans the execution strategy following failure analysis.
    Increments retry count and updates the step plan.
    """
    task_id = state.get("task_id", "")
    retry_count = state.get("retry_count", 0) + 1
    failure_history = state.get("failure_history", [])

    logger.info(f"[{task_id}] Replanning task (retry {retry_count}/{settings.MAX_RETRIES})")

    latest_err = failure_history[-1]["error"] if failure_history else "Previous attempt failed"

    plan = [
        {"step": 1, "description": f"Diagnose root cause of: {latest_err}", "status": "pending"},
        {"step": 2, "description": "Apply targeted source patch avoiding previous failure pattern", "status": "pending"},
        {"step": 3, "description": "Re-execute test runner and verify fix", "status": "pending"},
    ]

    observations = list(state.get("observations", []))
    observations.append(f"Replanner: Initiated retry #{retry_count} with targeted fix plan.")

    return {
        "retry_count": retry_count,
        "plan": plan,
        "observations": observations,
        "current_step": 1
    }
