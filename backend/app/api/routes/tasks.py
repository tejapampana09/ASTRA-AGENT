from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_task_lifecycle
from app.runtime.lifecycle import TaskLifecycleManager

router = APIRouter(prefix="/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    goal: str = Field(..., description="High-level engineering task prompt")
    repository_path: Optional[str] = Field(None, description="Optional local path or source repo to clone/copy")
    timeout_seconds: Optional[int] = Field(None, description="Optional custom task runtime timeout in seconds")


class TaskResponse(BaseModel):
    task_id: str
    goal: str
    status: str
    verification_status: str
    workspace_path: Optional[str] = None
    created_at: str
    final_report: Optional[Dict[str, Any]] = None


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=TaskResponse)
async def create_task(
    req: CreateTaskRequest,
    lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle)
):
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    task_info = lifecycle.create_task(
        task_id=task_id,
        goal=req.goal,
        repository_path=req.repository_path,
        timeout_seconds=req.timeout_seconds,
    )
    # Dispatch execution in background task without blocking HTTP response
    lifecycle.dispatch_task(task_id)

    return TaskResponse(**task_info)


@router.get("", response_model=List[TaskResponse])
async def list_tasks(lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle)):
    return [TaskResponse(**t) for t in lifecycle.list_tasks()]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle)):
    task_info = lifecycle.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskResponse(**task_info)


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle)):
    task_info = lifecycle.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    cancelled = lifecycle.cancel_task(task_id)
    return {"task_id": task_id, "cancelled": cancelled}


@router.post("/{task_id}/recover")
async def recover_task(task_id: str, lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle)):
    """P4.2 Crash-restart checkpoint recovery endpoint."""
    task_info = lifecycle.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    recovery_result = await lifecycle.recover_and_resume_task(task_id)
    return recovery_result


@router.get("/{task_id}/health")
async def get_task_health(task_id: str, lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle)):
    """P4.2 Task health, heartbeat, and liveness monitor."""
    task_info = lifecycle.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return lifecycle.get_task_health(task_id)


@router.get("/{task_id}/audit")
async def get_task_audit(task_id: str, lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle)):
    """
    P4.5 Execution Timeline + Evidence Audit Endpoint.
    Returns comprehensive auditable record of decisions, executed commands,
    file diffs, empirical evidence, failure triages, and PR references.
    """
    from app.runtime.events import central_event_bus

    task_info = lifecycle.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    events = central_event_bus.get_history(task_id, limit=500)
    final_report = task_info.get("final_report") or {}
    evidence = final_report.get("evidence") or {}

    audit_report = {
        "task_id": task_id,
        "goal": task_info.get("goal"),
        "status": task_info.get("status"),
        "verification_status": task_info.get("verification_status"),
        "workspace_path": task_info.get("workspace_path"),
        "timing": {
            "created_at": task_info.get("created_at"),
            "started_at": task_info.get("started_at"),
            "completed_at": task_info.get("completed_at"),
            "timeout_seconds": task_info.get("timeout_seconds"),
        },
        "timeline_events": [e.to_dict() for e in events],
        "decisions": final_report.get("decisions", []),
        "commands_and_tools": final_report.get("tool_calls", []),
        "files_touched": evidence.get("files_changed", []),
        "git_diff": final_report.get("git_diff", ""),
        "empirical_verification": {
            "test_results": evidence.get("tests", {}),
            "build_status": evidence.get("build", "unknown"),
            "verification_status": task_info.get("verification_status"),
            "evidence_score": evidence.get("verification_evidence", {}).get("evidence_score", 0.0),
        },
        "failure_and_retry_history": final_report.get("failure_history", []),
        "commit": final_report.get("commit"),
        "pull_request": final_report.get("pull_request"),
        "token_usage_and_cost": {
            "total_tokens": final_report.get("total_tokens", 0),
            "estimated_cost_usd": final_report.get("estimated_cost_usd", 0.0),
        },
    }
    return audit_report


