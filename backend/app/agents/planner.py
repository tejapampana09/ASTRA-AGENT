from __future__ import annotations

from typing import Any, Dict, List

from app.agents.state import AstraAgentState
from app.observability.logging import logger


def plan_task(state: AstraAgentState) -> Dict[str, Any]:
    """Generates an initial or refined execution plan based on goal and context."""
    goal = state.get("user_goal", "")
    task_id = state.get("task_id", "")
    context = state.get("repository_context", {})

    logger.info(f"[{task_id}] Generating execution plan for: {goal}")

    # Build logical steps based on task requirements
    plan = [
        {"step": 1, "description": "Inspect repository files and directory structure", "status": "pending"},
        {"step": 2, "description": f"Implement required changes for: {goal}", "status": "pending"},
        {"step": 3, "description": "Run tests and verify implementation correctness", "status": "pending"},
        {"step": 4, "description": "Review git diff and finalize execution report", "status": "pending"},
    ]

    messages = list(state.get("messages", []))
    messages.append({
        "role": "assistant",
        "content": f"Plan initialized with {len(plan)} steps."
    })

    return {
        "plan": plan,
        "current_step": 1,
        "messages": messages
    }


def risk_assessment(state: AstraAgentState) -> Dict[str, Any]:
    """
    Evaluates whether the pending actions require human approval.
    Risk levels:
    - READ / LOW / MEDIUM: automatic
    - HIGH / CRITICAL (e.g. git push origin main, delete database, force commit): requires approval
    """
    goal = state.get("user_goal", "").lower()
    task_id = state.get("task_id", "")

    critical_keywords = ["drop database", "rm -rf /", "git push --force", "deploy to prod"]
    high_keywords = ["git push", "delete branch", "merge to main"]

    approval_required = False
    risk_level = "LOW"

    for kw in critical_keywords:
        if kw in goal:
            risk_level = "CRITICAL"
            approval_required = True
            break

    if not approval_required:
        for kw in high_keywords:
            if kw in goal:
                risk_level = "HIGH"
                approval_required = True
                break

    logger.info(f"[{task_id}] Risk Assessment: level={risk_level}, approval_required={approval_required}")

    return {
        "approval_required": approval_required,
        "approval_status": "pending" if approval_required else "not_requested",
    }
