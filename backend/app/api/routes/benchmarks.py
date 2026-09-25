from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.evaluation.bench import ASTRA_BENCHMARK_TASKS, astra_bench

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


class RunBenchmarkRequest(BaseModel):
    category: Optional[str] = None


@router.get("")
async def list_benchmarks() -> List[Dict[str, Any]]:
    """Lists standard ASTRA-Bench task specifications."""
    return [
        {
            "task_id": t.task_id,
            "category": t.category,
            "name": t.name,
            "description": t.description,
            "difficulty": t.difficulty,
            "file_count": len(t.files),
        }
        for t in ASTRA_BENCHMARK_TASKS
    ]


@router.post("/run")
async def run_benchmarks(req: Optional[RunBenchmarkRequest] = None) -> Dict[str, Any]:
    """
    P4.7 ASTRA-Bench Evaluation Endpoint:
    Executes benchmark tasks across bug fixing, refactoring, feature addition,
    multi-file updates, and dependency fixes, returning scored resolution rates.
    """
    category = req.category if req else None
    result = astra_bench.run_suite(category=category)
    return result.to_dict()
