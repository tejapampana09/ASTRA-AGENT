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
from app.runtime.workspace import WorkspaceManager


@dataclass
class TaskEvent:
    task_id: str
    event_type: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "event_type": self.event_type,
            "message": self.message,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class EventBroker:
    """Pub/Sub broker for real-time task event streaming over SSE."""

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[task_id].append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        if task_id in self._subscribers and q in self._subscribers[task_id]:
            self._subscribers[task_id].remove(q)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def publish(self, event: TaskEvent) -> None:
        if event.task_id in self._subscribers:
            for q in list(self._subscribers[event.task_id]):
                await q.put(event)


event_broker = EventBroker()


class TaskLifecycleManager:
    """
    Orchestrates background task execution without blocking HTTP request threads.
    Integrates WorkspaceManager, EventBroker, and the LangGraph engine.
    """

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._async_tasks: Dict[str, asyncio.Task] = {}
        self.workspace_mgr = WorkspaceManager()

    def create_task(self, task_id: str, goal: str, repository_path: Optional[str] = None) -> Dict[str, Any]:
        task_info = {
            "task_id": task_id,
            "goal": goal,
            "status": "created",
            "verification_status": "pending",
            "repository_path": repository_path,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "final_report": None,
            "events": []
        }
        self._tasks[task_id] = task_info
        logger.info(f"Task created: {task_id}")
        return task_info

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return list(self._tasks.values())

    async def run_task_async(self, task_id: str) -> None:
        """Launches autonomous execution in the background."""
        task_info = self._tasks.get(task_id)
        if not task_info:
            raise KeyError(f"Task {task_id} not registered")

        task_info["status"] = "running"
        await event_broker.publish(TaskEvent(task_id=task_id, event_type="TASK_STARTED", message=f"Task {task_id} started."))

        # 1. Create isolated workspace
        ws = self.workspace_mgr.create_workspace(task_id=task_id, source_repo_path=task_info.get("repository_path"))
        task_info["workspace_path"] = str(ws.path)

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

        try:
            await event_broker.publish(TaskEvent(task_id=task_id, event_type="PLANNING", message="Initializing task planning."))

            config = {"configurable": {"thread_id": task_id}}
            result_state = await astra_graph.ainvoke(initial_state, config=config)

            # Check if execution was halted for human approval
            if result_state.get("verification_status") == "paused_for_approval":
                task_info["status"] = "paused_for_approval"
                await event_broker.publish(
                    TaskEvent(
                        task_id=task_id,
                        event_type="APPROVAL_REQUIRED",
                        message="Task execution paused: Human authorization required before execution."
                    )
                )
                return

            final_report = result_state.get("final_result", {})
            status = final_report.get("status", "UNCERTAIN")

            task_info["status"] = "completed" if status in ["VERIFIED", "verified"] else "failed"
            task_info["verification_status"] = status
            task_info["final_report"] = final_report

            event_type = "TASK_COMPLETED" if status in ["VERIFIED", "verified"] else "TASK_FAILED"
            await event_broker.publish(TaskEvent(task_id=task_id, event_type=event_type, message=f"Task finished with status: {status}", payload=final_report))

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
        if task_id in self._async_tasks:
            t = self._async_tasks[task_id]
            t.cancel()
            logger.info(f"Task cancelled: {task_id}")
            return True
        return False


# Global lifecycle manager singleton
task_lifecycle = TaskLifecycleManager()
