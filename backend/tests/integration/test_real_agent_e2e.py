from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
import pytest

import urllib.request

from app.runtime.lifecycle import TaskLifecycleManager
from app.runtime.workspace import LocalExecutionWorkspace


def is_ollama_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not is_ollama_available(), reason="Ollama local server is not running or unreachable")
def test_real_openhands_agent_modifies_repo_and_passes_test():
    """
    REAL AGENT E2E TEST (No Mock):
    Verifies that a real OpenHands agent using local Ollama model (qwen2.5-coder:3b)
    actually modifies the user's repository files and resolves failing tests without mock agent.
    """
    # Ensure mock agent is explicitly disabled
    os.environ.pop("ASTRA_MOCK_AGENT", None)
    os.environ["ASTRA_CLI_MODE"] = "1"

    async def _run_e2e():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_repo = Path(tmpdir) / "RealApp"
            test_repo.mkdir()

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=test_repo, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "RealTester"], cwd=test_repo, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "tester@real.com"], cwd=test_repo, capture_output=True, check=True)

            # Create source with bug and a failing test
            (test_repo / "calc.py").write_text("def multiply(a, b):\n    return a + b  # BUG: should be a * b\n", encoding="utf-8")
            (test_repo / "test_calc.py").write_text(
                "from calc import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n",
                encoding="utf-8"
            )

            subprocess.run(["git", "add", "."], cwd=test_repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit with failing test"], cwd=test_repo, capture_output=True, check=True)

            # Verify that the test initially fails
            init_res = subprocess.run([os.sys.executable, "-m", "pytest", "test_calc.py"], cwd=test_repo, capture_output=True)
            assert init_res.returncode != 0, "Test must fail initially"

            # Execute task using real OpenHands agent + Ollama
            lifecycle = TaskLifecycleManager()
            task_id = "real-agent-e2e-task"
            lifecycle.create_task(
                task_id=task_id,
                goal="Fix the bug in calc.py so that multiply returns a * b and test_calc.py passes.",
                repository_path=str(test_repo),
                model="ollama/qwen2.5-coder:3b",
                mode="autonomous"
            )

            await lifecycle.run_task_async(task_id)

            # Physical disk verification: calc.py must be modified
            content = (test_repo / "calc.py").read_text(encoding="utf-8")
            assert "*" in content or "a * b" in content, f"calc.py was not updated with multiplication fix. Content: {content}"

            # Real pytest execution verification
            final_res = subprocess.run([os.sys.executable, "-m", "pytest", "test_calc.py"], cwd=test_repo, capture_output=True)
            assert final_res.returncode == 0, f"pytest failed after agent fix: {final_res.stdout.decode()}"

    asyncio.run(_run_e2e())
