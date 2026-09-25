from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.repository.scanner import RepositoryScanner, RepositorySummary

router = APIRouter(prefix="/repositories", tags=["repositories"])


class ScanRepoRequest(BaseModel):
    path: str = Field(..., description="Local filesystem path to inspect")


@router.post("/scan")
async def scan_repository(req: ScanRepoRequest) -> Dict[str, Any]:
    target = Path(req.path).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Directory path '{req.path}' does not exist")

    summary = RepositoryScanner.scan(target)
    return summary.to_dict()
