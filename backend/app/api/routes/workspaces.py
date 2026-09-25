from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.runtime.workspace import WorkspaceManager

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCleanupRequest(BaseModel):
    max_age_seconds: int = Field(86400, description="Purge workspaces older than this age in seconds")
    max_workspaces: Optional[int] = Field(None, description="Max workspaces to retain before purging LRU")
    max_disk_bytes: Optional[int] = Field(None, description="Max disk usage bytes before purging LRU")


@router.get("")
async def list_workspaces() -> Dict[str, Any]:
    """List all active workspaces and overall storage metrics."""
    wm = WorkspaceManager()
    return wm.get_storage_summary()


@router.get("/{task_id}")
async def get_workspace_details(task_id: str) -> Dict[str, Any]:
    """Get metadata and file details for a specific task workspace."""
    wm = WorkspaceManager()
    ws = wm.get_workspace(task_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace for task '{task_id}' not found")

    return {
        "task_id": ws.task_id,
        "path": str(ws.path),
        "is_git_repo": ws.is_git_repo,
        "is_dirty": ws.is_dirty(),
        "modified_files": ws.get_modified_files(),
        "files_count": len(ws.list_files()),
        "disk_usage_bytes": ws.get_disk_usage(),
        "metadata": ws.metadata.to_dict() if ws.metadata else None,
    }


@router.delete("/{task_id}")
async def delete_workspace(task_id: str) -> Dict[str, Any]:
    """Manually delete a specific task workspace."""
    wm = WorkspaceManager()
    success = wm.cleanup_workspace(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Workspace for task '{task_id}' not found or could not be removed")
    return {"status": "deleted", "task_id": task_id}


@router.post("/cleanup")
async def trigger_workspace_cleanup(req: WorkspaceCleanupRequest) -> Dict[str, Any]:
    """Trigger automated workspace retention policy garbage collection."""
    wm = WorkspaceManager()
    purged = wm.cleanup_stale_workspaces(
        max_age_seconds=req.max_age_seconds,
        max_workspaces=req.max_workspaces,
        max_disk_bytes=req.max_disk_bytes,
    )
    return {
        "status": "success",
        "purged_count": len(purged),
        "purged_task_ids": purged,
        "storage_summary": wm.get_storage_summary(),
    }
