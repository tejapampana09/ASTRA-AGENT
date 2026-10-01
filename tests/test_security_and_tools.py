"""Unit tests for ASTRA V4 Tool Security Sandbox and Tool Registry."""
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from astra.tools import PermissionLevel, SecurityManager, ToolExecutor, ToolRegistry


@pytest.fixture
def temp_workspace():
    td = tempfile.mkdtemp()
    ws = Path(td).resolve()
    yield ws
    shutil.rmtree(td, ignore_errors=True)


def test_path_traversal_blocked(temp_workspace):
    sec = SecurityManager(temp_workspace)

    # Attempt path traversal outside workspace
    with pytest.raises(PermissionError) as exc_info:
        sec.resolve_and_validate_path("../../windows/system32/cmd.exe")
    assert "Security Violation" in str(exc_info.value)

    with pytest.raises(PermissionError) as exc_info2:
        sec.resolve_and_validate_path("../secret.txt")
    assert "Security Violation" in str(exc_info2.value)


def test_sensitive_file_protection(temp_workspace):
    sec = SecurityManager(temp_workspace)
    
    # Sensitive .env file should be blocked from raw reading by default
    (temp_workspace / ".env").write_text("API_KEY=secret_123")
    with pytest.raises(PermissionError) as exc_info:
        sec.resolve_and_validate_path(".env")
    assert "Security Protection" in str(exc_info.value)

    # Key file should also be blocked
    (temp_workspace / "id_rsa").write_text("private-key-material")
    with pytest.raises(PermissionError) as exc_info2:
        sec.resolve_and_validate_path("id_rsa")
    assert "Security Protection" in str(exc_info2.value)


def test_dangerous_command_classification(temp_workspace):
    sec = SecurityManager(temp_workspace)

    assert sec.classify_command("rm -rf /") == PermissionLevel.DANGEROUS
    assert sec.classify_command("format c:") == PermissionLevel.DANGEROUS
    assert sec.classify_command("git reset --hard HEAD~1") == PermissionLevel.DANGEROUS
    assert sec.classify_command("git push origin main --force") == PermissionLevel.DANGEROUS
    
    # Safe commands
    assert sec.classify_command("pytest -q") == PermissionLevel.SAFE
    assert sec.classify_command("python script.py") == PermissionLevel.SAFE
    assert sec.classify_command("git status") == PermissionLevel.SAFE


def test_create_and_delete_file(temp_workspace):
    tools = ToolExecutor(temp_workspace)

    # create_file
    res = tools.create_file("module.py", "def compute(): pass\n")
    assert "Successfully created" in res
    assert (temp_workspace / "module.py").exists()

    # duplicate create_file fails
    res_dup = tools.create_file("module.py", "duplicate")
    assert "Error: File already exists" in res_dup

    # delete_file
    res_del = tools.delete_file("module.py")
    assert "Successfully deleted" in res_del
    assert not (temp_workspace / "module.py").exists()


def test_tool_registry_execution(temp_workspace):
    registry = ToolRegistry(temp_workspace)
    
    # Execute write_file through central registry
    res = registry.execute("write_file", {"file_path": "calc.py", "content": "x = 100\n"})
    assert res.success is True
    assert (temp_workspace / "calc.py").exists()

    # Read back through central registry
    res_read = registry.execute("read_file", {"file_path": "calc.py"})
    assert res_read.success is True
    assert "x = 100" in res_read.output
