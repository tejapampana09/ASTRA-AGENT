from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.runtime.events import AgentEventType, central_event_bus
from app.runtime.lifecycle import task_lifecycle
from app.runtime.agent_runtime import AgentRuntime, AstraAgentEvent
from app.api.routes.events import stream_task_events

client = TestClient(app)


def test_realtime_events_history_and_from_sequence_filtering():
    """
    Validates that:
    1. Events emitted to central_event_bus are queryable via /api/events/history/{task_id}.
    2. Events are monotonic with sequence_id.
    3. Stream endpoint respects from_sequence_id filter to prevent duplicate replay.
    """
    task_id = "test-realtime-events-01"

    # Register task so API route allows access
    task_lifecycle.job_manager.register_task(
        task_id=task_id,
        goal="Build authentication module with live events",
        mode="autonomous",
    )

    async def _emit():
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TASK_CREATED,
            message="Autonomous task initialized",
            payload={"goal": "Build authentication", "mode": "autonomous"},
            source="api",
        )
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.PLAN_GENERATED,
            message="Execution plan finalized",
            payload={"steps": ["Edit auth.py", "Run pytest"]},
            source="planner",
        )
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TOOL_CALL_STARTED,
            message="Running pytest tests/test_auth.py",
            payload={"tool": "terminal", "arguments": {"command": "pytest tests/test_auth.py"}},
            source="runtime",
        )
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TOOL_CALL_COMPLETED,
            message="Completed pytest tests/test_auth.py: 1 passed in 0.05s",
            payload={"tool": "terminal", "result": "1 passed in 0.05s", "exit_code": 0},
            source="runtime",
        )
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TASK_COMPLETED,
            message="Task completed successfully",
            payload={"status": "completed"},
            source="lifecycle",
        )

    asyncio.run(_emit())

    # 1. Verify history endpoint
    res = client.get(f"/api/events/history/{task_id}")
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 5
    seq_ids = [e["sequence_id"] for e in events]
    assert seq_ids == sorted(seq_ids)
    assert events[0]["event_type"] == "TASK_CREATED"
    assert events[1]["event_type"] == "PLAN_GENERATED"
    assert events[2]["event_type"] == "TOOL_CALL_STARTED"
    assert events[3]["event_type"] == "TOOL_CALL_COMPLETED"
    assert events[4]["event_type"] == "TASK_COMPLETED"

    # 2. Verify from_sequence_id filter logic on stream endpoint
    async def _test_stream():
        mock_req = MagicMock()
        mock_req.is_disconnected = AsyncMock(return_value=False)
        sse_resp = await stream_task_events(task_id=task_id, request=mock_req, from_sequence_id=2)
        streamed = []
        async for chunk in sse_resp.body_iterator:
            streamed.append(chunk)
            if "TASK_COMPLETED" in str(chunk):
                break
        return streamed

    stream_chunks = asyncio.run(_test_stream())
    assert len(stream_chunks) > 0

    # Parse JSON payloads in stream chunks
    parsed_events = []
    for chunk in stream_chunks:
        chunk_str = str(chunk)
        for line in chunk_str.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                raw_json = line.replace("data:", "").strip()
                if raw_json and raw_json.startswith("{"):
                    try:
                        parsed_events.append(json.loads(raw_json))
                    except Exception:
                        pass
            elif line.startswith("{"):
                try:
                    parsed_events.append(json.loads(line))
                except Exception:
                    pass

    # Verify that all events streamed with from_sequence_id=2 have sequence_id > 2
    for ev in parsed_events:
        if ev.get("event_type") not in ("CONNECTED", None):
            assert ev["sequence_id"] > 2


def test_agent_runtime_openhands_event_listener_translation():
    """
    Verifies that AgentRuntime's create_openhands_listener translates OpenHands SDK
    Action and Observation events into canonical ASTRA events.
    """
    runtime = AgentRuntime()
    captured_events: list[dict] = []

    def emit_fn(event_type: str, message: str, payload: dict | None = None):
        captured_events.append({"event_type": event_type, "message": message, "payload": payload or {}})

    listener = runtime.create_openhands_listener(emit_fn=emit_fn)

    # 1. Simulate FileEditAction (edit file)
    mock_file_action = MagicMock()
    mock_file_action.__class__.__name__ = "FileEditAction"
    mock_file_action.args = {"path": "backend/app/auth.py", "command": "edit"}
    mock_file_action.thought = "Editing authentication module"

    listener(mock_file_action)

    assert len(captured_events) >= 1
    file_event = captured_events[-1]
    assert file_event["event_type"] == "TOOL_CALL_STARTED"
    assert "backend/app/auth.py" in file_event["message"]
    assert file_event["payload"].get("tool") == "file_editor"

    # 2. Simulate Terminal CmdOutputObservation (completed test)
    mock_terminal_obs = MagicMock()
    mock_terminal_obs.__class__.__name__ = "CmdOutputObservation"
    mock_terminal_obs.content = "=== 2 passed in 0.12s ==="

    listener(mock_terminal_obs)

    assert len(captured_events) >= 3  # TEST_COMPLETED + TOOL_CALL_COMPLETED
    event_types = [e["event_type"] for e in captured_events]
    assert "TEST_COMPLETED" in event_types
    assert "TOOL_CALL_COMPLETED" in event_types

    test_ev = next(e for e in captured_events if e["event_type"] == "TEST_COMPLETED")
    assert test_ev["payload"].get("passed") == 2
    assert test_ev["payload"].get("exit_code") == 0
