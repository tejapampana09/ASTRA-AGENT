"""Unit tests for SQLite Session persistence."""
import shutil
import tempfile
from pathlib import Path
import pytest

from astra.events import AgentEvent, AgentState
from astra.session import SessionManager


@pytest.fixture
def temp_db():
    td = tempfile.mkdtemp()
    db_file = Path(td) / "test_sessions.db"
    sm = SessionManager(db_file)
    yield sm
    shutil.rmtree(td, ignore_errors=True)


def test_session_lifecycle(temp_db):
    # Create session
    s_id = temp_db.create_session(workspace_path="C:/test", model="ollama/qwen", title="Test Session")
    assert s_id is not None

    # Retrieve session
    data = temp_db.get_session(s_id)
    assert data is not None
    assert data["title"] == "Test Session"
    assert data["model"] == "ollama/qwen"
    assert data["state"] == AgentState.IDLE.value

    # Add message
    temp_db.add_message(s_id, "user", "Fix bug in auth")
    temp_db.add_message(s_id, "assistant", "I will fix it", [{"function": {"name": "read_file"}}])

    # Add file change
    temp_db.add_file_change(s_id, "auth.py", "modified")

    # Add verification
    temp_db.add_verification(s_id, True, "Tests passed", "1 test passed", "verified")

    # Check updated session
    updated = temp_db.get_session(s_id)
    assert len(updated["messages"]) == 2
    assert "auth.py" in updated["files_modified"]
    assert updated["latest_verification"]["passed"] == 1

    # List sessions
    all_sessions = temp_db.list_sessions()
    assert len(all_sessions) >= 1

    # Delete session
    deleted = temp_db.delete_session(s_id)
    assert deleted is True
    assert temp_db.get_session(s_id) is None
