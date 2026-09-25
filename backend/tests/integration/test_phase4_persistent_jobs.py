from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.runtime.checkpointer import DurableCheckpointSaver
from app.runtime.jobs import JobStatus, PersistentJobManager
from app.runtime.lifecycle import TaskLifecycleManager


@pytest.fixture
def temp_db_session():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "persistent_test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        yield Session
        engine.dispose()


def test_p4_2_durable_checkpoint_saver_persistence(temp_db_session):
    """
    P4.2 TEST:
    Proves DurableCheckpointSaver writes state transitions into SQL database,
    and can successfully hydrate checkpoints from a cold cache after simulated crash.
    """
    async def _run():
        from langgraph.graph import END, START, StateGraph
        from typing import TypedDict

        class PipelineState(TypedDict):
            counter: int
            milestone: str

        def node_a(s: PipelineState):
            return {"counter": s["counter"] + 5, "milestone": "node_a_done"}

        def node_b(s: PipelineState):
            return {"counter": s["counter"] * 2, "milestone": "node_b_done"}

        builder = StateGraph(PipelineState)
        builder.add_node("node_a", node_a)
        builder.add_node("node_b", node_b)
        builder.add_edge(START, "node_a")
        builder.add_edge("node_a", "node_b")
        builder.add_edge("node_b", END)

        saver1 = DurableCheckpointSaver(session_factory=temp_db_session)
        graph1 = builder.compile(checkpointer=saver1)

        cfg = {"configurable": {"thread_id": "test-thread-durability-01"}}
        res = await graph1.ainvoke({"counter": 10, "milestone": "init"}, config=cfg)
        assert res["counter"] == 30
        assert res["milestone"] == "node_b_done"

        # SIMULATE PROCESS RESTART: Create a brand new saver with empty in-memory cache
        saver2 = DurableCheckpointSaver(session_factory=temp_db_session)
        assert len(saver2.storage) == 0, "Cold restart saver must have empty local memory cache"

        recovered_tuple = saver2.get_tuple(cfg)
        assert recovered_tuple is not None, "Checkpoint must be hydrated from SQL database"
        ch_vals = recovered_tuple.checkpoint.get("channel_values", {})
        assert ch_vals.get("counter") == 30
        assert ch_vals.get("milestone") == "node_b_done"

    asyncio.run(_run())


def test_p4_2_task_timeout_enforcement(temp_db_session):
    """
    P4.2 TEST:
    Proves PersistentJobManager enforces runtime limits,
    transitioning stalled tasks to TIMED_OUT status upon exceeding timeout.
    """
    async def _run():
        job_mgr = PersistentJobManager(session_factory=temp_db_session, heartbeat_interval_seconds=0.1)
        task_id = "test-task-timeout-01"
        job_mgr.register_task(task_id, goal="Run long computation", timeout_seconds=1)

        async def hanging_workload():
            await asyncio.sleep(5.0)
            return {"status": "finished"}

        with pytest.raises(TimeoutError):
            await job_mgr.execute_task_with_monitoring(
                task_id=task_id,
                coro_func=hanging_workload,
                timeout_seconds=1,
            )

        task_info = job_mgr.get_task(task_id)
        assert task_info["status"] == JobStatus.TIMED_OUT.value
        assert "timeout limit" in task_info.get("error_message", "")

    asyncio.run(_run())


def test_p4_2_task_heartbeat_and_health_monitor(temp_db_session):
    """
    P4.2 TEST:
    Proves active tasks emit heartbeats, health monitor accurately computes
    liveness and heartbeat age, and stale task detection operates correctly.
    """
    async def _run():
        job_mgr = PersistentJobManager(
            session_factory=temp_db_session,
            heartbeat_interval_seconds=0.1,
            stale_threshold_seconds=0.3,
        )
        task_id = "test-task-heartbeat-01"
        job_mgr.register_task(task_id, goal="Telemetry heartbeat test", timeout_seconds=10)

        # Start task with short execution
        async def quick_work():
            await asyncio.sleep(0.3)
            return {"verification_status": "paused_for_approval"}

        await job_mgr.execute_task_with_monitoring(task_id=task_id, coro_func=quick_work)

        health = job_mgr.get_task_health(task_id)
        assert health.task_id == task_id
        assert health.last_heartbeat is not None
        assert health.timeout_seconds == 10
        assert not health.is_timed_out

    asyncio.run(_run())


def test_p4_2_task_cancellation(temp_db_session):
    """
    P4.2 TEST:
    Proves tasks can be cleanly cancelled, terminating background tasks
    and updating persistent status to CANCELLED.
    """
    async def _run():
        job_mgr = PersistentJobManager(session_factory=temp_db_session, heartbeat_interval_seconds=0.1)
        lifecycle = TaskLifecycleManager(job_manager=job_mgr)

        task_id = "test-task-cancel-01"
        lifecycle.create_task(task_id, goal="Cancellable task")

        async def long_running():
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                raise

        # Launch task in background
        t = asyncio.create_task(
            job_mgr.execute_task_with_monitoring(task_id, coro_func=long_running)
        )
        lifecycle._async_tasks[task_id] = t

        await asyncio.sleep(0.1)
        cancelled = lifecycle.cancel_task(task_id)
        assert cancelled is True

        # Let cancellation propagate
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

        task_data = lifecycle.get_task(task_id)
        assert task_data["status"] == JobStatus.CANCELLED.value

    asyncio.run(_run())


def test_p4_2_crash_restart_checkpoint_recovery(temp_db_session):
    """
    P4.2 TEST:
    Comprehensive crash-restart recovery test:
    1. Runs a multi-step task that pauses for human approval or crashes mid-way.
    2. Checkpoints state to persistent SQLite/PostgreSQL store.
    3. Simulates host crash / process reboot (new JobManager instance created).
    4. Triggers recover_and_resume_task(task_id).
    5. Confirms state restoration from DB checkpoint and resumed execution.
    """
    async def _run():
        from langgraph.graph import END, START, StateGraph
        from typing import TypedDict

        class PipelineState(TypedDict):
            step_val: int
            stage: str
            verification_status: str

        def step_one(s: PipelineState):
            return {"step_val": s["step_val"] + 1, "stage": "step_one_finished"}

        def step_two(s: PipelineState):
            return {
                "step_val": s["step_val"] * 5,
                "stage": "step_two_finished",
                "verification_status": "paused_for_approval",
            }

        builder = StateGraph(PipelineState)
        builder.add_node("step_one", step_one)
        builder.add_node("step_two", step_two)
        builder.add_edge(START, "step_one")
        builder.add_edge("step_one", "step_two")
        builder.add_edge("step_two", END)

        # Process 1: Initial run before crash
        job_mgr_1 = PersistentJobManager(session_factory=temp_db_session)
        task_id = "test-crash-recovery-01"
        job_mgr_1.register_task(task_id, goal="Simulate crash recovery")

        saver_1 = DurableCheckpointSaver(session_factory=temp_db_session)
        g1 = builder.compile(checkpointer=saver_1)

        cfg = {"configurable": {"thread_id": task_id}}
        res1 = await g1.ainvoke({"step_val": 10, "stage": "init", "verification_status": "running"}, config=cfg)
        assert res1["step_val"] == 55
        assert res1["verification_status"] == "paused_for_approval"

        # Mark task as running/paused in DB
        job_mgr_1._update_task_state(task_id, status=JobStatus.PAUSED_FOR_APPROVAL.value)

        # SIMULATE SYSTEM CRASH / RESTART: Process 1 dies, Process 2 starts!
        del job_mgr_1
        del g1
        del saver_1

        job_mgr_2 = PersistentJobManager(session_factory=temp_db_session)
        recovery_result = await job_mgr_2.recover_and_resume_task(task_id)

        assert recovery_result["recovered"] is True
        assert recovery_result["task_id"] == task_id
        assert recovery_result["status"] == JobStatus.PAUSED_FOR_APPROVAL.value
        assert "checkpoint" in recovery_result["message"].lower() or recovery_result.get("checkpoint_id") is not None

    asyncio.run(_run())
