"""ASTRA V4 Local API Server & WebSocket Event Hub.

Provides RESTful endpoints and real-time WebSocket event streaming for
the Electron Desktop UI and external integrations.
"""
from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from astra import __version__
from astra.agent import AstraAgent
from astra.approval import approval_manager
from astra.config import settings
from astra.events import AgentEvent, AgentState, EventType, event_bus
from astra.llm import LLMRouter
from astra.session import session_manager
from astra.tools import ToolExecutor
from astra.workspace import WorkspaceManager

app = FastAPI(title="ASTRA V4 Runtime API", version=__version__)

# Enable CORS for desktop app and dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active running agents mapped by session_id
active_agents: Dict[str, AstraAgent] = {}
agent_threads: Dict[str, threading.Thread] = {}

# Pending approvals for dangerous commands {approval_id: asyncio.Event or threading.Event}
pending_approvals: Dict[str, Dict[str, Any]] = {}

# Active WebSocket connections
connected_websockets: Set[WebSocket] = set()
session_websockets: Dict[str, Set[WebSocket]] = {}
main_event_loop: Optional[asyncio.AbstractEventLoop] = None

router = LLMRouter()
current_workspace = WorkspaceManager(settings.workspace_path)


@app.on_event("startup")
async def on_startup():
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()


# Broadcast AgentEvents to appropriate WebSockets:
# Session-scoped events route strictly to that session's subscribers.
# Global / system-wide events route to connected_websockets.
def broadcast_event(event: AgentEvent) -> None:
    data_json = event.to_json()
    loop = main_event_loop
    if not loop or not loop.is_running():
        return

    sess_id = event.session_id
    if sess_id and sess_id in session_websockets:
        sess_dead = set()
        for ws in set(session_websockets[sess_id]):
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(data_json), loop)
            except Exception:
                sess_dead.add(ws)
        if sess_dead:
            session_websockets[sess_id].difference_update(sess_dead)
    elif not sess_id or sess_id == "global":
        dead = set()
        for ws in set(connected_websockets):
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(data_json), loop)
            except Exception:
                dead.add(ws)
        if dead:
            connected_websockets.difference_update(dead)


event_bus.subscribe(broadcast_event)


# Request Models
class CreateSessionRequest(BaseModel):
    workspace_path: Optional[str] = None
    model: Optional[str] = None
    title: Optional[str] = None


class SetWorkspaceRequest(BaseModel):
    workspace_path: str


class StartTaskRequest(BaseModel):
    session_id: Optional[str] = None
    goal: str
    workspace_path: Optional[str] = None
    model: Optional[str] = None


class ApprovalResponseRequest(BaseModel):
    approved: bool


# REST Endpoints
@app.get("/api/health")
def get_health():
    """System health check, version, and Ollama connection status."""
    ollama_health = router.ollama.health()
    meta = current_workspace.scan()
    return {
        "status": "online",
        "version": __version__,
        "ollama": ollama_health,
        "active_workspace": str(current_workspace.workspace_path),
        "project_type": meta.project_type.value,
        "default_model": settings.default_model,
        "active_tasks_count": len([a for a in active_agents.values() if not a.is_cancelled() and a.state not in (AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED, AgentState.IDLE)]),
    }


@app.get("/api/models")
def get_models():
    """Retrieve all available models across providers (Ollama, Gemini, Groq, TejaAI)."""
    return router.list_all_models()


@app.get("/api/sessions")
def list_sessions():
    """List all previous sessions."""
    return session_manager.list_sessions()


@app.post("/api/sessions")
def create_session(req: CreateSessionRequest):
    """Create a new session."""
    ws = req.workspace_path or str(current_workspace.workspace_path)
    m = req.model or settings.default_model
    session_id = session_manager.create_session(ws, m, req.title)
    return {"session_id": session_id, "workspace_path": ws, "model": m}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    """Get full details of a session."""
    sess = session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a session."""
    ok = session_manager.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id}


@app.get("/api/workspace")
def get_workspace():
    """Get active workspace metadata."""
    meta = current_workspace.scan(force_refresh=True)
    return meta.to_dict()


@app.post("/api/workspace/set")
def set_workspace(req: SetWorkspaceRequest):
    """Change the active workspace directory."""
    ok = current_workspace.set_workspace(req.workspace_path)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid workspace path or directory does not exist.")
    settings.workspace_path = current_workspace.workspace_path
    meta = current_workspace.scan(force_refresh=True)
    return {"success": True, "workspace_path": str(current_workspace.workspace_path), "metadata": meta.to_dict()}


@app.get("/api/workspace/files")
def get_workspace_files():
    """Get workspace directory tree for file explorer UI."""
    return current_workspace.get_file_tree(max_depth=4)


@app.get("/api/workspace/file")
def read_workspace_file(path: str):
    """Read a specific file in workspace."""
    tools = ToolExecutor(current_workspace.workspace_path)
    content = tools.read_file(path)
    return {"path": path, "content": content}


@app.get("/api/workspace/diff")
def get_workspace_diff():
    """Get colorized/plain git diff of current changes."""
    tools = ToolExecutor(current_workspace.workspace_path)
    diff = tools.git_diff()
    status = tools.git_status()
    branch = tools.git_branch()
    return {"diff": diff, "status": status, "branch": branch}


@app.post("/api/tasks")
def start_task(req: StartTaskRequest):
    """Start autonomous coding task in background thread."""
    ws_path = Path(req.workspace_path or current_workspace.workspace_path).resolve()
    model_name = req.model or settings.default_model
    session_id = req.session_id or session_manager.create_session(str(ws_path), model_name, title=req.goal[:40])

    # Check if already running
    if session_id in active_agents and not active_agents[session_id].is_cancelled() and active_agents[session_id].state not in (AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED, AgentState.IDLE):
        return {"status": "already_running", "session_id": session_id}

    agent = AstraAgent(
        workspace_path=ws_path,
        model_name=model_name,
        session_id=session_id,
        max_iterations=settings.max_iterations,
    )
    active_agents[session_id] = agent

    def _run_worker():
        try:
            agent.run(req.goal)
        except Exception as exc:
            agent._set_state(AgentState.FAILED, {"error": str(exc)})
            agent._emit_event(EventType.AGENT_FAILED, {"error": str(exc)})

    t = threading.Thread(target=_run_worker, daemon=True)
    agent_threads[session_id] = t
    t.start()

    return {"status": "started", "session_id": session_id, "goal": req.goal, "model": model_name}


@app.post("/api/tasks/{session_id}/stop")
def stop_task(session_id: str):
    """Stop/cancel a running agent task."""
    agent = active_agents.get(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail="No active task found for session.")
    agent.cancel()
    return {"status": "cancelling", "session_id": session_id}


@app.post("/api/tasks/{session_id}/resume")
def resume_task(session_id: str):
    """Resume an interrupted or stopped task from saved TaskState."""
    saved = session_manager.get_task_state(session_id)
    if not saved:
        sess = session_manager.get_session(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found.")
        ws_path = Path(sess.get("workspace_path") or current_workspace.workspace_path)
        model = sess.get("model") or settings.default_model
    else:
        ws_path = Path(saved.get("workspace_path") or current_workspace.workspace_path)
        model = saved.get("model_name") or settings.default_model

    agent = AstraAgent(
        workspace_path=ws_path,
        model_name=model,
        session_id=session_id,
        max_iterations=settings.max_iterations,
    )
    active_agents[session_id] = agent

    def _run_resume():
        try:
            agent.resume()
        except Exception as exc:
            agent._set_state(AgentState.FAILED, {"error": str(exc)})
            agent._emit_event(EventType.AGENT_FAILED, {"error": str(exc)})

    t = threading.Thread(target=_run_resume, daemon=True)
    agent_threads[session_id] = t
    t.start()
    return {"status": "resumed", "session_id": session_id}


@app.post("/api/tasks/{session_id}/rollback")
def rollback_task(session_id: str, checkpoint_id: Optional[str] = None):
    """Revert changes back to a specific checkpoint safely."""
    agent = active_agents.get(session_id)
    if not agent:
        sess = session_manager.get_session(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found.")
        ws = Path(sess.get("workspace_path") or current_workspace.workspace_path)
        agent = AstraAgent(workspace_path=ws, session_id=session_id)
    res = agent.checkpoint_manager.rollback(checkpoint_id)
    return res


@app.get("/api/approvals/pending")
def list_pending_approvals(session_id: Optional[str] = None):
    """List all pending approval requests."""
    return [r.to_dict() for r in approval_manager.list_pending(session_id)]


@app.post("/api/approvals/{approval_id}")
def handle_approval(approval_id: str, req: ApprovalResponseRequest):
    """Approve or reject a pending dangerous command."""
    ok = approval_manager.respond(approval_id, req.approved)
    if not ok:
        if approval_id in pending_approvals:
            appr = pending_approvals[approval_id]
            appr["approved"] = req.approved
            appr["event"].set()
            return {"approval_id": approval_id, "approved": req.approved}
        raise HTTPException(status_code=404, detail="Approval request not found or expired.")
    return {"approval_id": approval_id, "approved": req.approved}


# WebSocket for Live Events
@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, session_id: Optional[str] = None):
    await websocket.accept()
    if session_id:
        if session_id not in session_websockets:
            session_websockets[session_id] = set()
        session_websockets[session_id].add(websocket)
    else:
        connected_websockets.add(websocket)
    try:
        # Send initial status
        meta = current_workspace.scan()
        initial_event = AgentEvent(
            event_type="connection_established",
            state=AgentState.IDLE,
            session_id=session_id or "default",
            data={
                "message": "Connected to ASTRA V4 runtime engine",
                "workspace": str(current_workspace.workspace_path),
                "project_type": meta.project_type.value,
                "ollama": router.ollama.health(),
            }
        )
        await websocket.send_text(initial_event.to_json())

        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, Exception):
        connected_websockets.discard(websocket)
        if session_id and session_id in session_websockets:
            session_websockets[session_id].discard(websocket)
    finally:
        connected_websockets.discard(websocket)
        if session_id and session_id in session_websockets:
            session_websockets[session_id].discard(websocket)


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Launch uvicorn server programmatically."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
