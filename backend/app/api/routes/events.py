from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.runtime.lifecycle import event_broker, task_lifecycle

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream/{task_id}")
async def stream_task_events(task_id: str, request: Request):
    """
    Server-Sent Events (SSE) endpoint streaming real-time agent updates.
    """
    task = task_lifecycle.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    queue = event_broker.subscribe(task_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Yield initial connection confirmation
            yield json.dumps({"event_type": "CONNECTED", "task_id": task_id, "message": "Stream connected."})

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield json.dumps(event.to_dict())
                    if event.event_type in ["TASK_COMPLETED", "TASK_FAILED", "TASK_CANCELLED"]:
                        break
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": ping\n\n"
        finally:
            event_broker.unsubscribe(task_id, queue)

    return EventSourceResponse(event_generator())
