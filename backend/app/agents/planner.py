from __future__ import annotations

from typing import Any, Dict, List

from app.agents.state import AstraAgentState
from app.observability.logging import logger


def plan_task(state: AstraAgentState) -> Dict[str, Any]:
    """
    Generates a repository-aware, goal-specific execution plan grounded in
    the detected architecture, symbols, frameworks, and test runners.
    """
    goal = state.get("user_goal", "")
    task_id = state.get("task_id", "")
    context = state.get("repository_context", {})
    summary = context.get("summary", {})
    files = context.get("files", [])
    symbols = context.get("symbols", [])
    test_cmd = summary.get("test_command") or context.get("test_command") or "pytest"
    backend = summary.get("backend") or "Application"

    logger.info(f"[{task_id}] Generating repository-aware execution plan for: {goal}")

    # Identify primary candidate files based on goal keywords, flow chain, and past memories
    target_files = []
    goal_words = set(goal.lower().split())
    flow_chain = context.get("flow_chain")
    past_memories = context.get("past_memories", [])

    for f in files:
        if any(w in f.lower() for w in goal_words if len(w) > 3):
            target_files.append(f)

    # Add files from past related tasks if present
    for mem in past_memories:
        for mf in mem.get("files_modified", []):
            if mf not in target_files and mf in files:
                target_files.append(mf)

    if not target_files and files:
        target_files = files[:3]

    plan_steps = [
        {
            "step": 1,
            "description": f"Inspect repository architecture ({backend}, {len(files)} files, {len(symbols)} symbols)" + (f" and trace flow: {flow_chain['summary']}" if flow_chain and flow_chain.get("summary") else ""),
            "status": "pending",
            "targets": target_files[:3],
            "flow_chain": flow_chain.get("summary") if flow_chain else None
        }
    ]

    # If prior experience exists, add memory reflection step
    if past_memories:
        top_mem = past_memories[0]
        discoveries_text = "; ".join(top_mem.get("discoveries", []))[:150]
        plan_steps.append({
            "step": 2,
            "description": f"Apply prior task memory from {top_mem.get('task_id')}: {discoveries_text or 'utilize past solution patterns'}",
            "status": "pending",
            "past_task_id": top_mem.get("task_id")
        })

    next_step_num = len(plan_steps) + 1
    plan_steps.extend([
        {
            "step": next_step_num,
            "description": f"Implement changes for goal: '{goal}'",
            "status": "pending",
            "framework": backend
        },
        {
            "step": next_step_num + 1,
            "description": f"Execute test verification suite using '{test_cmd}'",
            "status": "pending",
            "command": test_cmd
        },
        {
            "step": next_step_num + 2,
            "description": "Inspect git diff, ensure zero unintended regressions, and compile verified report",
            "status": "pending"
        }
    ])

    plan = plan_steps


    messages = list(state.get("messages", []))
    messages.append({
        "role": "assistant",
        "content": f"Repository-aware plan generated: {len(plan)} tailored steps for {backend}."
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
