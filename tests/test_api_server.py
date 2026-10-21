"""Integration tests for ASTRA V4 FastAPI local server."""
from fastapi.testclient import TestClient
import pytest

from astra.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "version" in data
    assert "ollama" in data
    assert "active_workspace" in data


def test_api_models(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert "models" in data
    assert "ollama" in data["providers"]


def test_api_workspace(client):
    res = client.get("/api/workspace")
    assert res.status_code == 200
    data = res.json()
    assert "workspace_path" in data
    assert "project_type" in data


def test_api_session_crud(client):
    # Create
    res = client.post("/api/sessions", json={"title": "Integration Test Session"})
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    assert session_id

    # Read
    res_get = client.get(f"/api/sessions/{session_id}")
    assert res_get.status_code == 200
    assert res_get.json()["title"] == "Integration Test Session"

    # List
    res_list = client.get("/api/sessions")
    assert res_list.status_code == 200
    assert any(s["id"] == session_id for s in res_list.json())

    # Delete
    res_del = client.delete(f"/api/sessions/{session_id}")
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True


def test_api_workspace_file_path_traversal_blocked(client):
    # Attempting to read outside workspace should return 403 Forbidden
    res = client.get("/api/workspace/file?path=../../windows/win.ini")
    assert res.status_code == 403
    assert "Security Violation" in res.json()["detail"]


def test_api_workspace_file_sensitive_blocked(client):
    # Attempting to read sensitive configuration file like .env should return 403 Forbidden
    res = client.get("/api/workspace/file?path=.env")
    assert res.status_code == 403
    assert "Security Protection" in res.json()["detail"]


def test_api_workspace_file_missing_returns_404(client):
    res = client.get("/api/workspace/file?path=non_existent_file_xyz123.py")
    assert res.status_code == 404


def test_api_token_auth_protection(client):
    from astra.config import settings
    original_token = settings.api_token
    try:
        settings.api_token = "secret-test-token"

        # Request without token should return 401 Unauthorized
        res_unauth = client.post("/api/workspace/set", json={"workspace_path": "."})
        assert res_unauth.status_code == 401
        assert "Unauthorized" in res_unauth.json()["detail"]

        # Request with invalid token should return 401 Unauthorized
        res_bad = client.post(
            "/api/workspace/set",
            json={"workspace_path": "."},
            headers={"X-Astra-Token": "wrong-token"},
        )
        assert res_bad.status_code == 401

        # Request with valid header token should succeed
        res_ok = client.post(
            "/api/workspace/set",
            json={"workspace_path": "."},
            headers={"X-Astra-Token": "secret-test-token"},
        )
        assert res_ok.status_code == 200
    finally:
        settings.api_token = original_token


def test_websocket_session_event_isolation():
    """Verify that private session events are strictly isolated to that session's subscribers."""
    from unittest.mock import patch, MagicMock
    from astra.server import broadcast_event, session_websockets, connected_websockets
    from astra.events import AgentEvent, AgentState
    import astra.server as server

    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    server.main_event_loop = mock_loop

    ws_a = MagicMock()
    ws_b = MagicMock()
    ws_global = MagicMock()

    session_websockets["sess_A"] = {ws_a}
    session_websockets["sess_B"] = {ws_b}
    connected_websockets.add(ws_global)

    try:
        with patch("asyncio.run_coroutine_threadsafe") as mock_dispatch:
            event = AgentEvent(event_type="test", state=AgentState.EXECUTING, session_id="sess_A", data={})
            broadcast_event(event)
            # Event must only be dispatched to session A's subscriber
            assert mock_dispatch.call_count == 1
            ws_a.send_text.assert_called_once()
            ws_b.send_text.assert_not_called()
            ws_global.send_text.assert_not_called()
    finally:
        session_websockets.clear()
        connected_websockets.clear()


def test_cors_headers_strict_origins(client):
    # Allowed origin gets explicit access control origin header
    res_allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Untrusted origin does not get access control origin header
    res_untrusted = client.options(
        "/api/health",
        headers={
            "Origin": "http://evil-attacker.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_untrusted.headers.get("access-control-allow-origin") is None


def test_workspace_authorization_system_root_blocked(client):
    # System root directory must be rejected with 403
    import sys
    dangerous_path = "C:\\Windows" if sys.platform == "win32" else "/etc"
    res = client.post("/api/workspace/set", json={"workspace_path": dangerous_path})
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]

    # Non-existent directory must be rejected with 400
    res_missing = client.post("/api/workspace/set", json={"workspace_path": "/path/does/not/exist/12345"})
    assert res_missing.status_code == 400


def test_websocket_unauthorized_session_rejected(client):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    # Non-existent session must be rejected with code 1008
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/events?session_id=completely_unknown_session_xyz") as ws:
            ws.receive_text()


def test_websocket_token_auth_rejected(client):
    from astra.config import settings
    original_token = settings.api_token
    try:
        settings.api_token = "secret-token-ws"
        # Connecting without token must be rejected
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/events") as ws:
                ws.receive_text()

        # Connecting with valid token succeeds
        with client.websocket_connect("/ws/events?token=secret-token-ws") as ws:
            init_msg = ws.receive_text()
            assert "connection_established" in init_msg
    finally:
        settings.api_token = original_token


