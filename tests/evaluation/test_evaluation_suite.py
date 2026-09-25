from __future__ import annotations

import tempfile
import pytest
from pathlib import Path

from app.agents.graph import finalize_task, should_continue_or_finalize
from app.agents.state import AstraAgentState
from app.agents.verifier import verify_solution
from app.runtime.workspace import WorkspaceManager
from app.verification.tests import TestRunner


def test_eval_add_endpoint_task():
    """Evaluation Task: Add a new endpoint to an existing FastAPI app and verify."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_mgr = WorkspaceManager(base_dir=tmpdir)
        ws = ws_mgr.create_workspace(task_id="eval_add_endpoint")

        # Initial codebase
        initial_app = (
            "from fastapi import FastAPI\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'status': 'ok'}\n"
        )
        (ws.path / "main.py").write_text(initial_app, encoding="utf-8")

        # Agent implements new endpoint: /items
        updated_app = (
            "from fastapi import FastAPI\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'status': 'ok'}\n\n"
            "@app.get('/items')\n"
            "def list_items():\n"
            "    return [{'id': 1, 'name': 'Item A'}]\n"
        )
        (ws.path / "main.py").write_text(updated_app, encoding="utf-8")

        # Test suite testing both endpoints
        test_file = (
            "from fastapi.testclient import TestClient\n"
            "from main import app\n\n"
            "client = TestClient(app)\n\n"
            "def test_health():\n"
            "    assert client.get('/health').status_code == 200\n\n"
            "def test_list_items():\n"
            "    res = client.get('/items')\n"
            "    assert res.status_code == 200\n"
            "    assert len(res.json()) == 1\n"
        )
        (ws.path / "test_main.py").write_text(test_file, encoding="utf-8")

        # Run verification
        state: AstraAgentState = {
            "task_id": "eval_add_endpoint",
            "user_goal": "Add /items endpoint to FastAPI app and write tests",
            "workspace_path": str(ws.path),
            "iteration_count": 1,
            "retry_count": 0,
            "observations": [],
            "failure_history": [],
            "errors": [],
        }

        verif = verify_solution(state)
        state.update(verif)

        assert state["verification_status"] == "verified"
        assert state["test_results"]["passed"] == 2
        assert state["test_results"]["failed"] == 0

        final = finalize_task(state)
        report = final["final_result"]
        assert report["status"] == "verified"
        assert report["evidence"]["tests"]["passed"] == 2

        ws.cleanup()


def test_eval_refactor_module_without_regression():
    """Evaluation Task: Refactor helper functions into separate module without breaking tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_mgr = WorkspaceManager(base_dir=tmpdir)
        ws = ws_mgr.create_workspace(task_id="eval_refactor")

        # Helper module
        helpers = (
            "def calculate_total(prices: list[float], tax_rate: float = 0.1) -> float:\n"
            "    subtotal = sum(prices)\n"
            "    return round(subtotal * (1 + tax_rate), 2)\n"
        )
        (ws.path / "helpers.py").write_text(helpers, encoding="utf-8")

        # Main service importing helper
        service = (
            "from helpers import calculate_total\n\n"
            "def process_order(items: list[dict]) -> float:\n"
            "    prices = [i['price'] for i in items]\n"
            "    return calculate_total(prices)\n"
        )
        (ws.path / "service.py").write_text(service, encoding="utf-8")

        # Unit test
        test_file = (
            "from service import process_order\n\n"
            "def test_process_order():\n"
            "    items = [{'price': 10.0}, {'price': 20.0}]\n"
            "    assert process_order(items) == 33.0\n"
        )
        (ws.path / "test_service.py").write_text(test_file, encoding="utf-8")

        # Run verification
        state: AstraAgentState = {
            "task_id": "eval_refactor",
            "user_goal": "Refactor helper logic into helpers.py and verify test integrity",
            "workspace_path": str(ws.path),
            "iteration_count": 1,
            "retry_count": 0,
            "observations": [],
            "failure_history": [],
            "errors": [],
        }

        verif = verify_solution(state)
        state.update(verif)

        assert state["verification_status"] == "verified"
        assert state["test_results"]["passed"] == 1
        assert state["test_results"]["failed"] == 0

        ws.cleanup()
