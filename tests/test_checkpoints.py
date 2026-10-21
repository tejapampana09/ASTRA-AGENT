"""Unit tests for ASTRA V4 Checkpoint & Rollback System."""
import shutil
import tempfile
from pathlib import Path
import pytest

from astra.checkpoints import CheckpointManager


@pytest.fixture
def temp_workspace():
    td = tempfile.mkdtemp()
    ws = Path(td).resolve()
    yield ws
    shutil.rmtree(td, ignore_errors=True)


def test_checkpoint_and_rollback_restores_file(temp_workspace):
    # Create initial file
    f = temp_workspace / "sample.py"
    f.write_text("initial_content = 1\n", encoding="utf-8")

    mgr = CheckpointManager(temp_workspace)
    cp = mgr.create_checkpoint(session_id="s1", description="before edit", files=["sample.py"])

    # Mutate file
    f.write_text("corrupted_content = 999\n", encoding="utf-8")

    # Rollback
    res = mgr.rollback(cp.checkpoint_id)
    assert res["success"] is True
    assert "sample.py" in res["restored_files"]
    assert f.read_text(encoding="utf-8") == "initial_content = 1\n"


def test_checkpoint_and_rollback_removes_created_file(temp_workspace):
    mgr = CheckpointManager(temp_workspace)
    cp = mgr.create_checkpoint(session_id="s2", description="before creating new_file.py", files=["new_file.py"])

    # Create new file
    new_f = temp_workspace / "new_file.py"
    new_f.write_text("def hello(): pass\n", encoding="utf-8")
    assert new_f.exists()

    # Rollback should delete newly created file
    res = mgr.rollback(cp.checkpoint_id)
    assert res["success"] is True
    assert "new_file.py" in res["deleted_files"]
    assert not new_f.exists()


def test_checkpoint_never_deletes_pre_existing_files(temp_workspace):
    # Pre-existing file created before CheckpointManager initialized
    pre = temp_workspace / "keep_me.txt"
    pre.write_text("pre-existing content", encoding="utf-8")

    mgr = CheckpointManager(temp_workspace)
    # Checkpoint snapshot with None for an untracked file
    cp = mgr.create_checkpoint(session_id="s3", description="snapshot", files=["nonexistent.txt"])

    res = mgr.rollback(cp.checkpoint_id)
    assert res["success"] is True
    assert pre.exists()
    assert pre.read_text(encoding="utf-8") == "pre-existing content"


def test_checkpoint_rollback_blocks_path_traversal(temp_workspace):
    # Craft a malicious checkpoint entry attempting to escape workspace
    mgr = CheckpointManager(temp_workspace)
    cp = mgr.create_checkpoint(session_id="s4", description="test traversal")
    
    # Inject a traversal path directly into checkpoint snapshots
    outside_file = temp_workspace.parent / "should_not_be_written.txt"
    if outside_file.exists():
        outside_file.unlink()

    cp.file_snapshots["../../should_not_be_written.txt"] = "malicious payload"

    res = mgr.rollback(cp.checkpoint_id)
    assert res["success"] is True
    # Verify that outside_file was NEVER created
    assert not outside_file.exists()
    assert "../../should_not_be_written.txt" not in res["restored_files"]
