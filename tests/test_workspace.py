"""Unit tests for ASTRA V4 WorkspaceManager and project type detection."""
import shutil
import tempfile
from pathlib import Path
import pytest

from astra.workspace import ProjectType, WorkspaceManager


@pytest.fixture
def temp_workspace():
    td = tempfile.mkdtemp()
    ws = Path(td).resolve()
    yield ws
    shutil.rmtree(td, ignore_errors=True)


def test_detect_python_project(temp_workspace):
    (temp_workspace / "requirements.txt").write_text("pytest>=8.0.0\n")
    (temp_workspace / "app.py").write_text("print('hello')\n")
    
    wm = WorkspaceManager(temp_workspace)
    meta = wm.scan()
    assert meta.project_type == ProjectType.PYTHON
    assert meta.package_manager == "pip"
    assert "pytest" in (meta.test_command or "")


def test_detect_node_react_project(temp_workspace):
    pkg_json = """{
      "name": "sample-react-app",
      "dependencies": {
        "react": "^18.2.0",
        "react-dom": "^18.2.0"
      },
      "scripts": {
        "test": "vitest",
        "build": "vite build"
      }
    }"""
    (temp_workspace / "package.json").write_text(pkg_json)
    
    wm = WorkspaceManager(temp_workspace)
    meta = wm.scan()
    assert ProjectType.REACT in meta.project_types
    assert "test" in (meta.test_command or "")
    assert "build" in (meta.build_command or "")


def test_detect_rust_project(temp_workspace):
    (temp_workspace / "Cargo.toml").write_text('[package]\nname = "my_crate"\n')
    
    wm = WorkspaceManager(temp_workspace)
    meta = wm.scan()
    assert meta.project_type == ProjectType.RUST
    assert meta.package_manager == "cargo"
    assert meta.test_command == "cargo test"


def test_workspace_file_tree(temp_workspace):
    (temp_workspace / "src").mkdir()
    (temp_workspace / "src" / "index.ts").write_text("console.log('hi');")
    (temp_workspace / "README.md").write_text("# Doc")

    wm = WorkspaceManager(temp_workspace)
    tree = wm.get_file_tree()
    
    names = [node["name"] for node in tree]
    assert "README.md" in names
    assert "src" in names

    src_node = next(n for n in tree if n["name"] == "src")
    assert src_node["type"] == "directory"
    assert len(src_node["children"]) == 1
    assert src_node["children"][0]["name"] == "index.ts"
