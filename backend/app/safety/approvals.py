from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.observability.logging import logger
from app.safety.permissions import ActionPermissionManager, RiskLevel


@dataclass
class ApprovalTicket:
    id: str
    task_id: str
    tool_name: str
    arguments: Dict[str, object]
    risk_level: RiskLevel
    status: str = "pending"  # "pending", "approved", "rejected"
    comment: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None


class ApprovalManager:
    """In-memory and durable tracker for human approval requests."""

    def __init__(self):
        self._tickets: Dict[str, ApprovalTicket] = {}

    def create_request(
        self,
        task_id: str,
        tool_name: str,
        arguments: Dict[str, object]
    ) -> ApprovalTicket:
        ticket_id = f"appr-{uuid.uuid4().hex[:8]}"
        risk = ActionPermissionManager.get_risk_level(tool_name, arguments)

        ticket = ApprovalTicket(
            id=ticket_id,
            task_id=task_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk,
            status="pending"
        )
        self._tickets[ticket_id] = ticket
        logger.warning(f"Created approval ticket {ticket_id} for task {task_id}: {tool_name} (risk: {risk.value})")
        return ticket

    def approve(self, ticket_id: str, comment: Optional[str] = None) -> ApprovalTicket:
        if ticket_id not in self._tickets:
            raise KeyError(f"Approval ticket {ticket_id} not found")
        ticket = self._tickets[ticket_id]
        ticket.status = "approved"
        ticket.comment = comment
        ticket.resolved_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"Ticket {ticket_id} APPROVED by human reviewer.")
        return ticket

    def reject(self, ticket_id: str, reason: Optional[str] = None) -> ApprovalTicket:
        if ticket_id not in self._tickets:
            raise KeyError(f"Approval ticket {ticket_id} not found")
        ticket = self._tickets[ticket_id]
        ticket.status = "rejected"
        ticket.comment = reason
        ticket.resolved_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"Ticket {ticket_id} REJECTED by human reviewer. Reason: {reason}")
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[ApprovalTicket]:
        return self._tickets.get(ticket_id)

    def list_pending(self, task_id: Optional[str] = None) -> List[ApprovalTicket]:
        tickets = [t for t in self._tickets.values() if t.status == "pending"]
        if task_id:
            tickets = [t for t in tickets if t.task_id == task_id]
        return tickets


# Global singleton
approval_manager = ApprovalManager()
