from __future__ import annotations

import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "ASTRA" in data["app"]


def test_create_and_get_task():
    # 1. Create Task
    create_payload = {
        "goal": "Create a FastAPI hello-world endpoint, write a test, run the test, and report the result."
    }
    res = client.post("/api/tasks", json=create_payload)
    assert res.status_code == 202
    task_data = res.json()
    assert "task_id" in task_data
    task_id = task_data["task_id"]

    # 2. Get Task
    get_res = client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 200
    assert get_res.json()["task_id"] == task_id

    # 3. List Tasks
    list_res = client.get("/api/tasks")
    assert list_res.status_code == 200
    task_ids = [t["task_id"] for t in list_res.json()]
    assert task_id in task_ids


def test_scan_repository_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        (repo_path / "requirements.txt").write_text("fastapi\npytest\n", encoding="utf-8")

        res = client.post("/api/repositories/scan", json={"path": str(repo_path)})
        assert res.status_code == 200
        summary = res.json()
        assert "Python" in summary["languages"]
        assert summary["backend"] == "FastAPI"
        assert summary["test_framework"] == "pytest"


def test_approvals_api():
    res = client.get("/api/approvals")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
