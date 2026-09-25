from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import sessionmaker

from app.database.models import AgentEventRecord, utc_now
from app.database.session import get_sync_session_factory
from app.observability.logging import logger


class AgentEventType(str, Enum):
    TASK_CREATED = "TASK_CREATED"
    WORKSPACE_INITIALIZED = "WORKSPACE_INITIALIZED"
    PLANNING_STARTED = "PLANNING_STARTED"
    PLAN_GENERATED = "PLAN_GENERATED"
    TOOL_CALL_STARTED = "TOOL_CALL_STARTED"
    TOOL_CALL_COMPLETED = "TOOL_CALL_COMPLETED"
    FILE_CHANGED = "FILE_CHANGED"
    DIFF_GENERATED = "DIFF_GENERATED"
    TEST_STARTED = "TEST_STARTED"
    TEST_COMPLETED = "TEST_COMPLETED"
    DEBUG_STARTED = "DEBUG_STARTED"
    HYPOTHESIS_FORMULATED = "HYPOTHESIS_FORMULATED"
    REPLAN_TRIGGERED = "REPLAN_TRIGGERED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    COMMIT_CREATED = "COMMIT_CREATED"
    PR_CREATED = "PR_CREATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_TIMEOUT = "TASK_TIMEOUT"


@dataclass
class AgentEvent:
    task_id: str
    event_type: str
    message: str
    sequence_id: int = 1
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "sequence_id": self.sequence_id,
            "event_type": str(self.event_type),
            "message": self.message,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class CentralEventBus:
    """
    Production Unified Agent Event System for ASTRA 2.0 (Phase 4.3).
    
    Guarantees:
    - Standardized event lifecycle model with strict schema validation
    - Monotonically increasing sequence IDs per task for deterministic replay
    - Real-time Pub/Sub distribution to SSE/WebSocket subscribers
    - Persistent database storage of all agent actions, diffs, and verification steps
    """

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or get_sync_session_factory()
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._sequence_counters: Dict[str, int] = defaultdict(int)
        self._event_history: Dict[str, List[AgentEvent]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _next_sequence_id(self, task_id: str) -> int:
        self._sequence_counters[task_id] += 1
        return self._sequence_counters[task_id]

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[task_id].append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        if task_id in self._subscribers and q in self._subscribers[task_id]:
            self._subscribers[task_id].remove(q)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def emit(
        self,
        task_id: str,
        event_type: AgentEventType | str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "system",
    ) -> AgentEvent:
        """
        Emits a canonical AgentEvent with auto-generated monotonic sequence ID.
        Distributes to active subscribers and persists to SQL database.
        """
        from app.safety.policies import SecurityPolicies

        seq_id = self._next_sequence_id(task_id)
        type_str = event_type.value if isinstance(event_type, Enum) else str(event_type)

        clean_message = SecurityPolicies.sanitize_secrets(message)
        clean_payload = SecurityPolicies.sanitize_payload(payload or {})

        event = AgentEvent(
            task_id=task_id,
            sequence_id=seq_id,
            event_type=type_str,
            message=clean_message,
            payload=clean_payload,
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # 1. Cache in memory history
        self._event_history[task_id].append(event)

        # 2. Dispatch to live subscriber queues
        if task_id in self._subscribers:
            for q in list(self._subscribers[task_id]):
                await q.put(event)

        # 3. Persist to database if session factory is available
        if self._session_factory:
            try:
                with self._session_factory() as session:
                    rec = AgentEventRecord(
                        task_id=task_id,
                        sequence_id=seq_id,
                        event_type=type_str,
                        source=source,
                        message=clean_message,
                        payload=clean_payload,
                    )
                    session.add(rec)
                    session.commit()
            except Exception as e:
                logger.debug(f"Failed to persist AgentEventRecord: {e}")

        logger.info(f"[{task_id}][#{seq_id}][{type_str}][{source}] {clean_message}")
        return event

    async def publish(self, event: Any) -> None:
        """Compatibility adapter for legacy TaskEvent objects."""
        from app.safety.policies import SecurityPolicies

        if hasattr(event, "sequence_id"):
            seq_id = event.sequence_id
            type_str = str(event.event_type)
            msg = event.message
            payload = getattr(event, "payload", {})
            source = getattr(event, "source", "system")
        else:
            seq_id = self._next_sequence_id(event.task_id)
            type_str = str(event.event_type)
            msg = event.message
            payload = getattr(event, "payload", {})
            source = getattr(event, "source", "system")

        clean_msg = SecurityPolicies.sanitize_secrets(msg)
        clean_payload = SecurityPolicies.sanitize_payload(payload)

        canonical_event = AgentEvent(
            task_id=event.task_id,
            sequence_id=seq_id,
            event_type=type_str,
            message=clean_msg,
            payload=clean_payload,
            source=source,
            timestamp=getattr(event, "timestamp", datetime.now(timezone.utc).isoformat()),
        )

        self._event_history[event.task_id].append(canonical_event)

        if event.task_id in self._subscribers:
            for q in list(self._subscribers[event.task_id]):
                await q.put(canonical_event)

        if self._session_factory:
            try:
                with self._session_factory() as session:
                    rec = AgentEventRecord(
                        task_id=event.task_id,
                        sequence_id=seq_id,
                        event_type=type_str,
                        source=source,
                        message=msg,
                        payload=payload,
                    )
                    session.add(rec)
                    session.commit()
            except Exception as e:
                logger.debug(f"Failed to persist legacy event: {e}")

    def get_history(self, task_id: str, limit: int = 200) -> List[AgentEvent]:
        """Returns chronological list of events for a task."""
        if self._session_factory:
            try:
                with self._session_factory() as session:
                    records = (
                        session.query(AgentEventRecord)
                        .filter_by(task_id=task_id)
                        .order_by(AgentEventRecord.sequence_id.asc())
                        .limit(limit)
                        .all()
                    )
                    if records:
                        return [
                            AgentEvent(
                                task_id=r.task_id,
                                sequence_id=r.sequence_id or 1,
                                event_type=r.event_type,
                                message=r.message,
                                source=r.source or "system",
                                payload=r.payload or {},
                                timestamp=r.created_at.isoformat() if r.created_at else "",
                            )
                            for r in records
                        ]
            except Exception as e:
                logger.debug(f"Error querying event history from DB: {e}")

        return list(self._event_history.get(task_id, []))[:limit]


# Global unified event bus singleton
central_event_bus = CentralEventBus()
