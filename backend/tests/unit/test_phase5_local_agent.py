from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from app.llm.resolver import resolve_model, ResolvedModel
from app.runtime.workspace import (
    IsolatedWorkspace,
    LocalExecutionWorkspace,
    WorkspaceManager,
    WorkspaceSecurityError,
)
from app.runtime.session import ConversationSessionManager
from app.agents.verifier import verify_solution
from app.agents.state import AstraAgentState


def test_model_resolver_all_providers():
    """Test 6: Verify all supported providers resolve through canonical resolve_model."""
    # Ollama / Local
    res_ollama = resolve_model("ollama/qwen2.5-coder:3b")
    assert res_ollama.provider == "ollama"
    assert "qwen2.5-coder:3b" in res_ollama.model
    assert res_ollama.base_url == "http://localhost:11434"

    # Gemini
    res_gemini = resolve_model("gemini/gemini-2.5-flash")
    assert res_gemini.provider == "gemini"
    assert "gemini" in res_gemini.model

    # OpenRouter
    res_or = resolve_model("openrouter/anthropic/claude-3.5-sonnet")
    assert res_or.provider == "openrouter"
    assert res_or.base_url == "https://openrouter.ai/api/v1"

    # Anthropic
    res_anthropic = resolve_model("anthropic/claude-3-5-sonnet-20241022")
    assert res_anthropic.provider == "anthropic"

    # OpenAI
    res_openai = resolve_model("openai/gpt-4o")
    assert res_openai.provider == "openai"


def test_local_execution_workspace_operates_directly_on_repo():
    """Test 1: Verify LocalExecutionWorkspace operates directly on user's actual repo and does NOT copy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "my_project"
        repo_dir.mkdir()
        (repo_dir / "app.py").write_text("def hello(): return 'hello'", encoding="utf-8")
        (repo_dir / "test_app.py").write_text("from app import hello\ndef test_hello(): assert hello() == 'hello'", encoding="utf-8")

        mgr = WorkspaceManager(base_dir=Path(tmpdir) / "workspaces")
        ws = mgr.get_local_workspace(task_id="task_local_1", repo_path=repo_dir)

        assert isinstance(ws, LocalExecutionWorkspace)
        # Must point directly to the user's actual repo, NOT workspaces/
        assert ws.path.resolve() == repo_dir.resolve()
        assert not (Path(tmpdir) / "workspaces" / "task_local_1").exists()

        # Modify file directly
        (ws.path / "app.py").write_text("def hello(): return 'world'", encoding="utf-8")
        assert (repo_dir / "app.py").read_text(encoding="utf-8") == "def hello(): return 'world'"

        # Cleanup in Local mode must NEVER delete user repo
        ws.cleanup()
        assert repo_dir.exists()
        assert (repo_dir / "app.py").exists()


def test_local_workspace_path_security():
    """Phase 6: Verify path security inside local repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "secure_repo"
        repo_dir.mkdir()
        (repo_dir / "src").mkdir()
        (repo_dir / "src" / "app.py").write_text("x = 1", encoding="utf-8")

        ws = LocalExecutionWorkspace(task_id="t1", path=repo_dir)

        # Valid normal file inside repo
        p = ws.validate_path("src/app.py")
        assert p.exists()
        assert p.is_relative_to(repo_dir.resolve())

        # Path traversal attack
        with pytest.raises(WorkspaceSecurityError):
            ws.validate_path("../../etc/passwd")

        with pytest.raises(WorkspaceSecurityError):
            ws.validate_path("C:/Windows/System32")


def test_repository_switching_resets_session():
    """Test 2: Verify repository switching completely resets session and context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_a = Path(tmpdir) / "repoA"
        repo_b = Path(tmpdir) / "repoB"
        repo_a.mkdir()
        repo_b.mkdir()

        session_mgr = ConversationSessionManager()
        session_a = session_mgr.create_session(repository_path=str(repo_a), initial_title="Session A")
        session_mgr.add_user_message(session_a.id, "Goal for repo A")
        assert len(session_a.messages) == 1

        # Switch to repo B
        session_b = session_mgr.create_session(repository_path=str(repo_b), initial_title="Session B")
        assert session_b.id != session_a.id
        assert session_b.repository_path == str(repo_b)
        assert len(session_b.messages) == 0  # No stale messages from Repo A


def test_git_preservation_in_local_workspace():
    """Test 3: Verify existing .git metadata is preserved and not reinitialized or destroyed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "git_project"
        repo_dir.mkdir()

        # Initialize existing git repo
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True, check=True)

        app_file = repo_dir / "app.py"
        app_file.write_text("x = 10\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True, check=True)

        # Bind local workspace
        ws = LocalExecutionWorkspace(task_id="t_git", path=repo_dir)
        assert ws.is_git_repo is True
        assert not ws.is_dirty()

        # Make modification
        app_file.write_text("x = 20\n", encoding="utf-8")
        assert ws.is_dirty()
        diff = ws.get_git_diff()
        assert "+x = 20" in diff
        assert "-x = 10" in diff

        # .git directory still intact
        assert (repo_dir / ".git").is_dir()


def test_verification_detects_failure_and_does_not_fake_success():
    """Test 4: Verify verification suite detects test failures and reports failed status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "test_repo"
        repo_dir.mkdir()
        
        # Write a test that fails
        (repo_dir / "test_fail.py").write_text("def test_broken(): assert 1 == 2", encoding="utf-8")

        state: AstraAgentState = {
            "task_id": "test_verify_fail",
            "workspace_path": str(repo_dir),
            "files_changed": ["test_fail.py"],
            "user_goal": "Fix broken code",
            "plan_metadata": {"relevant_tests": ["test_fail.py"]},
            "iteration_count": 1,
            "retry_count": 0,
            "verification_status": "pending",
        }

        result = verify_solution(state)
        # Must report failed, never fake verified
        assert result["verification_status"] == "failed"
        assert result["test_results"]["failed"] > 0


def test_openhands_tool_security_enforces_containment():
    """Test 5: Verify OpenHands Terminal and FileEditor enforce workspace path security."""
    from app.runtime.agent_runtime import AgentRuntime
    from openhands.tools.file_editor.editor import FileEditor
    from openhands.tools.terminal import TerminalExecutor, TerminalAction

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "safe_repo"
        repo_dir.mkdir()
        outside_file = Path(tmpdir) / "secret.txt"
        outside_file.write_text("SUPER_SECRET_HOST_DATA", encoding="utf-8")

        ws = LocalExecutionWorkspace(task_id="t_sec", path=repo_dir)
        AgentRuntime._current_active_workspace = ws

        try:
            # 1. FileEditor security containment
            editor = FileEditor()
            obs = editor(command="view", path=str(outside_file))
            assert "Security violation" in obs.text

            # 2. Terminal cd escape containment
            executor = TerminalExecutor(working_dir=str(repo_dir))
            cd_action = TerminalAction(command="cd ..", is_input=False)
            t_obs = executor(cd_action)
            assert "Security violation" in t_obs.text or "outside workspace" in t_obs.text

            # 3. Terminal path security containment
            cat_action = TerminalAction(command=f"cat {outside_file}", is_input=False)
            t_obs2 = executor(cat_action)
            assert "Security violation" in t_obs2.text or "outside repository" in t_obs2.text

        finally:
            AgentRuntime._current_active_workspace = None
            try:
                if 'executor' in locals():
                    if hasattr(executor, "close"):
                        executor.close()
                    if hasattr(executor, "session") and hasattr(executor.session, "close"):
                        executor.session.close()
            except Exception:
                pass


def test_rag_repository_invalidation_on_repo_switch():
    """Test 6: Verify switching repositories invalidates previous RAG chunks and loads fresh index."""
    from app.rag.vector_store import get_vector_store
    from app.rag.indexer import IndexedCodeChunk, ChunkType

    vs = get_vector_store()
    chunk_a = IndexedCodeChunk(
        chunk_id="chunk_a_1",
        repo_id="RepoA",
        file_path="src/a.py",
        symbol="func_a",
        chunk_type=ChunkType.FUNCTION,
        language="python",
        content="def func_a(): return 'a'",
        embedding=[0.1] * 128
    )
    vs.upsert_chunks([chunk_a])

    # Chunks for RepoA exist
    chunks_before = vs.get_all_chunks("RepoA")
    assert len(chunks_before) == 1

    # Invalidate RepoA
    vs.delete_repo_chunks("RepoA")
    chunks_after = vs.get_all_chunks("RepoA")
    assert len(chunks_after) == 0

