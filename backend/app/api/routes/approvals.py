from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_approval_manager
from app.safety.approvals import ApprovalManager, ApprovalTicket

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalActionRequest(BaseModel):
    comment: Optional[str] = None


@router.get("", response_model=List[Dict[str, Any]])
async def list_pending_approvals(
    task_id: Optional[str] = None,
    mgr: ApprovalManager = Depends(get_approval_manager)
):
    tickets = mgr.list_pending(task_id=task_id)
    return [
        {
            "id": t.id,
            "task_id": t.task_id,
            "tool_name": t.tool_name,
            "arguments": t.arguments,
            "risk_level": t.risk_level.value,
            "status": t.status,
            "created_at": t.created_at
        }
        for t in tickets
    ]


@router.post("/{ticket_id}/approve")
async def approve_ticket(
    ticket_id: str,
    req: ApprovalActionRequest,
    mgr: ApprovalManager = Depends(get_approval_manager)
):
    try:
        ticket = mgr.approve(ticket_id, comment=req.comment)
        return {"status": "approved", "ticket_id": ticket.id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")


@router.post("/{ticket_id}/reject")
async def reject_ticket(
    ticket_id: str,
    req: ApprovalActionRequest,
    mgr: ApprovalManager = Depends(get_approval_manager)
):
    try:
        ticket = mgr.reject(ticket_id, reason=req.comment)
        return {"status": "rejected", "ticket_id": ticket.id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
