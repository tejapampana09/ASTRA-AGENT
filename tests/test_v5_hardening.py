"""Tests for ASTRA V5 Hardening:
- Persistent Checkpoints & Crash-Safe Rollback
- ProgressTracker & Stagnation Scoring
- Dynamic Planner & Adaptive Replanning
- Deterministic Agent Controller
- Session-only WebSocket Routing
"""
import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from astra.checkpoints import CheckpointManager
from astra.controller import DeterministicAgentController
from astra.events import AgentEvent, AgentState, EventType
from astra.planner import Planner
from astra.progress import ProgressAction, ProgressTracker
from astra.session import SessionManager
from astra.state import StepStatus, TaskPlan, TaskState
from astra.tools import ToolRegistry, ToolResult


@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        ws = Path(tmp_dir) / "workspace"
        ws.mkdir()
        db_file = Path(tmp_dir) / "test_sessions.db"
        sess_mgr = SessionManager(db_path=db_file)
        yield ws, sess_mgr


def test_persistent_checkpoint_survives_restart(temp_env):
    workspace, sess_mgr = temp_env
    sess_id = sess_mgr.create_session(str(workspace), title="Checkpoint Test")

    # Create pre-existing file
    file_a = workspace / "module.py"
    file_a.write_text("v1_code = True\n")

    # Manager 1 takes checkpoint and mutates
    mgr1 = CheckpointManager(workspace, session_manager=sess_mgr)
    chk = mgr1.create_checkpoint(sess_id, "Before editing module.py", files=["module.py"])
    file_a.write_text("v2_code_broken = True\n")

    # Simulate crash/restart: Manager 2 created fresh with no in-memory state
    mgr2 = CheckpointManager(workspace, session_manager=sess_mgr)
    assert len(mgr2.checkpoints) >= 1
    assert any(c.checkpoint_id == chk.checkpoint_id for c in mgr2.checkpoints)

    # Rollback using Manager 2
    res = mgr2.rollback(chk.checkpoint_id)
    assert res["success"] is True
    assert "module.py" in res["restored_files"]
    assert file_a.read_text() == "v1_code = True\n"


def test_progress_tracker_evaluates_plan_and_errors(temp_env):
    workspace, _ = temp_env
    tracker = ProgressTracker(workspace, max_stagnant_steps=3)
    plan = TaskPlan(goal="Test goal")
    plan.add_step("Step 1")
    plan.add_step("Step 2")

    # 1. Step without progress
    rep1 = tracker.record_step("read_file", {"file_path": "a.py"}, True, "some content", plan)
    assert rep1.is_progressing is True

    # 2. Complete a step -> plan percentage advances
    plan.complete_current_step("Step 1 done")
    rep2 = tracker.record_step("write_file", {"file_path": "b.py"}, True, "ok", plan)
    assert rep2.is_progressing is True
    assert rep2.details.get("plan_percentage") == 50.0

    # 3. Repeated error produces stagnation
    tracker.record_step("run_command", {"command": "pytest"}, False, "AssertionError: expected 1 got 2")
    rep_stagnant = tracker.record_step("run_command", {"command": "pytest"}, False, "AssertionError: expected 1 got 2")
    assert rep_stagnant.is_progressing is False
    assert rep_stagnant.recommended_action == ProgressAction.REPLAN


def test_planner_initial_and_replan():
    plan = Planner.create_initial_plan("Implement JWT authentication", "python")
    assert len(plan.steps) == 3
    assert plan.steps[0].status == StepStatus.IN_PROGRESS
    assert "Explore" in plan.steps[0].title

    # Trigger dynamic replanning
    replanned = Planner.replan(plan, failure_reason="Missing PyJWT dependency", error_details="ModuleNotFoundError: No module named 'jwt'")
    # Recovery step should be injected before final step
    step_titles = [s.title for s in replanned.steps]
    assert any("Resolve Blocker" in t for t in step_titles)
    curr = replanned.get_current_step()
    assert curr is not None
    assert "Resolve Blocker" in curr.title


def test_deterministic_controller_lifecycle(temp_env):
    workspace, sess_mgr = temp_env
    sess_id = sess_mgr.create_session(str(workspace), title="Controller Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="Create calculator module",
        session_manager=sess_mgr,
    )

    # 1. Prepare action creates checkpoint for mutating action
    allowed, msg, _ = controller.validate_and_prepare_action("create_file", {"file_path": "calc.py", "content": "def add(a, b): return a + b"})
    assert allowed is True

    # 2. Execute action
    res = controller.execute_action("create_file", {"file_path": "calc.py", "content": "def add(a, b): return a + b"})
    assert res.success is True

    # 3. Post-execution records changes in TaskState and SQLite
    prep = controller.record_and_evaluate_action("create_file", {"file_path": "calc.py"}, res)
    assert prep.is_progressing is True
    assert "calc.py" in controller.task_state.files_created

    # 4. Loop detection prevents duplicate invocation
    controller.record_and_evaluate_action("create_file", {"file_path": "calc.py"}, res)
    allowed2, err2, guide2 = controller.validate_and_prepare_action("create_file", {"file_path": "calc.py"})
    assert allowed2 is False
    assert "duplicate" in err2.lower()
    assert guide2 is not None

    # 5. Persisted TaskState check
    saved_state = sess_mgr.get_task_state(sess_id)
    assert saved_state is not None
    assert "calc.py" in saved_state["files_created"]


def test_session_message_history_and_resume(temp_env):
    workspace, sess_mgr = temp_env
    sess_id = sess_mgr.create_session(str(workspace), title="Resume Test")

    sess_mgr.add_message(sess_id, "user", "Create utils.py")
    sess_mgr.add_message(sess_id, "assistant", "I will create utils.py", [{"function": {"name": "create_file"}}])
    sess_mgr.add_message(sess_id, "tool", "Created utils.py")

    history = sess_mgr.get_messages(sess_id)
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "tool"
