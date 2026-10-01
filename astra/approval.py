"""ASTRA V4 Approval Pipeline and Security Interceptor.

Thread-safe, session-aware approval manager with unique IDs, configurable timeouts,
and non-blocking event synchronization for dangerous workspace actions.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from astra.events import AgentEvent, AgentState, EventType, event_bus


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class ApprovalRequest:
    approval_id: str
    session_id: str
    tool_name: str
    arguments: Dict[str, Any]
    description: str
    command: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 120.0
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision: Optional[bool] = None
    _event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "command": self.command,
            "arguments": self.arguments,
            "description": self.description,
            "created_at": self.created_at,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "decision": self.decision,
        }


class ApprovalManager:
    """Centralized thread-safe approval manager."""

    def __init__(self, default_timeout: float = 120.0):
        self.default_timeout = default_timeout
        self._lock = threading.Lock()
        self._requests: Dict[str, ApprovalRequest] = {}

    def create_request(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        description: str,
        command: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> ApprovalRequest:
        appr_id = f"appr_{uuid.uuid4().hex[:12]}"
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout
        req = ApprovalRequest(
            approval_id=appr_id,
            session_id=session_id,
            tool_name=tool_name,
            command=command or arguments.get("command"),
            arguments=arguments,
            description=description,
            timeout_seconds=timeout,
        )
        with self._lock:
            self._requests[appr_id] = req

        # Emit structured event for Desktop UI and WebSocket listeners
        event_bus.emit(
            AgentEvent(
                event_type=EventType.APPROVAL_REQUIRED.value,
                state=AgentState.WAITING_FOR_APPROVAL,
                session_id=session_id,
                data=req.to_dict(),
            )
        )
        return req

    def wait_for_decision(self, req: ApprovalRequest) -> bool:
        """Blocks calling worker thread safely until user responds or timeout occurs."""
        signaled = req._event.wait(timeout=req.timeout_seconds)
        with self._lock:
            if not signaled:
                req.status = ApprovalStatus.EXPIRED
                req.decision = False
                return False
            return bool(req.decision)

    def respond(self, approval_id: str, approved: bool) -> bool:
        """Called by API endpoint when user clicks Approve or Reject."""
        with self._lock:
            req = self._requests.get(approval_id)
            if not req or req.status != ApprovalStatus.PENDING:
                return False

            req.decision = approved
            req.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            req._event.set()
            return True

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            return self._requests.get(approval_id)

    def list_pending(self, session_id: Optional[str] = None) -> List[ApprovalRequest]:
        with self._lock:
            now = time.time()
            pending = []
            for req in self._requests.values():
                if req.status == ApprovalStatus.PENDING:
                    if (now - req.created_at) > req.timeout_seconds:
                        req.status = ApprovalStatus.EXPIRED
                        req.decision = False
                        req._event.set()
                        continue
                    if session_id is None or req.session_id == session_id:
                        pending.append(req)
            return pending


# Global singleton approval manager
approval_manager = ApprovalManager()
