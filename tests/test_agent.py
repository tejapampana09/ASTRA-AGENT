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
    assert "web_search" in names


def test_independent_verifier_valid_syntax(temp_workspace):
    from astra.verifier import IndependentVerifier
    verifier = IndependentVerifier(temp_workspace)
    
    # Create valid python file
    p = temp_workspace / "valid.py"
    p.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    
    result = verifier.verify(["valid.py"])
    assert result.passed is True
    assert result.phase == "verified"


def test_independent_verifier_catches_syntax_error(temp_workspace):
    from astra.verifier import IndependentVerifier
    verifier = IndependentVerifier(temp_workspace)
    
    # Create invalid python file
    p = temp_workspace / "broken.py"
    p.write_text("def broken_syntax(\n    return 42\n", encoding="utf-8")
    
    result = verifier.verify(["broken.py"])
    assert result.passed is False
    assert result.phase == "syntax_check"
    assert "SyntaxError" in result.details


def test_parse_gemma_tool_calls():
    from astra.llm import parse_gemma_tool_calls

    # Markdown JSON block
    sample_text = (
        "I will now create the requested function.\n"
        "```json\n"
        '{"name": "write_file", "arguments": {"file_path": "math_utils.py", "content": "def add(x, y): return x + y"}}\n'
        "```\n"
        "After creating it, I will verify it."
    )
    thought, calls = parse_gemma_tool_calls(sample_text)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "write_file"
    assert calls[0]["function"]["arguments"]["file_path"] == "math_utils.py"

    # Gemma native special token syntax
    token_text = 'Let me inspect the file: <|tool_call>call:read_file{"file_path": "main.py"}<tool_call|>'
    thought2, calls2 = parse_gemma_tool_calls(token_text)
    assert len(calls2) == 1
    assert calls2[0]["function"]["name"] == "read_file"
    assert calls2[0]["function"]["arguments"]["file_path"] == "main.py"


def test_agent_context_compression(temp_workspace):
    from astra.agent import AstraAgent
    agent = AstraAgent(workspace_path=temp_workspace)

    messages = [
        {"role": "system", "content": "You are ASTRA."},
        {"role": "user", "content": "Goal"},
        {"role": "assistant", "content": "Let me read the file"},
        {"role": "tool", "name": "read_file", "content": "X" * 1000},
        {"role": "assistant", "content": "Now editing"},
        {"role": "tool", "name": "edit_file", "content": "Y" * 1000},
        {"role": "assistant", "content": "Almost done"},
        {"role": "tool", "name": "run_command", "content": "short"},
    ]

    compressed = agent._compress_messages(messages)
    assert len(compressed) == len(messages)
    # The older tool outputs should be trimmed
    assert len(compressed[3]["content"]) < 1000
    assert "Output trimmed for context" in compressed[3]["content"]
    # The recent tool output should stay intact
    assert compressed[7]["content"] == "short"

