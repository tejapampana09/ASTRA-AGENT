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
    from app.api.dependencies import get_approval_manager

    mgr = get_approval_manager()
    ticket = mgr.create_request("task-test-approval", "execute_terminal_command", {"command": "git push origin main"})

    # 1. List approvals
    res = client.get("/api/approvals")
    assert res.status_code == 200
    tickets = res.json()
    assert any(t["id"] == ticket.id for t in tickets)

    # 2. Filter by task_id
    res_task = client.get("/api/approvals?task_id=task-test-approval")
    assert res_task.status_code == 200
    assert len(res_task.json()) >= 1

    # 3. Approve ticket
    approve_res = client.post(f"/api/approvals/{ticket.id}/approve", json={"comment": "Looks good, proceed"})
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"
    assert mgr.get_ticket(ticket.id).status == "approved"

    # 4. Create another ticket and reject
    ticket2 = mgr.create_request("task-test-approval-2", "execute_terminal_command", {"command": "rm -rf /tmp/test"})
    reject_res = client.post(f"/api/approvals/{ticket2.id}/reject", json={"comment": "Command denied"})
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"
    assert mgr.get_ticket(ticket2.id).status == "rejected"

    # 5. Non-existent ticket returns 404
    missing_res = client.post("/api/approvals/non-existent-id/approve", json={})
    assert missing_res.status_code == 404

