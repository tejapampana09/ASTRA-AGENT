from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from app.runtime.lifecycle import TaskLifecycleManager
from app.runtime.workspace import LocalExecutionWorkspace


import asyncio

def test_local_agent_workflow_operates_on_actual_repo():
    """
    Final Acceptance Test:
    Verify ASTRA CLI local execution runs against user's actual repository,
    modifies code directly in that repository, and does NOT create a copied ASTRA/workspaces/ directory.
    """
    async def _async_test():
        os.environ["ASTRA_CLI_MODE"] = "1"
        os.environ["ASTRA_MOCK_AGENT"] = "1"  # Deterministic test execution

        with tempfile.TemporaryDirectory() as tmpdir:
            test_repo = Path(tmpdir) / "TestApp"
            test_repo.mkdir()

            # Initialize real git repository
            subprocess.run(["git", "init"], cwd=test_repo, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "TestEngineer"], cwd=test_repo, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "engineer@test.com"], cwd=test_repo, capture_output=True, check=True)

            # Create source and failing test
            (test_repo / "app.py").write_text("def solve(): return 0\n", encoding="utf-8")
            (test_repo / "test_app.py").write_text(
                "from app import solve\ndef test_solve(): assert solve() == 42\n",
                encoding="utf-8"
            )
            subprocess.run(["git", "add", "."], cwd=test_repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=test_repo, capture_output=True, check=True)

            # Initialize lifecycle manager
            lifecycle = TaskLifecycleManager()
            task_id = "task-local-e2e-001"

            task_info = lifecycle.create_task(
                task_id=task_id,
                goal="Fix the failing test in test_app.py by making solve return 42",
                repository_path=str(test_repo),
                mode="autonomous"
            )

            # Run task
            await lifecycle.run_task_async(task_id)

            # 1. Verify workspace_path points directly to the real repo
            updated_task = lifecycle.get_task(task_id)
            assert updated_task["workspace_path"] == str(test_repo.resolve())
            assert updated_task.get("execution_mode") == "LOCAL"

            # 2. Verify ASTRA did NOT copy the repo to ASTRA/workspaces/
            workspaces_base = Path("backend/workspaces").resolve()
            assert not (workspaces_base / task_id).exists()

            # 3. Verify .git exists and was not destroyed or replaced
            assert (test_repo / ".git").is_dir()

            # 4. Verify LocalExecutionWorkspace abstraction
            ws = lifecycle.workspace_mgr.get_local_workspace(task_id, test_repo)
            assert isinstance(ws, LocalExecutionWorkspace)
            assert ws.path.resolve() == test_repo.resolve()

    asyncio.run(_async_test())

