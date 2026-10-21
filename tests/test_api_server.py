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
