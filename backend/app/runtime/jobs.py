from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

from sqlalchemy.orm import sessionmaker

from app.agents.graph import astra_graph, build_astra_graph
from app.agents.state import AstraAgentState
from app.config import settings
from app.database.models import TaskRecord, utc_now
from app.database.session import get_sync_session_factory
from app.observability.logging import logger
from app.runtime.checkpointer import get_durable_checkpointer
from app.runtime.workspace import WorkspaceManager


class JobStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED_FOR_APPROVAL = "paused_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    STALE = "stale"


@dataclass
class JobHealthInfo:
    task_id: str
    status: str
    is_alive: bool
    last_heartbeat: Optional[str]
    heartbeat_age_seconds: Optional[float]
    started_at: Optional[str]
    elapsed_seconds: Optional[float]
    timeout_seconds: int
    is_timed_out: bool
    has_checkpoint: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PersistentJobManager:
    """
    Production-grade persistent job manager for ASTRA 2.0 (Phase 4.2).
    
    Provides:
    - Persistent task registration and lifecycle management (PostgreSQL / SQLite)
    - Enforced task execution timeouts (MAX_RUNTIME_SECONDS)
    - Real-time periodic heartbeat tracking and health monitoring
    - Stale / crashed task detection
    - Crash-restart checkpoint recovery:
      DB state restore -> LangGraph checkpoint reload -> autonomous resumption
    - Clean task cancellation
    """

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        heartbeat_interval_seconds: float = 3.0,
        stale_threshold_seconds: float = 30.0,
    ):
        self._session_factory = session_factory or get_sync_session_factory()
        self._heartbeat_interval = heartbeat_interval_seconds
        self._stale_threshold = stale_threshold_seconds

        # In-memory execution registry
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._heartbeat_jobs: Dict[str, asyncio.Task] = {}
        self.workspace_mgr = WorkspaceManager()
        self.checkpointer = get_durable_checkpointer(self._session_factory)

    def register_task(
        self,
        task_id: str,
        goal: str,
        repository_path: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        workspace_path: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[str] = "autonomous",
    ) -> Dict[str, Any]:
        """Registers a new task in memory and the persistent database."""
        effective_timeout = timeout_seconds or settings.MAX_RUNTIME_SECONDS
        now_iso = datetime.now(timezone.utc).isoformat()

        task_data = {
            "task_id": task_id,
            "goal": goal,
            "repository_path": repository_path,
            "model": model,
            "mode": mode or "autonomous",
            "status": JobStatus.CREATED.value,
            "verification_status": "pending",
            "workspace_path": workspace_path,
            "timeout_seconds": effective_timeout,
            "heartbeat_at": None,
            "started_at": None,
            "completed_at": None,
            "created_at": now_iso,
            "final_report": None,
            "error_message": None,
        }
        self._tasks[task_id] = task_data

        if self._session_factory:
            try:
                with self._session_factory() as session:
                    rec = TaskRecord(
                        id=task_id,
                        goal=goal,
                        status=JobStatus.CREATED.value,
                        verification_status="pending",
                        workspace_path=workspace_path,
                        timeout_seconds=effective_timeout,
                    )
                    session.merge(rec)
                    session.commit()
            except Exception as e:
                logger.warning(f"Failed to persist TaskRecord to database: {e}")

        logger.info(f"[{task_id}] Registered persistent task with {effective_timeout}s timeout.")
        return task_data

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves task info from active registry or falls back to database."""
        if task_id in self._tasks:
            return self._tasks[task_id]

        if self._session_factory:
            try:
                with self._session_factory() as session:
                    rec = session.query(TaskRecord).filter_by(id=task_id).first()
                    if rec:
                        task_data = {
                            "task_id": rec.id,
                            "goal": rec.goal,
                            "status": rec.status,
                            "verification_status": rec.verification_status,
                            "workspace_path": rec.workspace_path,
                            "timeout_seconds": rec.timeout_seconds or settings.MAX_RUNTIME_SECONDS,
                            "heartbeat_at": rec.heartbeat_at.isoformat() if rec.heartbeat_at else None,
                            "started_at": rec.started_at.isoformat() if rec.started_at else None,
                            "completed_at": rec.completed_at.isoformat() if rec.completed_at else None,
                            "created_at": rec.created_at.isoformat() if rec.created_at else None,
                            "final_report": rec.final_report,
                            "error_message": rec.error_message,
                        }
                        self._tasks[task_id] = task_data
                        return task_data
            except Exception as e:
                logger.warning(f"Error fetching task {task_id} from database: {e}")
        return None

    def _update_task_state(self, task_id: str, **updates: Any) -> None:
        """Helper to sync task state across memory and database."""
        task_data = self._tasks.get(task_id)
        if task_data:
            task_data.update(updates)

        if self._session_factory:
            try:
                with self._session_factory() as session:
                    rec = session.query(TaskRecord).filter_by(id=task_id).first()
                    if rec:
                        for k, v in updates.items():
                            if hasattr(rec, k):
                                setattr(rec, k, v)
                        session.commit()
            except Exception as e:
                logger.debug(f"Failed to update task record in DB: {e}")

    async def _heartbeat_worker(self, task_id: str) -> None:
        """Periodic heartbeat loop that updates task timestamp."""
        try:
            while True:
                now_dt = datetime.now(timezone.utc)
                self._update_task_state(task_id, heartbeat_at=now_dt)
                await asyncio.sleep(self._heartbeat_interval)
        except asyncio.CancelledError:
            pass

    def start_heartbeat(self, task_id: str) -> None:
        """Spawns an active heartbeat worker for task."""
        self.stop_heartbeat(task_id)
        coro = self._heartbeat_worker(task_id)
        self._heartbeat_jobs[task_id] = asyncio.create_task(coro)

    def stop_heartbeat(self, task_id: str) -> None:
        """Halts active heartbeat worker for task."""
        if task_id in self._heartbeat_jobs:
            self._heartbeat_jobs[task_id].cancel()
            del self._heartbeat_jobs[task_id]

    async def execute_task_with_monitoring(
        self,
        task_id: str,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
        timeout_seconds: Optional[int] = None,
    ) -> Any:
        """
        Executes a task coroutine with automated timeout protection and heartbeat monitoring.
        """
        task_data = self.get_task(task_id)
        if not task_data:
            raise KeyError(f"Task {task_id} not registered")

        effective_timeout = timeout_seconds or task_data.get("timeout_seconds") or settings.MAX_RUNTIME_SECONDS
        now_dt = datetime.now(timezone.utc)
        self._update_task_state(
            task_id,
            status=JobStatus.RUNNING.value,
            started_at=now_dt,
            heartbeat_at=now_dt,
        )

        self.start_heartbeat(task_id)

        try:
            logger.info(f"[{task_id}] Executing task with {effective_timeout}s timeout limit.")
            result = await asyncio.wait_for(coro_func(), timeout=effective_timeout)

            # Check if paused for human approval
            if isinstance(result, dict) and result.get("verification_status") == "paused_for_approval":
                self.stop_heartbeat(task_id)
                self._update_task_state(task_id, status=JobStatus.PAUSED_FOR_APPROVAL.value)
                return result

            final_report = result.get("final_result", {}) if isinstance(result, dict) else {}
            v_status = final_report.get("status", "UNCERTAIN")
            is_success = str(v_status).lower() in ["verified", "partially_verified"]
            final_job_status = JobStatus.COMPLETED.value if is_success else JobStatus.FAILED.value

            self.stop_heartbeat(task_id)
            self._update_task_state(
                task_id,
                status=final_job_status,
                verification_status=str(v_status),
                completed_at=datetime.now(timezone.utc),
                final_report=final_report,
            )
            return result

        except asyncio.TimeoutError:
            self.stop_heartbeat(task_id)
            err_msg = f"Task execution exceeded timeout limit of {effective_timeout} seconds."
            logger.error(f"[{task_id}] {err_msg}")
            self._update_task_state(
                task_id,
                status=JobStatus.TIMED_OUT.value,
                verification_status="timed_out",
                completed_at=datetime.now(timezone.utc),
                error_message=err_msg,
            )
            raise TimeoutError(err_msg)

        except asyncio.CancelledError:
            self.stop_heartbeat(task_id)
            logger.warning(f"[{task_id}] Task execution cancelled.")
            self._update_task_state(
                task_id,
                status=JobStatus.CANCELLED.value,
                completed_at=datetime.now(timezone.utc),
                error_message="Task cancelled by user or operator.",
            )
            raise

        except Exception as e:
            self.stop_heartbeat(task_id)
            logger.error(f"[{task_id}] Execution error: {e}", exc_info=True)
            self._update_task_state(
                task_id,
                status=JobStatus.FAILED.value,
                completed_at=datetime.now(timezone.utc),
                error_message=str(e),
            )
            raise

    def cancel_task(self, task_id: str) -> bool:
        """Cancels a running job and halts its heartbeat."""
        self.stop_heartbeat(task_id)
        job = self._running_jobs.get(task_id)
        if job and not job.done():
            job.cancel()
            self._update_task_state(
                task_id,
                status=JobStatus.CANCELLED.value,
                completed_at=datetime.now(timezone.utc),
                error_message="Task cancelled by operator.",
            )
            logger.info(f"[{task_id}] Cancelled active execution job.")
            return True

        task_data = self.get_task(task_id)
        if task_data and task_data.get("status") in [JobStatus.RUNNING.value, JobStatus.QUEUED.value]:
            self._update_task_state(
                task_id,
                status=JobStatus.CANCELLED.value,
                completed_at=datetime.now(timezone.utc),
                error_message="Task cancelled by operator.",
            )
            return True
        return False

    def get_task_health(self, task_id: str) -> JobHealthInfo:
        """Computes live telemetry and heartbeat age for a task."""
        task_data = self.get_task(task_id) or {}
        status = task_data.get("status", "unknown")
        timeout_seconds = task_data.get("timeout_seconds", settings.MAX_RUNTIME_SECONDS)

        heartbeat_at = task_data.get("heartbeat_at")
        heartbeat_age: Optional[float] = None
        if heartbeat_at:
            if isinstance(heartbeat_at, str):
                hb_dt = datetime.fromisoformat(heartbeat_at)
            else:
                hb_dt = heartbeat_at
            if hb_dt.tzinfo is None:
                hb_dt = hb_dt.replace(tzinfo=timezone.utc)
            heartbeat_age = (datetime.now(timezone.utc) - hb_dt).total_seconds()

        started_at = task_data.get("started_at")
        elapsed: Optional[float] = None
        is_timed_out = False
        if started_at:
            if isinstance(started_at, str):
                st_dt = datetime.fromisoformat(started_at)
            else:
                st_dt = started_at
            if st_dt.tzinfo is None:
                st_dt = st_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - st_dt).total_seconds()
            if elapsed > timeout_seconds and status == JobStatus.RUNNING.value:
                is_timed_out = True

        active_job = self._running_jobs.get(task_id)
        is_alive = bool(active_job and not active_job.done())

        # Check if durable checkpoint exists in checkpointer
        tuple_info = self.checkpointer.get_tuple({"configurable": {"thread_id": task_id}})
        has_checkpoint = tuple_info is not None

        return JobHealthInfo(
            task_id=task_id,
            status=status,
            is_alive=is_alive,
            last_heartbeat=str(heartbeat_at) if heartbeat_at else None,
            heartbeat_age_seconds=round(heartbeat_age, 2) if heartbeat_age is not None else None,
            started_at=str(started_at) if started_at else None,
            elapsed_seconds=round(elapsed, 2) if elapsed is not None else None,
            timeout_seconds=timeout_seconds,
            is_timed_out=is_timed_out,
            has_checkpoint=has_checkpoint,
        )

    def check_all_tasks_health(self) -> List[JobHealthInfo]:
        """Audits all registered tasks and flags stale or orphaned executions."""
        task_ids = set(self._tasks.keys())
        if self._session_factory:
            try:
                with self._session_factory() as session:
                    for rec in session.query(TaskRecord.id).all():
                        task_ids.add(rec[0])
            except Exception as e:
                logger.warning(f"Error querying task IDs for health check: {e}")

        results: List[JobHealthInfo] = []
        for tid in task_ids:
            h = self.get_task_health(tid)
            # Detect stale running task whose process died
            if h.status == JobStatus.RUNNING.value and not h.is_alive:
                if h.heartbeat_age_seconds is not None and h.heartbeat_age_seconds > self._stale_threshold:
                    self._update_task_state(
                        tid,
                        status=JobStatus.STALE.value,
                        error_message="Process died or heartbeat stopped. Task marked STALE for recovery.",
                    )
                    h.status = JobStatus.STALE.value
            results.append(h)
        return results

    async def recover_and_resume_task(self, task_id: str) -> Dict[str, Any]:
        """
        CRASH-RESTART CHECKPOINT RECOVERY (P4.2):
        
        1. Loads task from DB / persistent store.
        2. Retrieves latest durable LangGraph checkpoint tuple.
        3. If task is paused for approval, preserves paused state.
        4. If task was interrupted / crashed, restores workspace and executes
           LangGraph with `ainvoke(None, config={"configurable": {"thread_id": task_id}})`.
        """
        task_data = self.get_task(task_id)
        if not task_data:
            raise KeyError(f"Task {task_id} not found in database or memory.")

        current_status = task_data.get("status")
        valid_recovery_statuses = [
            JobStatus.RUNNING.value,
            JobStatus.STALE.value,
            JobStatus.PAUSED_FOR_APPROVAL.value,
            "paused_for_approval",
        ]
        if current_status not in valid_recovery_statuses:
            return {
                "task_id": task_id,
                "recovered": False,
                "status": current_status,
                "message": f"Task in status '{current_status}' is not eligible for crash recovery.",
            }

        cfg = {"configurable": {"thread_id": task_id}}
        cp_tuple = self.checkpointer.get_tuple(cfg)
        if not cp_tuple:
            return {
                "task_id": task_id,
                "recovered": False,
                "status": current_status,
                "message": f"No durable checkpoint found for thread '{task_id}'. Cannot restore state.",
            }

        channel_values = cp_tuple.checkpoint.get("channel_values", {})
        saved_status = channel_values.get("verification_status")

        if saved_status == "paused_for_approval" or current_status in [JobStatus.PAUSED_FOR_APPROVAL.value, "paused_for_approval"]:
            logger.info(f"[{task_id}] Checkpoint recovered in paused_for_approval state.")
            return {
                "task_id": task_id,
                "recovered": True,
                "status": JobStatus.PAUSED_FOR_APPROVAL.value,
                "message": "Task successfully recovered from checkpoint. Awaiting human approval to resume.",
                "checkpoint_id": cp_tuple.checkpoint.get("id"),
            }

        # Resuming execution from checkpoint
        logger.info(f"[{task_id}] Recovering execution from durable checkpoint id={cp_tuple.checkpoint.get('id')}")

        async def resume_coro():
            graph_instance = build_astra_graph(checkpointer=self.checkpointer)
            return await graph_instance.ainvoke(None, config=cfg)

        # Dispatch monitored execution
        job_task = asyncio.create_task(
            self.execute_task_with_monitoring(
                task_id=task_id,
                coro_func=resume_coro,
                timeout_seconds=task_data.get("timeout_seconds"),
            )
        )
        self._running_jobs[task_id] = job_task

        return {
            "task_id": task_id,
            "recovered": True,
            "status": JobStatus.RUNNING.value,
            "message": "Crash recovery successful: Task state restored from checkpoint and resumed in background.",
            "checkpoint_id": cp_tuple.checkpoint.get("id"),
        }


# Global PersistentJobManager instance
persistent_job_manager = PersistentJobManager()
