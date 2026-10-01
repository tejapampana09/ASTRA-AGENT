"""Unit tests for TaskState, TaskPlan, StagnationAndLoopDetector, and Resumption."""
from astra.session import SessionManager
from astra.state import ActionRecord, StagnationAndLoopDetector, StepStatus, TaskPlan, TaskState


def test_task_plan_progression():
    plan = TaskPlan(goal="Test goal")
    s1 = plan.add_step("Step 1", "Explore")
    s2 = plan.add_step("Step 2", "Implement")

    assert plan.current_step_index == 0
    assert plan.progress_percentage() == 0.0

    plan.complete_current_step("Step 1 done")
    assert s1.status == StepStatus.COMPLETED
    assert plan.current_step_index == 1
    assert plan.progress_percentage() == 50.0

    plan.complete_current_step("Step 2 done")
    assert s2.status == StepStatus.COMPLETED
    assert plan.progress_percentage() == 100.0
    assert plan.is_all_completed() is True


def test_stagnation_and_loop_detector():
    detector = StagnationAndLoopDetector(max_consecutive_duplicates=2)
    tool = "create_file"
    args = {"file_path": "main.py", "content": "print(1)"}

    # 1st call
    detector.record_action(tool, args, success=True)
    is_loop, _ = detector.check_loop(tool, args)
    assert is_loop is False

    # 2nd call
    detector.record_action(tool, args, success=True)
    is_loop, msg = detector.check_loop(tool, args)
    assert is_loop is True
    assert "Loop detected" in msg


def test_task_state_sqlite_persistence(tmp_path):
    db_file = tmp_path / "test_state.db"
    sm = SessionManager(db_path=db_file)
    sid = sm.create_session()

    state = TaskState(
        session_id=sid,
        goal="Build feature X",
        workspace_path=str(tmp_path),
        model_name="qwen2.5-coder:3b",
    )
    state.plan.add_step("Setup", "Create structure")
    state.files_created.add("feature.py")
    state.commands_executed.append("pytest")

    sm.save_task_state(state.to_dict())

    restored = sm.get_task_state(sid)
    assert restored is not None
    assert restored["goal"] == "Build feature X"
    assert "feature.py" in restored["files_created"]
    assert len(restored["plan"]["steps"]) == 1
