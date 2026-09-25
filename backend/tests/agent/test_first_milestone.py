from __future__ import annotations

import tempfile
import pytest
from pathlib import Path

from app.agents.debugger import debug_failure
from app.agents.graph import build_astra_graph, should_continue_or_finalize, finalize_task
from app.agents.planner import plan_task, risk_assessment
from app.agents.replanner import replan_step
from app.agents.state import AstraAgentState
from app.agents.supervisor import load_repository_context, understand_task
from app.agents.verifier import verify_solution
from app.runtime.workspace import WorkspaceManager
from app.verification.tests import TestRunner


def test_first_milestone_fastapi_hello_world():
    """
    First Milestone Verification Test:
    ASTRA receives a coding task:
    'Create a FastAPI hello-world endpoint, write a test, run the test, and report the result.'
    Executes:
    Task -> Workspace -> Agent (Create Code + Test) -> Run Pytest -> Observe -> Verify -> Report
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Task & Workspace Creation
        ws_mgr = WorkspaceManager(base_dir=tmpdir)
        ws = ws_mgr.create_workspace(task_id="milestone_1_task")
        assert ws.path.exists()

        # 2. Agent modifies code in isolated workspace
        # Implements FastAPI endpoint
        main_code = (
            "from fastapi import FastAPI\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/')\n"
            "def read_root():\n"
            "    return {'message': 'Hello World'}\n"
        )
        (ws.path / "main.py").write_text(main_code, encoding="utf-8")

        # Implements TestClient test
        test_code = (
            "from fastapi.testclient import TestClient\n"
            "from main import app\n\n"
            "client = TestClient(app)\n\n"
            "def test_read_root():\n"
            "    response = client.get('/')\n"
            "    assert response.status_code == 200\n"
            "    assert response.json() == {'message': 'Hello World'}\n"
        )
        (ws.path / "test_main.py").write_text(test_code, encoding="utf-8")

        # 3. Autonomous Verification Engine runs pytest
        test_report = TestRunner.run_tests(ws.path)
        assert test_report.status == "passed", f"Tests failed: {test_report.stderr} {test_report.stdout}"
        assert test_report.passed == 1
        assert test_report.failed == 0
        assert test_report.is_successful is True

        # 4. LangGraph State & Node Verification
        state: AstraAgentState = {
            "task_id": "milestone_1_task",
            "repository_id": "milestone_1_task",
            "user_goal": "Create a FastAPI hello-world endpoint, write a test, run the test, and report the result.",
            "workspace_path": str(ws.path),
            "iteration_count": 1,
            "retry_count": 0,
            "observations": [],
            "failure_history": [],
            "errors": [],
        }

        # Step 4a: Verify solution
        verif_result = verify_solution(state)
        state.update(verif_result)

        assert state["verification_status"] == "verified"
        assert state["test_results"]["passed"] == 1
        assert state["test_results"]["failed"] == 0

        # Step 4b: Routing decision check
        next_step = should_continue_or_finalize(state)
        assert next_step == "finalize"

        # Step 4c: Final report generation
        final_out = finalize_task(state)
        report = final_out["final_result"]

        assert report["status"] == "verified"
        assert report["evidence"]["tests"]["passed"] == 1
        assert report["evidence"]["tests"]["failed"] == 0
        assert report["evidence"]["files_changed_count"] >= 2
        assert len(report["timeline"]) > 0

        ws.cleanup()


def test_first_milestone_autonomous_debugging_and_replanning():
    """
    Tests the autonomous debugging loop:
    Fail -> Debug -> Replan -> Fix -> Pass -> Verify -> Finalize
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_mgr = WorkspaceManager(base_dir=tmpdir)
        ws = ws_mgr.create_workspace(task_id="debug_task")

        # 1. Create buggy code that causes test to FAIL
        buggy_code = (
            "from fastapi import FastAPI\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/')\n"
            "def read_root():\n"
            "    return {'message': 'Incorrect Output'}\n"
        )
        (ws.path / "main.py").write_text(buggy_code, encoding="utf-8")

        test_code = (
            "from fastapi.testclient import TestClient\n"
            "from main import app\n\n"
            "client = TestClient(app)\n\n"
            "def test_read_root():\n"
            "    response = client.get('/')\n"
            "    assert response.status_code == 200\n"
            "    assert response.json() == {'message': 'Hello World'}\n"
        )
        (ws.path / "test_main.py").write_text(test_code, encoding="utf-8")

        # 2. Run initial verification -> must fail!
        initial_state: AstraAgentState = {
            "task_id": "debug_task",
            "user_goal": "Fix failing authentication/hello-world endpoint",
            "workspace_path": str(ws.path),
            "iteration_count": 1,
            "retry_count": 0,
            "observations": [],
            "failure_history": [],
            "errors": [],
        }

        verif_1 = verify_solution(initial_state)
        initial_state.update(verif_1)
        assert initial_state["verification_status"] == "failed"
        assert initial_state["test_results"]["failed"] == 1

        # 3. Route to Debugger
        routing_1 = should_continue_or_finalize(initial_state)
        assert routing_1 == "debug"

        debug_out = debug_failure(initial_state)
        initial_state.update(debug_out)
        assert len(initial_state["failure_history"]) == 1
        assert "test_read_root" in initial_state["failure_history"][0]["error"]

        # 4. Route to Replanner
        replan_out = replan_step(initial_state)
        initial_state.update(replan_out)
        assert initial_state["retry_count"] == 1

        # 5. Apply fix
        fixed_code = (
            "from fastapi import FastAPI\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/')\n"
            "def read_root():\n"
            "    return {'message': 'Hello World'}\n"
        )
        (ws.path / "main.py").write_text(fixed_code, encoding="utf-8")

        # 6. Re-verify
        verif_2 = verify_solution(initial_state)
        initial_state.update(verif_2)
        assert initial_state["verification_status"] == "verified"
        assert initial_state["test_results"]["passed"] == 1
        assert initial_state["test_results"]["failed"] == 0

        # 7. Finalize
        routing_2 = should_continue_or_finalize(initial_state)
        assert routing_2 == "finalize"

        final_res = finalize_task(initial_state)
        assert final_res["final_result"]["status"] == "verified"
        assert final_res["final_result"]["retries"] == 1

        ws.cleanup()
