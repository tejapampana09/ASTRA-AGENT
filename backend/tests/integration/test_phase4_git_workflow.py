from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import pytest

from app.agents.graph import finalize_task
from app.git.branch import BranchManager
from app.git.commit import CommitManager
from app.git.pr import PullRequestManager
from app.memory.engineering import EngineeringMemoryStore, set_engineering_memory_store
from app.memory.store import TaskMemoryStore, set_task_memory_store
from app.rag.vector_store import InMemoryVectorStore, set_vector_store


def _setup_git_repo(ws_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=ws_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=ws_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@agent.internal"], cwd=ws_path, capture_output=True, check=True)
    # Create initial commit on main
    readme = ws_path / "README.md"
    readme.write_text("# Project\nInitial commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=ws_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=ws_path, capture_output=True, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=ws_path, capture_output=True, check=False)


def test_p4_1_branch_manager_lifecycle():
    """
    P4.1 TEST:
    Proves BranchManager creates isolated semantic feature branches,
    protects main, and switches branches safely.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        _setup_git_repo(ws_path)

        task_id = "task-8f9210aa-auth"
        goal = "Add JWT authentication to FastAPI service"

        # 1. Create feature branch
        branch_name = BranchManager.create_feature_branch(ws_path, task_id, goal)
        assert branch_name.startswith("astra/8f9210aa-")
        assert "jwt" in branch_name
        assert BranchManager.get_current_branch(ws_path) == branch_name

        # 2. Verify branches list
        branches = BranchManager.list_branches(ws_path)
        assert branch_name in branches
        assert "main" in branches

        # 3. Switch back to main
        assert BranchManager.checkout_branch(ws_path, "main")
        assert BranchManager.get_current_branch(ws_path) == "main"


def test_p4_1_commit_manager_conventional_commits():
    """
    P4.1 TEST:
    Proves CommitManager detects semantic scope and type,
    stages files, and creates Conventional Commits with verification metadata.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        _setup_git_repo(ws_path)

        # Create new source file
        services_dir = ws_path / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        auth_file = services_dir / "auth.py"
        auth_file.write_text("def authenticate(): return True\n", encoding="utf-8")

        task_id = "task-commit-01"
        goal = "Fix authentication credential validation"

        commit_res = CommitManager.create_commit(
            workspace_path=ws_path,
            task_id=task_id,
            goal=goal,
            files_changed=["services/auth.py"],
            verification_status="verified",
            test_summary="4 passed, 0 failed"
        )

        assert commit_res["success"] is True
        assert commit_res["committed"] is True
        assert commit_res["commit_sha"] is not None
        assert "fix(auth):" in commit_res["message"]
        assert "4 passed, 0 failed" in commit_res["message"]
        assert f"Task-ID: {task_id}" in commit_res["message"]

        # Verify git log
        latest = CommitManager.get_latest_commit(ws_path)
        assert latest["sha"] == commit_res["commit_sha"]
        assert "fix(auth):" in latest["subject"]


def test_p4_1_pull_request_manager_description_and_diff():
    """
    P4.1 TEST:
    Proves PullRequestManager synthesizes comprehensive PR descriptions
    and analyzes git diffs between feature branch and base.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        _setup_git_repo(ws_path)

        # Checkout feature branch and add file
        BranchManager.create_feature_branch(ws_path, "task-pr-01", "Add token refresh")
        svc_file = ws_path / "service.py"
        svc_file.write_text("def refresh(): pass\n", encoding="utf-8")
        subprocess.run(["git", "add", "service.py"], cwd=ws_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "feat: add refresh"], cwd=ws_path, capture_output=True, check=True)

        # 1. Analyze PR diff
        diff_info = PullRequestManager.analyze_pr_diff(ws_path, base_ref="main")
        assert diff_info["files_count"] == 1
        assert diff_info["files"][0]["file_path"] == "service.py"

        # 2. Generate PR description
        pr_desc = PullRequestManager.generate_pr_description(
            task_id="task-pr-01",
            goal="Add token refresh to auth service",
            files_changed=["service.py"],
            verification_evidence={
                "status": "verified",
                "evidence_score": 0.95,
                "tests": {"passed": 3, "failed": 0},
                "build": "passed",
            },
            impact_data={"affected_files": ["api/routes.py"], "risk_level": "LOW"},
            failure_history=[{"category": "runtime", "error": "Token expired", "hypothesis": "Add leeway"}]
        )

        assert "# ASTRA Pull Request" in pr_desc
        assert "Empirical Verification Evidence" in pr_desc
        assert "3 passed, 0 failed" in pr_desc
        assert "Resolved Autonomous Debugging Triages" in pr_desc
        assert "APPROVAL GATE" in pr_desc


def test_p4_1_human_approval_gate_on_merge():
    """
    CRITICAL SAFETY REQUIREMENT:
    Proves that PullRequestManager strictly blocks unauthorized merge attempts
    and requires explicit human approval.
    """
    # 1. Unauthorized merge must raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        PullRequestManager.merge_pull_request(
            repo="owner/repo",
            pull_number=42,
            human_approved=False
        )
    assert "CRITICAL SAFETY VIOLATION" in str(exc_info.value)
    assert "explicit human approval" in str(exc_info.value)

    # 2. Authorized merge succeeds
    merge_res = PullRequestManager.merge_pull_request(
        repo="owner/repo",
        pull_number=42,
        human_approved=True
    )
    assert merge_res["success"] is True
    assert merge_res["merged"] is True


def test_p4_1_finalize_task_autonomous_git_workflow():
    """
    P4.1 END-TO-END WORKFLOW:
    Proves finalize_task automatically creates conventional commit
    and generates GitHub Pull Request when task is verified.
    """
    set_task_memory_store(TaskMemoryStore())
    set_engineering_memory_store(EngineeringMemoryStore())
    set_vector_store(InMemoryVectorStore())

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        _setup_git_repo(ws_path)

        # Create branch
        BranchManager.create_feature_branch(ws_path, "task-e2e-git", "Add user profile")

        profile_file = ws_path / "profile.py"
        profile_file.write_text("def get_profile(): return {'name': 'Alice'}\n", encoding="utf-8")

        state = {
            "task_id": "task-e2e-git-99",
            "repository_id": "org/my-project",
            "user_goal": "Add user profile service",
            "verification_status": "verified",
            "test_results": {"passed": 2, "failed": 0, "errors": 0},
            "build_results": {"status": "passed"},
            "files_changed": ["profile.py"],
            "workspace_path": str(ws_path),
            "verification_evidence": {"status": "verified", "evidence_score": 1.0, "tests": {"passed": 2, "failed": 0}},
            "failure_history": [],
            "observations": [],
        }

        res = finalize_task(state)
        report = res["final_result"]

        # Verify commit created
        assert report["commit"] is not None
        assert report["commit"]["committed"] is True
        assert report["commit"]["commit_sha"] is not None

        # Verify PR created
        assert report["pull_request"] is not None
        assert report["pull_request"]["success"] is True
        assert report["pull_request"]["number"] is not None
        assert "https://github.com/org/my-project/pull/" in report["pull_request"]["url"]
