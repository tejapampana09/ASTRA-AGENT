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
