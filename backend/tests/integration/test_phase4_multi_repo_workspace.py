import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runtime.workspace import (
    IsolatedWorkspace,
    WorkspaceManager,
    WorkspaceMetadata,
    WorkspaceSecurityError,
)


@pytest.fixture
def temp_workspace_mgr():
    temp_dir = tempfile.mkdtemp(prefix="astra_test_workspaces_")
    mgr = WorkspaceManager(base_dir=temp_dir)
    yield mgr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_concurrent_task_workspace_isolation(temp_workspace_mgr):
    """
    Verify that concurrent tasks targeting the same repository receive strictly
    isolated directories, so file modifications never leak or conflict.
    """
    # 1. Create a mock source repository
    src_dir = Path(tempfile.mkdtemp(prefix="mock_source_repo_"))
    try:
        (src_dir / "app.py").write_text("print('original code')\n", encoding="utf-8")

        # 2. Spawn two concurrent workspaces for different tasks from same source
        ws1 = temp_workspace_mgr.create_workspace(task_id="task-concurrent-1", source_repo_path=src_dir)
        ws2 = temp_workspace_mgr.create_workspace(task_id="task-concurrent-2", source_repo_path=src_dir)

        assert ws1.path != ws2.path
        assert ws1.path.exists() and ws2.path.exists()

        # 3. Modify file only in workspace 1
        mod_file = ws1.path / "feature1.py"
        mod_file.write_text("def feature1(): pass\n", encoding="utf-8")

        # 4. Verify workspace 2 is completely isolated and untainted
        assert not (ws2.path / "feature1.py").exists()
        assert "feature1.py" in ws1.get_modified_files()
        assert "feature1.py" not in ws2.get_modified_files()

    finally:
        shutil.rmtree(src_dir, ignore_errors=True)


def test_workspace_path_traversal_and_symlink_security(temp_workspace_mgr):
    """
    Verify strict security boundaries: path traversal attacks outside workspace
    raise WorkspaceSecurityError.
    """
    ws = temp_workspace_mgr.create_workspace(task_id="task-security-boundary")

    # Legitimate paths inside workspace
    valid = ws.validate_path("subdir/nested.txt")
    assert valid == (ws.path / "subdir/nested.txt").resolve()

    # Traversal attempts
    with pytest.raises(WorkspaceSecurityError):
        ws.validate_path("../../etc/passwd")

    with pytest.raises(WorkspaceSecurityError):
        ws.validate_path("..")

    # Outside absolute paths
    outside = Path(tempfile.gettempdir()).resolve()
    with pytest.raises(WorkspaceSecurityError):
        ws.validate_path(outside)


def test_workspace_metadata_and_manifest(temp_workspace_mgr):
    """
    Verify that workspace state manifests are created and updated accurately.
    """
    ws = temp_workspace_mgr.create_workspace(task_id="task-meta-01")
    manifest_path = ws.path / ".astra_workspace.json"
    assert manifest_path.exists()

    # Add a file to check disk usage calculation
    dummy_file = ws.path / "data.bin"
    dummy_file.write_bytes(b"A" * 1024)

    usage = ws.get_disk_usage()
    assert usage >= 1024

    ws.touch_accessed()
    ws.save_metadata()

    # Verify manifest reflects the disk usage
    loaded_ws = temp_workspace_mgr.get_workspace("task-meta-01")
    assert loaded_ws is not None
    assert loaded_ws.metadata.task_id == "task-meta-01"


def test_workspace_ttl_garbage_collection(temp_workspace_mgr):
    """
    Verify automated cleanup of workspaces exceeding max age retention limit.
    """
    ws_old = temp_workspace_mgr.create_workspace(task_id="task-old-01")
    ws_new = temp_workspace_mgr.create_workspace(task_id="task-new-01")

    # Backdate ws_old creation in manifest
    old_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    ws_old.metadata.created_at = old_time
    ws_old.save_metadata()

    # Run cleanup with 1 day max age (86400s)
    purged = temp_workspace_mgr.cleanup_stale_workspaces(max_age_seconds=86400)
    assert "task-old-01" in purged
    assert "task-new-01" not in purged

    assert temp_workspace_mgr.get_workspace("task-old-01") is None
    assert temp_workspace_mgr.get_workspace("task-new-01") is not None


def test_workspace_lru_and_count_quota_eviction(temp_workspace_mgr):
    """
    Verify LRU eviction when active workspace count exceeds configured limit.
    """
    ws1 = temp_workspace_mgr.create_workspace(task_id="task-lru-1")
    time.sleep(0.01)
    ws2 = temp_workspace_mgr.create_workspace(task_id="task-lru-2")
    time.sleep(0.01)
    ws3 = temp_workspace_mgr.create_workspace(task_id="task-lru-3")

    # Touch ws1 to make it more recently accessed than ws2
    ws1.touch_accessed()

    # Evict to retain max 2 workspaces
    purged = temp_workspace_mgr.cleanup_stale_workspaces(max_workspaces=2)
    assert "task-lru-2" in purged
    assert "task-lru-1" not in purged
    assert "task-lru-3" not in purged


def test_workspace_api_endpoints():
    """
    Verify REST API endpoints for workspace introspection, deletion, and cleanup.
    """
    client = TestClient(app)

    # 1. Check storage summary endpoint
    res = client.get("/api/workspaces")
    assert res.status_code == 200
    data = res.json()
    assert "total_workspaces" in data
    assert "total_disk_bytes" in data
    assert isinstance(data["workspaces"], list)

    # 2. Trigger retention policy cleanup via API
    cleanup_res = client.post("/api/workspaces/cleanup", json={"max_age_seconds": 604800})
    assert cleanup_res.status_code == 200
    cleanup_data = cleanup_res.json()
    assert cleanup_data["status"] == "success"
    assert "purged_count" in cleanup_data
