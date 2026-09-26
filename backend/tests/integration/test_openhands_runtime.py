from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.runtime.agent_runtime import AgentRuntime, AstraAgentEvent, AstraExecutionResult, AstraToolCall
from app.runtime.lifecycle import TaskLifecycleManager, event_broker
from app.runtime.workspace import WorkspaceManager


def test_agent_runtime_tools_and_llm_configuration():
    runtime = AgentRuntime()
    tools = runtime._configure_tools()
    assert len(tools) >= 2
    tool_names = [t.name for t in tools]
    assert "file_editor" in tool_names
    assert "terminal" in tool_names

    llm = runtime._configure_llm(model="gpt-4o", api_key="test-api-key")
    assert llm.model == "openai/gpt-4o"
    assert llm.timeout == runtime.settings.LLM_TIMEOUT_SECONDS


def test_agent_runtime_event_emission():
    runtime = AgentRuntime()
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_mgr = WorkspaceManager(base_dir=tmpdir)
        ws = ws_mgr.create_workspace(task_id="test_runtime_events")

        received_events = []

        def on_event(ev: AstraAgentEvent):
            received_events.append(ev)

        # Mock conversation.run to avoid hitting remote LLM APIs in tests
        with patch("openhands.sdk.Conversation") as mock_conv_cls, \
             patch("openhands.sdk.Agent") as mock_agent_cls:
            mock_conv = MagicMock()
            mock_conv_cls.return_value = mock_conv
            mock_agent = MagicMock()
            mock_agent_cls.return_value = mock_agent

            res = runtime.execute_task(
                workspace=ws,
                prompt="Write a hello world program",
                on_event=on_event,
                max_iterations=5,
            )

            assert res.success is True
            assert res.task_id == "test_runtime_events"
            assert mock_conv.send_message.called
            assert mock_conv.run.called

            event_types = [e.event_type for e in received_events]
            assert "TASK_STARTED" in event_types
            assert "AGENT_RUNNING" in event_types
            assert "TASK_COMPLETED" in event_types


@pytest.mark.anyio
async def test_end_to_end_lifecycle_execution_flow():
    """
    Validates end-to-end execution path:
    Task Creation -> Lifecycle Dispatch -> LangGraph State Machine ->
    AgentRuntime -> Verification Engine -> Final Execution Report.
    """
    lifecycle = TaskLifecycleManager()
    with tempfile.TemporaryDirectory() as tmpdir:
        lifecycle.workspace_mgr = WorkspaceManager(base_dir=tmpdir)
        task_id = "e2e_test_task"

        task_info = lifecycle.create_task(
            task_id=task_id,
            goal="Add a new feature and test it",
            repository_path=None,
        )
        assert task_info["status"] == "created"

        # Mock AgentRuntime.execute_task to simulate agent writing code and tests in the workspace
        def simulate_agent_work(workspace, prompt, on_event=None, **kwargs):
            # Create a valid passing python file and test
            app_code = "def add(a, b):\n    return a + b\n"
            (workspace.path / "calc.py").write_text(app_code, encoding="utf-8")

            test_code = "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
            (workspace.path / "test_calc.py").write_text(test_code, encoding="utf-8")

            # Git add intent so diff sees it
            diff = workspace.get_git_diff()
            modified = workspace.get_modified_files()

            return AstraExecutionResult(
                success=True,
                task_id=workspace.task_id,
                message="Implemented calc.py and test_calc.py",
                tool_calls=[
                    AstraToolCall(id="tc-1", name="file_editor", arguments={"path": "calc.py"}, result="written"),
                    AstraToolCall(id="tc-2", name="file_editor", arguments={"path": "test_calc.py"}, result="written"),
                ],
                modified_files=modified or ["calc.py", "test_calc.py"],
            )

        with patch("app.agents.executor.AgentRuntime.execute_task", side_effect=simulate_agent_work):
            await lifecycle.run_task_async(task_id)

        updated_task = lifecycle.get_task(task_id)
        assert updated_task["status"] == "completed"
        assert updated_task["verification_status"] == "verified"
        assert updated_task["final_report"] is not None

        evidence = updated_task["final_report"]["evidence"]
        assert evidence["tests"]["passed"] == 1
        assert evidence["tests"]["failed"] == 0
        assert evidence["build"] == "passed"
