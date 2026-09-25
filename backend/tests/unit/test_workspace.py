from __future__ import annotations

import pytest
from pathlib import Path
import tempfile
import shutil

from app.runtime.workspace import WorkspaceManager, IsolatedWorkspace, WorkspaceSecurityError


def test_create_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = WorkspaceManager(base_dir=tmpdir)
        ws = mgr.create_workspace(task_id="test_task_1")

        assert ws.path.exists()
        assert (ws.path / ".git").exists()
        assert ws.is_git_repo is True
        assert ws.task_id == "test_task_1"
        ws.cleanup()


def test_workspace_security_path_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = WorkspaceManager(base_dir=tmpdir)
        ws = mgr.create_workspace(task_id="test_task_sec")

        # Legitimate path inside workspace
        valid_path = ws.validate_path("app/main.py")
        assert valid_path.is_relative_to(ws.path)

        # Path traversal attack attempt
        with pytest.raises(WorkspaceSecurityError):
            ws.validate_path("../../etc/passwd")

        with pytest.raises(WorkspaceSecurityError):
            ws.validate_path("C:/Windows/System32")
        ws.cleanup()


def test_workspace_git_diff_and_dirty_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = WorkspaceManager(base_dir=tmpdir)
        ws = mgr.create_workspace(task_id="test_task_diff")

        assert not ws.is_dirty()

        # Create a file
        new_file = ws.path / "sample.py"
        new_file.write_text("print('hello')", encoding="utf-8")

        assert ws.is_dirty()
        diff = ws.get_git_diff()
        assert diff != ""
        ws.cleanup()
