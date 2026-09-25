from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.main import app
from app.runtime.events import AgentEventType, central_event_bus
from app.runtime.lifecycle import task_lifecycle


@pytest.fixture
def test_client():
    return TestClient(app)


def test_p4_5_task_health_and_audit_endpoints(test_client):
    """
    P4.4 & P4.5 TEST:
    Proves /tasks/{task_id}/health and /tasks/{task_id}/audit endpoints return
    comprehensive auditable records of agent events, empirical evidence,
    commands executed, git diffs, and health telemetry.
    """
    task_id = "test-task-audit-01"
    # 1. Register task in lifecycle
    task_info = task_lifecycle.create_task(
        task_id=task_id,
        goal="Audit trail verification for token service",
        timeout_seconds=600,
    )
    assert task_info["task_id"] == task_id

    # 2. Emit simulated canonical events
    async def _emit_events():
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TASK_CREATED,
            message="Task initialized",
            source="api",
        )
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.PLANNING_STARTED,
            message="Planning autonomous steps",
            source="planner",
        )
        await central_event_bus.emit(
            task_id=task_id,
            event_type=AgentEventType.TEST_COMPLETED,
            message="Tests verified 4/4 passing",
            payload={"passed": 4, "failed": 0},
            source="verifier",
        )

    asyncio.run(_emit_events())

    # Attach mock final report to task info
    task_info["verification_status"] = "verified"
    task_info["final_report"] = {
        "task_id": task_id,
        "status": "VERIFIED",
        "evidence": {
            "tests": {"passed": 4, "failed": 0, "command": "pytest test_token.py"},
            "build": "passed",
            "files_changed": ["auth/token.py"],
            "verification_evidence": {"evidence_score": 0.98},
        },
        "git_diff": "--- a/auth/token.py\n+++ b/auth/token.py\n@@ -1 +1 @@\n+def verify(): return True",
        "tool_calls": [
            {"tool_name": "run_command", "command": "pytest", "duration_ms": 120}
        ],
        "decisions": [
            {"subject": "auth/token.py", "decision": "Add leeway window"}
        ],
        "commit": {
            "commit_sha": "abc12345",
            "commit_message": "feat(auth): token verification leeway",
            "branch": "astra/audit-01",
        },
        "pull_request": {
            "pr_number": 42,
            "pr_url": "https://github.com/org/repo/pull/42",
            "head_branch": "astra/audit-01",
            "base_branch": "main",
        },
        "total_tokens": 1450,
        "estimated_cost_usd": 0.007,
    }

    # 3. Test Health Endpoint
    health_resp = test_client.get(f"/api/tasks/{task_id}/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["task_id"] == task_id
    assert health_data["timeout_seconds"] == 600

    # 4. Test Audit Endpoint (P4.5)
    audit_resp = test_client.get(f"/api/tasks/{task_id}/audit")
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()

    assert audit_data["task_id"] == task_id
    assert audit_data["goal"] == "Audit trail verification for token service"
    assert audit_data["empirical_verification"]["evidence_score"] == 0.98
    assert audit_data["empirical_verification"]["test_results"]["passed"] == 4
    assert len(audit_data["timeline_events"]) >= 3
    assert audit_data["git_diff"].startswith("--- a/auth/token.py")
    assert audit_data["commit"]["commit_sha"] == "abc12345"
    assert audit_data["pull_request"]["pr_number"] == 42
    assert audit_data["token_usage_and_cost"]["total_tokens"] == 1450

    # 5. Test Event History Endpoint (P4.4)
    hist_resp = test_client.get(f"/api/events/history/{task_id}")
    assert hist_resp.status_code == 200
    events_data = hist_resp.json()
    assert len(events_data) >= 3
    assert events_data[0]["event_type"] == "TASK_CREATED"
    assert events_data[1]["event_type"] == "PLANNING_STARTED"
