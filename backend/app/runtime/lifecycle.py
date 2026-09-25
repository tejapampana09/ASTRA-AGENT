from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from app.agents.graph import astra_graph
from app.agents.state import AstraAgentState
from app.config import settings
from app.observability.logging import logger
from app.runtime.jobs import JobStatus, PersistentJobManager, persistent_job_manager
from app.runtime.workspace import WorkspaceManager


from app.runtime.events import AgentEvent, AgentEventType, CentralEventBus, central_event_bus

TaskEvent = AgentEvent
event_broker = central_event_bus


class TaskLifecycleManager:
    """
    Orchestrates persistent background task execution without blocking HTTP request threads.
    Integrates WorkspaceManager, EventBroker, PersistentJobManager, and the LangGraph engine.
    """

    def __init__(self, job_manager: Optional[PersistentJobManager] = None):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._async_tasks: Dict[str, asyncio.Task] = {}
        self.workspace_mgr = WorkspaceManager()
        self.job_manager = job_manager or persistent_job_manager

    def create_task(
        self,
        task_id: str,
        goal: str,
        repository_path: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        task_info = self.job_manager.register_task(
            task_id=task_id,
            goal=goal,
            repository_path=repository_path,
            timeout_seconds=timeout_seconds,
        )
        self._tasks[task_id] = task_info
        logger.info(f"Task created and registered in job manager: {task_id}")
        return task_info

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        in_mem = self._tasks.get(task_id)
        if in_mem:
            return in_mem
        return self.job_manager.get_task(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return list(self._tasks.values())

    def get_task_health(self, task_id: str) -> Dict[str, Any]:
        return self.job_manager.get_task_health(task_id).to_dict()

    async def recover_and_resume_task(self, task_id: str) -> Dict[str, Any]:
        return await self.job_manager.recover_and_resume_task(task_id)

    async def run_task_async(self, task_id: str) -> None:
        """Launches autonomous execution with heartbeat monitoring and timeout protection."""
        task_info = self.get_task(task_id)
        if not task_info:
            raise KeyError(f"Task {task_id} not registered")

        await event_broker.publish(TaskEvent(task_id=task_id, event_type="TASK_STARTED", message=f"Task {task_id} started."))

        # 1. Create isolated workspace
        ws = self.workspace_mgr.create_workspace(task_id=task_id, source_repo_path=task_info.get("repository_path"))
        task_info["workspace_path"] = str(ws.path)
        self.job_manager._update_task_state(task_id, workspace_path=str(ws.path))

        # 2. Prepare initial state
        initial_state: AstraAgentState = {
            "task_id": task_id,
            "repository_id": task_id,
            "user_goal": task_info["goal"],
            "workspace_path": str(ws.path),
            "iteration_count": 0,
            "retry_count": 0,
            "plan": [],
            "messages": [],
            "observations": [],
            "tool_calls": [],
            "tool_results": [],
            "files_changed": [],
            "errors": [],
            "verification_status": "pending",
            "approval_required": False,
            "approval_status": "not_requested",
        }

        async def _execution_routine():
            await event_broker.publish(TaskEvent(task_id=task_id, event_type="PLANNING", message="Initializing task planning."))
            config = {"configurable": {"thread_id": task_id}}
            return await astra_graph.ainvoke(initial_state, config=config)

        try:
            result_state = await self.job_manager.execute_task_with_monitoring(
                task_id=task_id,
                coro_func=_execution_routine,
                timeout_seconds=task_info.get("timeout_seconds"),
            )

            # Check if paused for human approval
            if isinstance(result_state, dict) and result_state.get("verification_status") == "paused_for_approval":
                task_info["status"] = "paused_for_approval"
                await event_broker.publish(
                    TaskEvent(
                        task_id=task_id,
                        event_type="APPROVAL_REQUIRED",
                        message="Task execution paused: Human authorization required before execution."
                    )
                )
                return

            final_report = result_state.get("final_result", {}) if isinstance(result_state, dict) else {}
            status = final_report.get("status", "UNCERTAIN")

            task_info["status"] = "completed" if status in ["VERIFIED", "verified", "partially_verified"] else "failed"
            task_info["verification_status"] = status
            task_info["final_report"] = final_report

            event_type = "TASK_COMPLETED" if status in ["VERIFIED", "verified", "partially_verified"] else "TASK_FAILED"
            await event_broker.publish(TaskEvent(task_id=task_id, event_type=event_type, message=f"Task finished with status: {status}", payload=final_report))

        except TimeoutError as te:
            task_info["status"] = "timed_out"
            task_info["verification_status"] = "timed_out"
            await event_broker.publish(TaskEvent(task_id=task_id, event_type="TASK_TIMEOUT", message=str(te)))
        except asyncio.CancelledError:
            task_info["status"] = "cancelled"
            await event_broker.publish(TaskEvent(task_id=task_id, event_type="TASK_CANCELLED", message="Task execution cancelled by user."))
        except Exception as e:
            logger.error(f"Task {task_id} execution error: {e}", exc_info=True)
            task_info["status"] = "failed"
            task_info["error"] = str(e)
            await event_broker.publish(TaskEvent(task_id=task_id, event_type="ERROR", message=str(e), payload={"error": str(e)}))



    async def resume_task_after_approval(self, task_id: str, approved: bool) -> None:
        """Resumes a paused LangGraph execution once an approval decision is reached."""
        task_info = self._tasks.get(task_id)
        if not task_info:
            return

        config = {"configurable": {"thread_id": task_id}}

        if not approved:
            task_info["status"] = "rejected"
            await event_broker.publish(TaskEvent(task_id=task_id, event_type="TASK_FAILED", message="Operation rejected by reviewer."))
            return

        task_info["status"] = "running"
        await event_broker.publish(TaskEvent(task_id=task_id, event_type="APPROVAL_GRANTED", message="Operation authorized. Resuming execution."))

        try:
            resume_update: AstraAgentState = {
                "approval_status": "approved",
                "approval_required": False
            }
            result_state = await astra_graph.ainvoke(resume_update, config=config)

            final_report = result_state.get("final_result", {})
            status = final_report.get("status", "UNCERTAIN")

            task_info["status"] = "completed" if status in ["VERIFIED", "verified"] else "failed"
            task_info["verification_status"] = status
            task_info["final_report"] = final_report

            event_type = "TASK_COMPLETED" if status in ["VERIFIED", "verified"] else "TASK_FAILED"
            await event_broker.publish(TaskEvent(task_id=task_id, event_type=event_type, message=f"Task finished with status: {status}", payload=final_report))
        except Exception as e:
            logger.error(f"Error resuming task {task_id}: {e}", exc_info=True)
            task_info["status"] = "failed"
            await event_broker.publish(TaskEvent(task_id=task_id, event_type="ERROR", message=str(e)))

    def dispatch_task(self, task_id: str) -> None:
        """Schedules background execution without blocking caller."""
        coro = self.run_task_async(task_id)
        task = asyncio.create_task(coro)
        self._async_tasks[task_id] = task

    def cancel_task(self, task_id: str) -> bool:
        cancelled = self.job_manager.cancel_task(task_id)
        if task_id in self._async_tasks:
            t = self._async_tasks[task_id]
            if not t.done():
                t.cancel()
            cancelled = True
        if cancelled:
            logger.info(f"Task cancelled: {task_id}")
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    event_broker.publish(TaskEvent(task_id=task_id, event_type="TASK_CANCELLED", message="Task cancelled."))
                )
            except RuntimeError:
                pass
        return cancelled


# Global lifecycle manager singleton
task_lifecycle = TaskLifecycleManager()
