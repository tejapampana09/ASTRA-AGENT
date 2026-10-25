"""ASTRA V4 Local API Server & WebSocket Event Hub.

Provides RESTful endpoints and real-time WebSocket event streaming for
the Electron Desktop UI and external integrations.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import ipaddress
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal
from urllib.parse import urlparse
from astra.quota import request_ledger

from astra import __version__
from astra.agent import AstraAgent
from astra.approval import approval_manager
from astra.config import settings
from astra.events import AgentEvent, AgentState, EventType, event_bus
from astra.llm import LLMRouter
from astra.session import session_manager
from astra.tools import ToolExecutor
from astra.workspace import WorkspaceManager


# Active WebSocket connections & event loop reference
connected_websockets: Set[WebSocket] = set()
session_websockets: Dict[str, Set[WebSocket]] = {}
main_event_loop: Optional[asyncio.AbstractEventLoop] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()
    yield


app = FastAPI(title="ASTRA V4 Runtime API", version=__version__, lifespan=lifespan)

# Restrict CORS to configured allowed origins (no wildcard '*')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Active running agents mapped by session_id
active_agents: Dict[str, AstraAgent] = {}
agent_threads: Dict[str, threading.Thread] = {}
worker_lock = threading.RLock()

# Pending approvals for dangerous commands {approval_id: asyncio.Event or threading.Event}
pending_approvals: Dict[str, Dict[str, Any]] = {}

router = LLMRouter()
current_workspace = WorkspaceManager(settings.workspace_path)
# Trust roots are fixed at startup; workspace switching must never widen them.
approved_workspace_roots = tuple(settings.allowed_workspaces or [settings.workspace_path.resolve()])


def _network_exposed(scope) -> bool:
    # Honor the real ASGI listener/client as well as configuration. This also
    # covers `uvicorn astra.server:app --host 0.0.0.0` bypassing run_server().
    for key in ("server", "client"):
        address = scope.get(key)
        if address:
            try:
                if not ipaddress.ip_address(address[0]).is_loopback:
                    return True
            except ValueError:
                pass  # Non-network test transports and hostnames use configured policy.
    return False


@app.middleware("http")
async def enforce_listener_auth(request, call_next):
    if request.method != "OPTIONS" and _network_exposed(request.scope) and not settings.api_token:
        return JSONResponse(status_code=500, content={"detail": "ASTRA_API_TOKEN is mandatory for a network-exposed listener."})
    return await call_next(request)


def verify_api_token(
    x_astra_token: Optional[str] = Header(None, alias="X-Astra-Token"),
    authorization: Optional[str] = Header(None),
) -> None:
    """Explicit token authentication check for sensitive operations.
    
    If exposed beyond loopback or if require_auth is enabled, authentication is mandatory.
    If no token is configured under non-loopback exposure, requests fail closed (HTTP 500).
    """
    expected_token = getattr(settings, "api_token", "")
    require_auth = getattr(settings, "require_auth", False) or not getattr(settings, "is_loopback", True)

    if not expected_token and not require_auth:
        return  # Local loopback development mode with no token configured

    if not expected_token and require_auth:
        raise HTTPException(
            status_code=500,
            detail="Server security policy violation: ASTRA_API_TOKEN is mandatory when exposed beyond loopback."
        )

    provided = x_astra_token
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not provided or not secrets.compare_digest(provided.encode("utf-8"), expected_token.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API token.")


def validate_authorized_workspace(workspace_path: str) -> Path:
    """Validate and authorize a workspace path, preventing path traversal, system hijacking, and arbitrary directory escape."""
    if not workspace_path or not str(workspace_path).strip():
        raise HTTPException(status_code=400, detail="Workspace path cannot be empty.")

    try:
        p = Path(workspace_path).resolve()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid workspace path: {exc}")

    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Workspace path does not exist or is not a directory: '{p}'")

    # Reject system root and critical directories
    p_str = str(p).lower().rstrip("\\/")
    dangerous_roots = {
        "c:", "c:\\", "c:/", "c:\\windows", "c:/windows",
        "c:\\program files", "c:/program files",
        "c:\\program files (x86)", "c:/program files (x86)",
        "", "/", "/etc", "/root", "/boot", "/sys", "/proc", "/usr", "/bin", "/sbin"
    }
    if p_str in dangerous_roots or p == p.parent:
        raise HTTPException(status_code=403, detail=f"Access denied: System root directory '{p}' cannot be used as a workspace.")

    # Check for user credential directories
    for sensitive_dir in [".ssh", ".aws", ".gnupg", ".docker", ".kube", ".config"]:
        if sensitive_dir in [part.lower() for part in p.parts]:
            raise HTTPException(status_code=403, detail=f"Access denied: Sensitive directory '{p}' cannot be used as a workspace.")

    allowed_roots = approved_workspace_roots

    authorized = False
    for allowed_root in allowed_roots:
        try:
            p.relative_to(allowed_root)
            authorized = True
            break
        except ValueError:
            pass

    if not authorized:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Workspace '{p}' is outside approved workspace roots."
        )

    return p


# Broadcast AgentEvents to appropriate WebSockets:
# Session-scoped events route strictly to that session's subscribers.
# Global / system-wide events route to connected_websockets.
def broadcast_event(event: AgentEvent) -> None:
    data_json = event.to_json()
    loop = main_event_loop
    if not loop or not loop.is_running():
        return

    sess_id = event.session_id
    # Strict session isolation: deliver only to the intended session subscribers
    if sess_id:
        recipients = set(session_websockets.get(sess_id, set()))
    else:
        recipients = set(connected_websockets)

    dead = set()
    for ws in recipients:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(data_json), loop)
        except Exception:
            dead.add(ws)

    if dead:
        if sess_id and sess_id in session_websockets:
            session_websockets[sess_id].difference_update(dead)
        else:
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


class RuntimeSettingsRequest(BaseModel):
    ollamaBaseUrl: str
    model: str = Field(min_length=1, max_length=200)
    maxIterations: int = Field(ge=1, le=100)
    commandTimeout: int = Field(ge=1, le=600)
    permissionMode: Literal["balanced", "strict", "safe", "ask"]


@app.get("/api/usage", dependencies=[Depends(verify_api_token)])
def get_usage():
    return request_ledger().summary()


@app.get("/api/settings", dependencies=[Depends(verify_api_token)])
def get_runtime_settings():
    return {"ollamaBaseUrl": settings.ollama_base_url, "model": settings.default_model,
            "maxIterations": settings.max_iterations, "commandTimeout": settings.command_timeout,
            "permissionMode": settings.permission_mode}


@app.put("/api/settings", dependencies=[Depends(verify_api_token)])
def update_runtime_settings(req: RuntimeSettingsRequest):
    url = urlparse(req.ollamaBaseUrl)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise HTTPException(status_code=400, detail="Ollama URL must be an HTTP(S) endpoint without credentials.")
    with worker_lock:
        if any(_worker_alive(sid) for sid in agent_threads):
            raise HTTPException(status_code=409, detail="Stop active tasks before updating runtime settings.")
        settings.ollama_base_url = req.ollamaBaseUrl.rstrip("/")
        settings.default_model = req.model
        settings.max_iterations = req.maxIterations
        settings.command_timeout = req.commandTimeout
        settings.permission_mode = req.permissionMode
        router.ollama.base_url = settings.ollama_base_url
    return get_runtime_settings()


# REST Endpoints
@app.get("/api/health", dependencies=[Depends(verify_api_token)])
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
        "active_tasks_count": sum(t.is_alive() for t in list(agent_threads.values())),
    }


@app.get("/api/models", dependencies=[Depends(verify_api_token)])
def get_models():
    """Retrieve all available models across providers (Ollama, Gemini, Groq, TejaAI)."""
    return router.list_all_models()


@app.get("/api/sessions", dependencies=[Depends(verify_api_token)])
def list_sessions():
    """List all previous sessions."""
    return session_manager.list_sessions()


@app.post("/api/sessions", dependencies=[Depends(verify_api_token)])
def create_session(req: CreateSessionRequest):
    """Create a new session."""
    if req.workspace_path:
        target_ws = validate_authorized_workspace(req.workspace_path)
        ws = str(target_ws)
    else:
        ws = str(current_workspace.workspace_path)
    m = req.model or settings.default_model
    session_id = session_manager.create_session(ws, m, req.title)
    return {"session_id": session_id, "workspace_path": ws, "model": m}


@app.get("/api/sessions/{session_id}", dependencies=[Depends(verify_api_token)])
def get_session(session_id: str):
    """Get full details of a session."""
    sess = session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


@app.delete("/api/sessions/{session_id}", dependencies=[Depends(verify_api_token)])
def delete_session(session_id: str):
    """Delete a session."""
    with worker_lock:
        if _worker_alive(session_id):
            raise HTTPException(status_code=409, detail="Cannot delete a running session.")
        ok = session_manager.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id}


@app.get("/api/workspace", dependencies=[Depends(verify_api_token)])
def get_workspace():
    """Get active workspace metadata."""
    meta = current_workspace.scan(force_refresh=True)
    return meta.to_dict()


@app.post("/api/workspace/set", dependencies=[Depends(verify_api_token)])
def set_workspace(req: SetWorkspaceRequest):
    """Change the active workspace directory."""
    target_path = validate_authorized_workspace(req.workspace_path)
    ok = current_workspace.set_workspace(str(target_path))
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid workspace path or directory does not exist.")
    settings.workspace_path = current_workspace.workspace_path
    meta = current_workspace.scan(force_refresh=True)
    return {"success": True, "workspace_path": str(current_workspace.workspace_path), "metadata": meta.to_dict()}


@app.get("/api/workspace/files", dependencies=[Depends(verify_api_token)])
def get_workspace_files():
    """Get workspace directory tree for file explorer UI."""
    return current_workspace.get_file_tree(max_depth=4)


@app.get("/api/workspace/file", dependencies=[Depends(verify_api_token)])
def read_workspace_file(path: str):
    """Read a specific file in workspace with path traversal and security checks."""
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'path' is required.")
    tools = ToolExecutor(current_workspace.workspace_path)
    try:
        resolved = tools.security.resolve_and_validate_path(path)
    except PermissionError as p_err:
        raise HTTPException(status_code=403, detail=str(p_err))
    except ValueError as v_err:
        raise HTTPException(status_code=400, detail=str(v_err))

    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: '{path}'")
    if resolved.is_dir():
        raise HTTPException(status_code=400, detail=f"Target '{path}' is a directory, not a file.")

    content = tools.read_file(path)
    return {"path": path, "content": content}


@app.get("/api/workspace/diff", dependencies=[Depends(verify_api_token)])
def get_workspace_diff():
    """Get colorized/plain git diff of current changes."""
    tools = ToolExecutor(current_workspace.workspace_path)
    diff = tools.git_diff()
    status = tools.git_status()
    branch = tools.git_branch()
    return {"diff": diff, "status": status, "branch": branch}


def _worker_alive(session_id: str) -> bool:
    thread = agent_threads.get(session_id)
    return thread is not None and thread.is_alive()


def _launch_worker(session_id: str, agent: AstraAgent, operation) -> None:
    """Caller holds worker_lock from reservation through Thread.start()."""
    def run():
        try:
            operation()
        except Exception as exc:
            agent._set_state(AgentState.FAILED, {"error": str(exc)})
            agent._emit_event(EventType.AGENT_FAILED, {"error": str(exc)})
        finally:
            with worker_lock:
                if active_agents.get(session_id) is agent:
                    active_agents.pop(session_id, None)
                    agent_threads.pop(session_id, None)

    thread = threading.Thread(target=run, daemon=True)
    active_agents[session_id] = agent
    agent_threads[session_id] = thread
    try:
        thread.start()
    except Exception:
        active_agents.pop(session_id, None)
        agent_threads.pop(session_id, None)
        raise


def _session(session_id: str) -> Dict[str, Any]:
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@app.post("/api/tasks", dependencies=[Depends(verify_api_token)])
def start_task(req: StartTaskRequest):
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Task goal cannot be empty.")
    with worker_lock:
        sess = _session(req.session_id) if req.session_id else None
        ws_path = validate_authorized_workspace(
            req.workspace_path or (sess or {}).get("workspace_path") or str(current_workspace.workspace_path)
        )
        if sess and ws_path != Path(sess["workspace_path"]).resolve():
            raise HTTPException(status_code=409, detail="Create a new session to change its workspace.")
        model_name = req.model or (sess or {}).get("model") or settings.default_model
        session_id = req.session_id or session_manager.create_session(str(ws_path), model_name, title=req.goal[:40])
        if _worker_alive(session_id):
            raise HTTPException(status_code=409, detail="Session worker is still running.")
        agent = AstraAgent(workspace_path=ws_path, model_name=model_name,
                           session_id=session_id, max_iterations=settings.max_iterations)
        history = session_manager.get_messages(session_id) if sess else []
        if history:
            history.append({"role": "user", "content": req.goal})
            session_manager.add_message(session_id, "user", req.goal)
        _launch_worker(session_id, agent, lambda: agent.run(req.goal, existing_messages=history or None))
    return {"status": "started", "session_id": session_id, "goal": req.goal, "model": model_name}


@app.post("/api/tasks/{session_id}/stop", dependencies=[Depends(verify_api_token)])
def stop_task(session_id: str):
    with worker_lock:
        agent = active_agents.get(session_id)
        if not agent:
            raise HTTPException(status_code=404, detail="No active task found for session.")
        agent.cancel()
    return {"status": "cancelling", "session_id": session_id}


@app.post("/api/tasks/{session_id}/resume", dependencies=[Depends(verify_api_token)])
def resume_task(session_id: str):
    with worker_lock:
        if _worker_alive(session_id):
            raise HTTPException(status_code=409, detail="Session worker is still running.")
        sess = _session(session_id)
        saved = session_manager.get_task_state(session_id) or {}
        ws_path = validate_authorized_workspace(saved.get("workspace_path") or sess["workspace_path"])
        if ws_path != Path(sess["workspace_path"]).resolve():
            raise HTTPException(status_code=409, detail="Saved workspace does not match the session.")
        agent = AstraAgent(workspace_path=ws_path, model_name=saved.get("model_name") or sess["model"],
                           session_id=session_id, max_iterations=settings.max_iterations)
        _launch_worker(session_id, agent, agent.resume)
    return {"status": "resumed", "session_id": session_id}


@app.post("/api/tasks/{session_id}/rollback", dependencies=[Depends(verify_api_token)])
def rollback_task(session_id: str, checkpoint_id: Optional[str] = None):
    with worker_lock:
        if _worker_alive(session_id):
            raise HTTPException(status_code=409, detail="Stop the worker and wait for it to exit before rollback.")
        sess = _session(session_id)
        ws = validate_authorized_workspace(sess["workspace_path"])
        from astra.checkpoints import CheckpointManager
        manager = CheckpointManager(ws, session_manager, session_id=session_id)
        return manager.rollback(checkpoint_id)


@app.get("/api/approvals/pending", dependencies=[Depends(verify_api_token)])
def list_pending_approvals(session_id: Optional[str] = None):
    """List all pending approval requests."""
    return [r.to_dict() for r in approval_manager.list_pending(session_id)]


@app.post("/api/approvals/{approval_id}", dependencies=[Depends(verify_api_token)])
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
async def websocket_events(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    token: Optional[str] = None,
):
    if _network_exposed(websocket.scope) and not settings.api_token:
        await websocket.close(code=1008, reason="Server credentials are required for network exposure.")
        return
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        await websocket.close(code=1008, reason="Untrusted origin.")
        return
    try:
        verify_api_token(token or websocket.headers.get("x-astra-token"), websocket.headers.get("authorization"))
    except HTTPException:
        await websocket.close(code=1008, reason="Unauthorized or missing server credentials.")
        return

    # 2. Session authorization: ensure session exists before subscribing
    if session_id:
        sess = session_manager.get_session(session_id)
        if not sess and session_id not in active_agents and session_id != "default":
            await websocket.close(code=1008, reason=f"Unauthorized: Session '{session_id}' not found.")
            return

    await websocket.accept()
    if session_id:
        if session_id not in session_websockets:
            session_websockets[session_id] = set()
        session_websockets[session_id].add(websocket)
    else:
        connected_websockets.add(websocket)
    try:
        # Send initial status
        meta = await asyncio.to_thread(current_workspace.scan)
        initial_event = AgentEvent(
            event_type="connection_established",
            state=AgentState.IDLE,
            session_id=session_id or "default",
            data={
                "message": "Connected to ASTRA V4 runtime engine",
                "workspace": str(current_workspace.workspace_path),
                "project_type": meta.project_type.value,
                "ollama": await asyncio.to_thread(router.ollama.health),
            }
        )
        await websocket.send_text(initial_event.to_json())

        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        connected_websockets.discard(websocket)
        if session_id and session_id in session_websockets:
            session_websockets[session_id].discard(websocket)
            if not session_websockets[session_id]:
                session_websockets.pop(session_id, None)


def run_server(host: Optional[str] = None, port: Optional[int] = None):
    """Launch uvicorn server programmatically."""
    import uvicorn
    host = host or settings.api_host
    port = port or settings.api_port
    if host not in ("127.0.0.1", "localhost", "::1") and not settings.api_token:
        raise RuntimeError("ASTRA_API_TOKEN is mandatory for a non-loopback listener.")
    # Match authentication policy to the actual listener, including programmatic overrides.
    settings.is_loopback = host in ("127.0.0.1", "localhost", "::1")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
