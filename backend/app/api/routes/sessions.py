from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_task_lifecycle
from app.runtime.lifecycle import TaskLifecycleManager
from app.runtime.session import conversation_manager, AgentSession, ConversationMessage

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    repository_path: Optional[str] = Field(None, description="Repository URL or local path")
    model: Optional[str] = Field("ollama/qwen2.5-coder:3b", description="Model name: ollama or gemini")
    mode: Optional[str] = Field("autonomous", description="Execution mode: autonomous or guided")
    title: Optional[str] = Field(None, description="Optional conversation session title")


class SendMessageRequest(BaseModel):
    message: str = Field(..., description="User prompt or instruction for ASTRA")
    repository_path: Optional[str] = Field(None, description="Optional repository override")
    model: Optional[str] = Field(None, description="Optional model override")
    mode: Optional[str] = Field(None, description="Optional mode override")


class SessionResponse(BaseModel):
    id: str
    title: str
    repository_path: Optional[str] = None
    workspace_path: Optional[str] = None
    active_branch: str
    model: str
    mode: str
    messages: List[Dict[str, Any]]
    tasks: List[str]
    context_summary: str
    created_at: str
    updated_at: str


class SessionMessageResponse(BaseModel):
    session: SessionResponse
    task_id: str
    status: str
    goal: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionResponse)
async def create_session(req: CreateSessionRequest):
    session = conversation_manager.create_session(
        repository_path=req.repository_path,
        model=req.model,
        mode=req.mode,
        initial_title=req.title,
    )
    return SessionResponse(**session.to_dict())


@router.get("", response_model=List[SessionResponse])
async def list_sessions():
    sessions = conversation_manager.list_sessions()
    return [SessionResponse(**s.to_dict()) for s in sessions]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    session = conversation_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return SessionResponse(**session.to_dict())


@router.post("/{session_id}/messages", status_code=status.HTTP_202_ACCEPTED, response_model=SessionMessageResponse)
async def send_session_message(
    session_id: str,
    req: SendMessageRequest,
    lifecycle: TaskLifecycleManager = Depends(get_task_lifecycle),
):
    session = conversation_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    task_id = f"task-{uuid.uuid4().hex[:8]}"

    # Add message to conversation history
    conversation_manager.add_user_message(session_id, req.message, task_id=task_id)

    # Build contextual prompt with previous turns
    contextual_goal = conversation_manager.build_contextual_prompt(session_id, req.message)

    repo = req.repository_path or session.repository_path
    model = req.model or session.model
    mode = req.mode or session.mode

    # Register task with lifecycle manager
    task_info = lifecycle.create_task(
        task_id=task_id,
        goal=contextual_goal,
        repository_path=repo,
        model=model,
        mode=mode,
    )

    # If session has existing workspace, reuse it
    if session.workspace_path:
        task_info["workspace_path"] = session.workspace_path

    # Dispatch task asynchronously
    lifecycle.dispatch_task(task_id)

    # Refresh session
    updated_session = conversation_manager.get_session(session_id)

    return SessionMessageResponse(
        session=SessionResponse(**updated_session.to_dict()),
        task_id=task_id,
        status="created",
        goal=req.message,
    )
