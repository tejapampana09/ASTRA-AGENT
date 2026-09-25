from __future__ import annotations

from typing import Any, Dict, List

from app.agents.state import AstraAgentState
from app.config import settings
from app.observability.logging import logger


def replan_step(state: AstraAgentState) -> Dict[str, Any]:
    """
    DYNAMIC REPLANNING ENGINE (Phase 3):
    Synthesizes a brand new, targeted execution plan incorporating:
    - Original user goal
    - Previous failed plan
    - Changed files from prior attempt
    - Diagnosed root cause, failure category, and fix hypothesis from Autonomous Debugger
    - Repository context and past task memories
    """
    task_id = state.get("task_id", "")
    retry_count = state.get("retry_count", 0) + 1
    failure_history = state.get("failure_history", [])
    files_changed = state.get("files_changed", [])
    last_diag = state.get("last_failure_diagnosis", {})
    context = state.get("repository_context", {})
    summary = context.get("summary", {})
    test_cmd = summary.get("test_command") or context.get("test_command") or "pytest"

    if last_diag:
        category = last_diag.get("category", "unknown").upper()
        root_cause = last_diag.get("root_cause", "Unspecified failure location")
        hypothesis = last_diag.get("hypothesis", "Fix implementation defect")
        proposed_fix = last_diag.get("proposed_fix", "Refactor offending logic")
        suspect_file = last_diag.get("suspect_file")
    elif failure_history:
        latest_err = failure_history[-1]
        category = latest_err.get("category", "unknown").upper()
        root_cause = latest_err.get("root_cause", latest_err.get("error", "Error"))
        hypothesis = latest_err.get("hypothesis", "Fix implementation defect")
        proposed_fix = latest_err.get("proposed_fix", "Refactor offending logic")
        suspect_file = latest_err.get("suspect_file")
    else:
        category = "UNKNOWN"
        root_cause = "Previous attempt failed verification"
        hypothesis = "Review diff and align with requirements"
        proposed_fix = "Correct discrepancies"
        suspect_file = files_changed[0] if files_changed else None

    logger.info(f"[{task_id}] Replanner formulating retry #{retry_count}/{settings.MAX_RETRIES} for [{category}]")

    target_repair_file = suspect_file or (files_changed[0] if files_changed else "target module")

    # Generate specialized plan steps directly targeted at the diagnosed root cause
    replan_steps: List[Dict[str, Any]] = [
        {
            "step": 1,
            "stage": "root_cause_inspection",
            "description": f"Inspect {target_repair_file} and verify diagnosed root cause: {root_cause}.",
            "status": "pending",
            "target": target_repair_file,
            "category": category,
            "depends_on": [],
        },
        {
            "step": 2,
            "stage": "targeted_repair",
            "description": f"Apply fix hypothesis in {target_repair_file}: {hypothesis}. Action: {proposed_fix}.",
            "status": "pending",
            "target": target_repair_file,
            "depends_on": [1],
        },
        {
            "step": 3,
            "stage": "targeted_verification",
            "description": f"Execute targeted test runner on modified component to confirm root cause is resolved.",
            "status": "pending",
            "command": f"{test_cmd} {target_repair_file}" if target_repair_file.endswith(".py") else test_cmd,
            "depends_on": [2],
        },
        {
            "step": 4,
            "stage": "regression_verification",
            "description": f"Run full regression suite ('{test_cmd}') to ensure fix introduced zero side-effects.",
            "status": "pending",
            "command": test_cmd,
            "depends_on": [3],
        }
    ]

    messages = list(state.get("messages", []))
    messages.append({
        "role": "assistant",
        "content": (
            f"Replanning initiated for retry #{retry_count}: Diagnosed as [{category}]. "
            f"Formulated targeted 4-stage remediation plan focused on {target_repair_file}."
        )
    })

    observations = list(state.get("observations", []))
    observations.append(
        f"Replanner: Initiated retry #{retry_count} with targeted fix plan for {target_repair_file} [{category}]."
    )

    return {
        "retry_count": retry_count,
        "plan": replan_steps,
        "current_step": 1,
        "messages": messages,
        "observations": observations,
    }
