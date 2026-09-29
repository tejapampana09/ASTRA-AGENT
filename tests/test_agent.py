"""Unit tests for ASTRA tools and agent execution."""
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from astra.tools import ToolExecutor, TOOL_DEFINITIONS
from astra.config import Config


@pytest.fixture
def temp_workspace():
    td = tempfile.mkdtemp()
    yield Path(td)
    shutil.rmtree(td, ignore_errors=True)


def test_tool_write_and_read_file(temp_workspace):
    tools = ToolExecutor(temp_workspace)
    
    # Write
    res_write = tools.write_file("test.py", "def add(a, b):\n    return a + b\n")
    assert "Successfully wrote" in res_write
    assert (temp_workspace / "test.py").exists()

    # Read
    res_read = tools.read_file("test.py")
    assert "def add(a, b):" in res_read
    assert "return a + b" in res_read


def test_tool_edit_file(temp_workspace):
    tools = ToolExecutor(temp_workspace)
    tools.write_file("greeting.txt", "Hello World!")
    
    # Edit
    res_edit = tools.edit_file("greeting.txt", "World", "ASTRA")
    assert "Successfully updated" in res_edit
    
    # Verify
    content = tools.read_file("greeting.txt")
    assert "Hello ASTRA!" in content


def test_tool_list_dir(temp_workspace):
    tools = ToolExecutor(temp_workspace)
    tools.write_file("file1.txt", "1")
    tools.write_file("file2.txt", "2")
    
    out = tools.list_dir(".")
    assert "file1.txt" in out
    assert "file2.txt" in out


def test_tool_search_code(temp_workspace):
    tools = ToolExecutor(temp_workspace)
    tools.write_file("app.py", "secret_key = 'super_secret_value'")
    
    out = tools.search_code("secret_key", ".")
    assert "app.py" in out
    assert "secret_key" in out


def test_tool_run_command(temp_workspace):
    tools = ToolExecutor(temp_workspace)
    out = tools.run_command("python -c \"print('Hello from CLI')\"")
    assert "Hello from CLI" in out
    assert "Exit code 0" in out


def test_tool_definitions_valid():
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert "read_file" in names
    assert "write_file" in names
    assert "edit_file" in names
    assert "list_dir" in names
    assert "search_code" in names
    assert "run_command" in names
