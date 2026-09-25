from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from app.observability.metrics import metrics_collector
from app.observability.tracing import tracer

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_platform_metrics() -> Dict[str, Any]:
    """
    P4.6 Observability Endpoint:
    Returns platform-wide aggregate metrics, verification pass rate %,
    total tokens, cost estimation, tool latencies, and failure distributions.
    """
    return metrics_collector.get_aggregate_summary()


@router.get("/{task_id}")
async def get_task_metrics(task_id: str) -> Dict[str, Any]:
    """
    Returns task-level metrics including token usage, estimated costs,
    tool execution latencies, and OpenTelemetry trace spans.
    """
    task_metrics = metrics_collector.get_or_create(task_id)
    spans = tracer.get_task_spans(task_id)

    res = task_metrics.to_dict()
    res["trace_spans"] = spans
    return res
