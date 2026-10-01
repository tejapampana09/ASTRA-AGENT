"""ASTRA V4 Local API Server & WebSocket Event Hub.

Provides RESTful endpoints and real-time WebSocket event streaming for
the Electron Desktop UI and external integrations.
"""
from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from astra import __version__
from astra.agent import AstraAgent
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
main_event_loop: Optional[asyncio.AbstractEventLoop] = None

router = LLMRouter()
current_workspace = WorkspaceManager(settings.workspace_path)


@app.on_event("startup")
async def on_startup():
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()


# Broadcast AgentEvents to all connected WebSockets
def broadcast_event(event: AgentEvent) -> None:
    data_json = event.to_json()
    loop = main_event_loop
    if loop and loop.is_running():
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
            pass

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


@app.post("/api/approvals/{approval_id}")
def handle_approval(approval_id: str, req: ApprovalResponseRequest):
    """Approve or reject a pending dangerous command."""
    if approval_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval request not found or expired.")
    appr = pending_approvals[approval_id]
    appr["approved"] = req.approved
    appr["event"].set()
    return {"approval_id": approval_id, "approved": req.approved}


# WebSocket for Live Events
@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        # Send initial status
        meta = current_workspace.scan()
        initial_event = AgentEvent(
            event_type="connection_established",
            state=AgentState.IDLE,
            data={
                "message": "Connected to ASTRA V4 runtime engine",
                "workspace": str(current_workspace.workspace_path),
                "project_type": meta.project_type.value,
                "ollama": router.ollama.health(),
            }
        )
        await websocket.send_text(initial_event.to_json())

        while True:
            # Keep alive & listen for client messages
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, Exception):
        connected_websockets.discard(websocket)
    finally:
        connected_websockets.discard(websocket)


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Launch uvicorn server programmatically."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
