from __future__ import annotations

import tempfile
from pathlib import Path

from app.tools.registry import tool_registry
from app.tools.filesystem import CreateFileTool, ReadFileTool, EditFileTool, DeleteFileTool
from app.tools.terminal import RunCommandTool


def test_filesystem_tools():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = Path(tmpdir)

        # 1. Create File
        create_res = tool_registry.execute_tool(
            "create_file",
            workspace_path=ws_path,
            path="hello.txt",
            content="Hello ASTRA 2.0"
        )
        assert create_res.success is True
        assert (ws_path / "hello.txt").exists()

        # 2. Read File
        read_res = tool_registry.execute_tool(
            "read_file",
            workspace_path=ws_path,
            path="hello.txt"
        )
        assert read_res.success is True
        assert read_res.output == "Hello ASTRA 2.0"

        # 3. Edit File
        edit_res = tool_registry.execute_tool(
            "edit_file",
            workspace_path=ws_path,
            path="hello.txt",
            old_text="Hello",
            new_text="Greetings"
        )
        assert edit_res.success is True
        assert (ws_path / "hello.txt").read_text(encoding="utf-8") == "Greetings ASTRA 2.0"

        # 4. Delete File
        del_res = tool_registry.execute_tool(
            "delete_file",
            workspace_path=ws_path,
            path="hello.txt"
        )
        assert del_res.success is True
        assert not (ws_path / "hello.txt").exists()


def test_terminal_blocked_commands():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = Path(tmpdir)

        # Attempt destructive command
        res = tool_registry.execute_tool(
            "run_command",
            workspace_path=ws_path,
            command="rm -rf /"
        )
        assert res.success is False
        assert "Command blocked by ASTRA security policy" in res.error
