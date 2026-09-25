"""
P4.10 LIVE OPENHANDS + REAL LLM AUTONOMOUS E2E TEST RUNNER
===========================================================

Purpose:
--------
This test executes the full black-box autonomous repair loop using the
LIVE OpenHands SDK and a REAL LLM (e.g. Gemini, Claude, or GPT-4o).

Execution Flow:
---------------
1. Checks for presence of an active LLM API key (LLM_API_KEY, GEMINI_API_KEY,
   ANTHROPIC_API_KEY, or OPENAI_API_KEY).
   If absent: gracefully SKIPS with clear instructions on how to activate.
2. Creates an isolated repository with a real failing test (auth.py hardcoded False).
3. Invokes the full ASTRA LangGraph state machine WITHOUT ASTRA_MOCK_AGENT.
4. The live OpenHands Agent actually inspects files, reasons through the error,
   invokes tools, and modifies auth.py.
5. Intelligent Verifier executes real pytest subprocess -> confirms FAIL -> PASS.
6. A Conventional Git commit is generated and pushed to an upstream origin.
7. PR description generated and human-approval gate strictly enforced.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from app.agents.graph import build_astra_graph
from app.agents.state import AstraAgentState
from app.config import settings
from app.git.branch import BranchManager
from app.git.pr import PullRequestManager
from app.runtime.checkpointer import get_durable_checkpointer
from app.runtime.lifecycle import task_lifecycle
from app.runtime.workspace import WorkspaceManager


def has_live_llm_key() -> bool:
    """Returns True if any supported live LLM API key is present in environment or config."""
    return bool(
        settings.LLM_API_KEY
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )


@pytest.fixture
def live_e2e_env():
    """Sets up an isolated git repository with a failing test and bare upstream origin."""
    base_tmp = Path(tempfile.mkdtemp(prefix="astra_live_llm_e2e_"))
    repo_dir = base_tmp / "sample_service"
    repo_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Live LLM Tester"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "tester@astra-live.corp"], cwd=repo_dir, capture_output=True, check=True)

    # Broken module (BUG: authenticate always returns False)
    auth_code = """
def authenticate(token: str) -> bool:
    # Defect: Always denies
    return False
"""
    test_code = """
from auth import authenticate

def test_valid_token_authenticated():
    assert authenticate("valid_token_xyz123") is True

def test_invalid_token_rejected():
    assert authenticate("bad_token_999") is False
"""
    (repo_dir / "auth.py").write_text(auth_code.strip(), encoding="utf-8")
    (repo_dir / "test_auth.py").write_text(test_code.strip(), encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit with auth bug"], cwd=repo_dir, capture_output=True, check=True)

    bare_remote = base_tmp / "remote_origin.git"
    bare_remote.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare"], cwd=bare_remote, capture_output=True, check=True)

    subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, capture_output=True, check=False)

    wm = WorkspaceManager(base_dir=base_tmp / "workspaces")

    yield {
        "base_tmp": base_tmp,
        "repo_dir": repo_dir,
        "bare_remote": bare_remote,
        "workspace_mgr": wm,
    }

    shutil.rmtree(base_tmp, ignore_errors=True)


@pytest.mark.skipif(
    not has_live_llm_key(),
    reason="Live LLM API key not detected (set GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, or LLM_API_KEY to run)."
)
def test_p4_10_live_openhands_llm_e2e(live_e2e_env):
    """
    BLACK-BOX LIVE AUTONOMOUS CODING E2E TEST:
    Runs real OpenHands SDK + Real LLM reasoning without any mock runtime.
    """
    env = live_e2e_env
    task_id = "task-live-llm-e2e-001"
    repo_dir = env["repo_dir"]
    bare_remote = env["bare_remote"]
    wm = env["workspace_mgr"]

    # 1. Register Task
    task_lifecycle.create_task(
        task_id=task_id,
        goal="Fix failing tests in test_auth.py: authenticate() must accept tokens with 'valid_token' prefix and reject others.",
        timeout_seconds=900,
    )

    # 2. Workspace & Branch Isolation
    ws = wm.create_workspace(task_id=task_id, source_repo_path=repo_dir)
    assert ws.path.exists()

    subprocess.run(["git", "remote", "remove", "origin"], cwd=ws.path, capture_output=True, check=False)
    subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=ws.path, capture_output=True, check=True)

    branch_name = BranchManager.create_feature_branch(ws.path, task_id, "Fix auth token logic")

    # 3. Confirm tests fail initially
    pre_test = subprocess.run(
        [__import__("sys").executable, "-m", "pytest", "test_auth.py", "-v"],
        cwd=ws.path, capture_output=True, text=True
    )
    assert pre_test.returncode != 0, "Test must genuinely fail before OpenHands runs"

    # 4. Invoke ASTRA Graph with LIVE OpenHands (ASTRA_MOCK_AGENT unset)
    os.environ.pop("ASTRA_MOCK_AGENT", None)

    checkpointer = get_durable_checkpointer()
    graph = build_astra_graph(checkpointer=checkpointer)

    initial_state: AstraAgentState = {
        "task_id": task_id,
        "user_goal": "Inspect the repository, diagnose why test_auth.py is failing, modify auth.py to fix authenticate() so it returns True for valid_token prefix, and verify tests pass.",
        "workspace_path": str(ws.path),
        "repo_id": "astra-agent/sample-service",
        "current_step": 0,
        "plan": [],
        "files_to_modify": ["auth.py"],
        "active_file": "auth.py",
        "observations": [],
        "verification_status": "pending",
        "verification_evidence": {},
        "diff_analysis": "",
        "failure_history": [],
        "iteration_count": 0,
        "retry_count": 0,
        "approval_required": False,
        "approval_status": "none",
        "final_result": {},
    }

    config = {"configurable": {"thread_id": task_id}}
    result = graph.invoke(initial_state, config=config)

    # 5. Verify Autonomous Verification
    verification_status = result.get("verification_status", "")
    assert verification_status in ["verified", "VERIFIED"], (
        f"Live agent failed to verify solution. Status: {verification_status}\n"
        f"Observations: {result.get('observations')}\n"
        f"Errors: {result.get('errors')}"
    )

    # 6. Verify real pytest runs pass in workspace
    post_test = subprocess.run(
        [__import__("sys").executable, "-m", "pytest", "test_auth.py", "-v"],
        cwd=ws.path, capture_output=True, text=True
    )
    assert post_test.returncode == 0, f"Tests must PASS after live agent intervention:\n{post_test.stdout}"

    # 7. Verify real commit & remote push
    final_res = result.get("final_result", {})
    assert "commit" in final_res
    commit_data = final_res["commit"]
    assert commit_data.get("success") is True

    # Pushed to remote origin
    remote_branch_check = subprocess.run(
        ["git", "branch", "--list", branch_name],
        cwd=bare_remote,
        capture_output=True,
        text=True,
    )
    assert branch_name in remote_branch_check.stdout

    # 8. Human Gate strictly enforced
    with pytest.raises(PermissionError):
        PullRequestManager.merge_pull_request(
            repo="astra-agent/sample-service",
            pr_number=final_res.get("pull_request", {}).get("pr_number", 1),
            human_approved=False
        )
