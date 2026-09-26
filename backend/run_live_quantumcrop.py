#!/usr/bin/env python3
"""
ASTRA 2.0 - Live Real-World Repository Execution
Target: QuantumCrop-AI (https://github.com/tejapampana09/QuantumCrop-AI.git)
"""
from __future__ import annotations

import os
import sys
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure live LLM mode is active (no mock runtime)
os.environ.pop("ASTRA_MOCK_AGENT", None)

# Load local .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.graph import build_astra_graph
from app.agents.state import AstraAgentState
from app.git import BranchManager
from app.runtime.checkpointer import get_durable_checkpointer
from app.runtime.workspace import WorkspaceManager
from app.runtime.lifecycle import task_lifecycle
from app.observability.logging import logger

def main():
    repo_path = Path(__file__).resolve().parent.parent.parent / "test_quantumcrop"
    if not repo_path.exists():
        print(f"Error: Target repository not found at {repo_path}")
        return 1

    import uuid
    task_id = f"task-qc-{uuid.uuid4().hex[:6]}"
    goal = (
        "In research/utils/io.py, implement `load_json_safe(path: str | Path, default: Any = None) -> Any` "
        "which returns `default` if the file does not exist or if JSON decoding fails. "
        "Create a comprehensive unit test suite in `tests/test_io.py` that verifies: "
        "1. loading a valid json file returns the parsed data, "
        "2. loading a non-existent file returns the default value, "
        "3. loading an invalid/corrupt json file returns the default value. "
        "Verify tests pass by running: pytest tests/test_audit.py tests/test_io.py -v"
    )

    print("=" * 70)
    print("🚀 ASTRA 2.0 — LIVE REAL REPOSITORY EXECUTION")
    print(f"📁 Target Repository: {repo_path.resolve()}")
    print(f"🎯 Task Goal: {goal}")
    print("=" * 70)

    # 1. Register task in lifecycle manager
    task_lifecycle.create_task(
        task_id=task_id,
        goal=goal,
        timeout_seconds=900,
    )
    print(f"✅ Registered task {task_id} in TaskLifecycleManager")

    # 2. Workspace & Branch Isolation
    workspaces_dir = backend_dir / "temp_workspaces"
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    task_ws_path = workspaces_dir / task_id
    if task_ws_path.exists():
        shutil.rmtree(task_ws_path, ignore_errors=True)

    wm = WorkspaceManager(base_dir=workspaces_dir)
    ws = wm.create_workspace(task_id=task_id, source_repo_path=repo_path)
    print(f"✅ Created isolated workspace at: {ws.path}")

    # Set up clean bare origin remote for safe branch pushes
    bare_remote = workspaces_dir / "quantumcrop_remote.git"
    if bare_remote.exists():
        shutil.rmtree(bare_remote, ignore_errors=True)
    bare_remote.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare"], cwd=bare_remote, capture_output=True, check=True)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=ws.path, capture_output=True, check=False)
    subprocess.run(["git", "remote", "add", "origin", str(bare_remote)], cwd=ws.path, capture_output=True, check=True)

    branch_name = BranchManager.create_feature_branch(
        workspace_path=ws.path,
        task_id=task_id,
        goal="quantumcrop-safe-json-loader"
    )
    print(f"✅ Created & checked out isolated branch: {branch_name}")

    # 3. Build & Invoke ASTRA Autonomous Graph
    print("\n🧠 Invoking ASTRA Autonomous Engineering Graph...")
    checkpointer = get_durable_checkpointer()
    graph = build_astra_graph(checkpointer=checkpointer)

    initial_state: AstraAgentState = {
        "task_id": task_id,
        "user_goal": goal,
        "workspace_path": str(ws.path),
        "repo_id": "tejapampana09/QuantumCrop-AI",
        "current_step": 0,
        "plan": [],
        "files_to_modify": ["research/utils/io.py", "tests/test_io.py"],
        "active_file": "research/utils/io.py",
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

    final_state = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": task_id}}
    )

    print("\n" + "=" * 70)
    print("🎉 ASTRA EXECUTION COMPLETED")
    print("=" * 70)
    print(f"📊 Verification Status: {final_state.get('verification_status')}")
    print(f"🧪 Verification Evidence: {final_state.get('verification_evidence')}")
    final_res = final_state.get("final_result") or {}
    commit_res = final_res.get("commit") or {}
    push_res = final_res.get("push") or {}
    pr_res = final_res.get("pull_request") or {}
    print(f"🔀 Git Commit: {commit_res.get('commit_hash', 'N/A')}")
    print(f"🌿 Branch: {push_res.get('branch', branch_name)}")
    print(f"📝 PR URL: {pr_res.get('url', 'N/A')}")
    print("\n📋 PR Summary:")
    print(pr_res.get("body", "N/A"))
    print("=" * 70)

    return 0

if __name__ == "__main__":
    sys.exit(main())
