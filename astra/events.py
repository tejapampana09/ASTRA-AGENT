"""ASTRA V4 Event System and Agent States.

Structured, real-time event broadcasting consumed by Desktop UI, CLI, and WebSockets.
"""
from __future__ import annotations

import asyncio
import enum
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


class AgentState(str, enum.Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXPLORING = "EXPLORING"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    FIXING = "FIXING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    # V5 Cognitive Phases
    CONVERSATION = "CONVERSATION"
    UNDERSTAND = "UNDERSTAND"
    INVESTIGATE = "INVESTIGATE"
    DIAGNOSE = "DIAGNOSE"
    REPLAN = "REPLAN"
    RECOVER = "RECOVER"
    BLOCKED = "BLOCKED"
    DONE = "COMPLETED"


class ControllerPhase(str, enum.Enum):
    CONVERSATION = "CONVERSATION"
    UNDERSTAND = "UNDERSTAND"
    INVESTIGATE = "INVESTIGATE"
    DIAGNOSE = "DIAGNOSE"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    VERIFY = "VERIFY"
    REPLAN = "REPLAN"
    RECOVER = "RECOVER"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class EventType(str, enum.Enum):
    # V5 Structured Cognitive Events
    TASK_STARTED = "task_started"
    TASK_CLASSIFIED = "task_classified"
    PHASE_CHANGED = "phase_changed"
    INVESTIGATION_STARTED = "investigation_started"
    EVIDENCE_FOUND = "evidence_found"
    HYPOTHESIS_CREATED = "hypothesis_created"
    ACTION_PROPOSED = "action_proposed"
    ACTION_BLOCKED = "action_blocked"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    OBSERVATION_CREATED = "observation_created"
    DIAGNOSIS_CREATED = "diagnosis_created"
    REPLAN_STARTED = "replan_started"
    CHECKPOINT_CREATED = "checkpoint_created"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    TASK_COMPLETED = "task_completed"
    TASK_BLOCKED = "task_blocked"
    TASK_FAILED = "task_failed"

    # Backward Compatibility Aliases for V4
    AGENT_STARTED = "agent_started"
    PLANNING = "planning"
    EXPLORATION_STARTED = "exploration_started"
    FILE_CHANGED = "file_changed"
    COMMAND_STARTED = "command_started"
    COMMAND_OUTPUT = "command_output"
    FIX_STARTED = "fix_started"
    APPROVAL_REQUIRED = "approval_required"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_CANCELLED = "agent_cancelled"
    STATE_CHANGED = "state_changed"


@dataclass
class AgentEvent:
    event_type: str
    state: AgentState
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: str = "default"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type if isinstance(self.event_type, str) else self.event_type.value,
            "state": self.state if isinstance(self.state, str) else self.state.value,
            "data": self.data,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class EventBus:
    """Thread-safe and async-compatible event publisher."""

    def __init__(self):
        self._sync_subscribers: Set[Callable[[AgentEvent], None]] = set()
        self._async_subscribers: Set[Callable[[AgentEvent], Any]] = set()

    def subscribe(self, callback: Callable[[AgentEvent], None]) -> None:
        self._sync_subscribers.add(callback)

    def unsubscribe(self, callback: Callable[[AgentEvent], None]) -> None:
        self._sync_subscribers.discard(callback)

    def subscribe_async(self, callback: Callable[[AgentEvent], Any]) -> None:
        self._async_subscribers.add(callback)

    def unsubscribe_async(self, callback: Callable[[AgentEvent], Any]) -> None:
        self._async_subscribers.discard(callback)

    def emit(self, event: AgentEvent) -> None:
        """Emit event to all registered listeners."""
        # Sync listeners
        for cb in list(self._sync_subscribers):
            try:
                cb(event)
            except Exception:
                pass

        # Async listeners
        if self._async_subscribers:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    for acb in list(self._async_subscribers):
                        try:
                            res = acb(event)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                        except Exception:
                            pass
            except RuntimeError:
                pass

    publish = emit


# Global event bus instance
event_bus = EventBus()
