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

