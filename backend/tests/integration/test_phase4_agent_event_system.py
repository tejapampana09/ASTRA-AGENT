from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.runtime.events import AgentEvent, AgentEventType, CentralEventBus
from app.runtime.jobs import PersistentJobManager
from app.runtime.lifecycle import TaskLifecycleManager


@pytest.fixture
def temp_db_session():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "events_test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        yield Session
        engine.dispose()


def test_p4_3_canonical_event_structure_and_sequence(temp_db_session):
    """
    P4.3 TEST:
    Proves CentralEventBus generates canonical AgentEvents with monotonic sequence_ids,
    rich metadata, valid event_types, and structured payloads.
    """
    async def _run():
        bus = CentralEventBus(session_factory=temp_db_session)
        task_id = "test-task-events-01"

        e1 = await bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TASK_CREATED,
            message="Task initialized",
            payload={"goal": "Refactor auth"},
            source="api",
        )
        assert e1.sequence_id == 1
        assert e1.event_type == "TASK_CREATED"
        assert e1.source == "api"
        assert e1.payload == {"goal": "Refactor auth"}
        assert e1.timestamp is not None

        e2 = await bus.emit(
            task_id=task_id,
            event_type=AgentEventType.PLANNING_STARTED,
            message="Generating execution plan",
            source="planner",
        )
        assert e2.sequence_id == 2
        assert e2.event_type == "PLANNING_STARTED"
        assert e2.source == "planner"

        e3 = await bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TOOL_CALL_STARTED,
            message="Invoking file_editor tool",
            payload={"tool": "file_editor", "target": "auth.py"},
            source="executor",
        )
        assert e3.sequence_id == 3
        assert e3.event_type == "TOOL_CALL_STARTED"

    asyncio.run(_run())


def test_p4_3_event_persistence_and_history(temp_db_session):
    """
    P4.3 TEST:
    Proves emitted events are durably persisted to SQL database and
    can be queried chronologically via get_history().
    """
    async def _run():
        bus = CentralEventBus(session_factory=temp_db_session)
        task_id = "test-task-history-01"

        events_to_emit = [
            (AgentEventType.WORKSPACE_INITIALIZED, "Workspace created", "workspace"),
            (AgentEventType.PLAN_GENERATED, "Plan with 3 steps", "planner"),
            (AgentEventType.DIFF_GENERATED, "Git diff +25 -5", "git"),
            (AgentEventType.TEST_COMPLETED, "Tests passed: 5/5", "verifier"),
            (AgentEventType.TASK_COMPLETED, "Autonomous execution verified", "orchestrator"),
        ]

        for et, msg, src in events_to_emit:
            await bus.emit(task_id, event_type=et, message=msg, source=src)

        # Retrieve history from DB
        history = bus.get_history(task_id)
        assert len(history) == 5

        # Verify sequence and content integrity
        for idx, (expected_et, expected_msg, expected_src) in enumerate(events_to_emit, 1):
            item = history[idx - 1]
            assert item.sequence_id == idx
            assert item.event_type == expected_et.value
            assert item.message == expected_msg
            assert item.source == expected_src

    asyncio.run(_run())


def test_p4_3_event_bus_pub_sub_streaming():
    """
    P4.3 TEST:
    Proves CentralEventBus distributes events in real-time to active subscribers.
    """
    async def _run():
        bus = CentralEventBus()
        task_id = "test-task-pubsub-01"

        queue1 = bus.subscribe(task_id)
        queue2 = bus.subscribe(task_id)

        emitted = await bus.emit(
            task_id=task_id,
            event_type=AgentEventType.FILE_CHANGED,
            message="Modified settings.py",
            payload={"file": "settings.py", "lines_added": 4},
            source="executor",
        )

        # Both subscribers receive identical event
        ev1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        ev2 = await asyncio.wait_for(queue2.get(), timeout=1.0)

        assert ev1.task_id == task_id
        assert ev1.event_type == "FILE_CHANGED"
        assert ev1.payload["lines_added"] == 4
        assert ev2.sequence_id == ev1.sequence_id == 1

        bus.unsubscribe(task_id, queue1)
        bus.unsubscribe(task_id, queue2)

    asyncio.run(_run())
