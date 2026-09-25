from __future__ import annotations

import logging
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.graph import finalize_task
from app.database.models import Base
from app.memory.store import get_task_memory_store, set_task_memory_store, TaskMemoryStore
from app.rag.indexer import ChunkType
from app.rag.vector_store import get_vector_store, set_vector_store, InMemoryVectorStore


@pytest.fixture
def test_db_session_factory():
    """Provides an isolated SQLite database session factory for durable memory tests."""
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    yield session_factory
    engine.dispose()


def test_finalize_task_persists_episodic_memory_and_runs_incremental_indexing(caplog, test_db_session_factory):
    """
    REGRESSION TEST:
    Proves that finalize_task():
    1. Uses `Path` without NameError (validates `from pathlib import Path` import).
    2. Successfully records episodic task memory into TaskMemoryStore (both SQL DB and working memory).
    3. Successfully executes IncrementalIndexer on the workspace files and updates VectorStore.
    4. Logs no warnings or errors during memory/indexing finalization.
    """
    # 1. Prepare isolated stores backed by test DB
    isolated_mem_store = TaskMemoryStore(db_session_factory=test_db_session_factory)
    set_task_memory_store(isolated_mem_store)

    isolated_vec_store = InMemoryVectorStore()
    set_vector_store(isolated_vec_store)

    # 2. Create a temporary workspace with a real python source file
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        routes_dir = tmp_path / "routes"
        routes_dir.mkdir(parents=True, exist_ok=True)
        route_file = routes_dir / "billing.py"
        route_file.write_text(
            'from fastapi import APIRouter\n\n'
            'router = APIRouter()\n\n'
            '@router.post("/checkout")\n'
            'def checkout():\n'
            '    return {"status": "success"}\n',
            encoding="utf-8"
        )

        state = {
            "task_id": "task-finalize-proof-101",
            "repository_id": "repo-billing-system",
            "user_goal": "Add checkout route to billing service",
            "verification_status": "verified",
            "test_results": {"passed": 2, "failed": 0, "errors": 0, "command": "pytest tests/"},
            "build_results": {"status": "passed"},
            "files_changed": ["routes/billing.py"],
            "git_diff": '+ @router.post("/checkout")',
            "workspace_path": str(tmp_path),
            "failure_history": [{"error": "404 Not Found: POST /checkout"}],
            "observations": ["Added checkout route", "Verified endpoint tests pass"],
            "iteration_count": 1,
            "retry_count": 0,
            "errors": [],
        }

        with caplog.at_level(logging.WARNING):
            result = finalize_task(state)

        # A. Verify no warnings or errors were emitted by finalize_task
        error_or_warn_records = [
            r.message for r in caplog.records
            if r.levelno >= logging.WARNING and "persisting task memory or incremental index" in r.message
        ]
        assert not error_or_warn_records, f"finalize_task logged memory/indexing errors: {error_or_warn_records}"

        # B. Verify finalize_task produced valid final report
        assert "final_result" in result
        assert result["final_result"]["status"] == "verified"
        assert result["final_result"]["evidence"]["tests"]["passed"] == 2

        # C. Verify episodic memory was ACTUALLY persisted into TaskMemoryStore
        mem_store = get_task_memory_store()
        recalled_mem = mem_store.get_task_memory("task-finalize-proof-101")
        assert recalled_mem is not None, "Task memory was not recorded in TaskMemoryStore!"
        assert recalled_mem.task_id == "task-finalize-proof-101"
        assert recalled_mem.repo_id == "repo-billing-system"
        assert recalled_mem.goal == "Add checkout route to billing service"
        assert recalled_mem.files_modified == ["routes/billing.py"]
        assert recalled_mem.test_status == "verified"
        assert any("404 Not Found" in d for d in recalled_mem.discoveries)

        # D. Verify IncrementalIndexer ACTUALLY indexed the modified file into VectorStore
        vec_store = get_vector_store()
        indexed_chunks = vec_store.get_all_chunks("repo-billing-system")
        assert len(indexed_chunks) >= 1, "IncrementalIndexer did not index files into VectorStore!"

        symbols = [c.symbol for c in indexed_chunks]
        assert "POST /checkout" in symbols, f"Expected 'POST /checkout' in symbols: {symbols}"
        api_chunks = [c for c in indexed_chunks if c.chunk_type == ChunkType.API_ROUTE]
        assert len(api_chunks) >= 1
        assert api_chunks[0].symbol == "POST /checkout"


def test_finalize_task_without_workspace_gracefully_records_memory(test_db_session_factory):
    """
    Verifies that finalize_task records episodic memory even when workspace_path is not set.
    """
    isolated_mem_store = TaskMemoryStore(db_session_factory=test_db_session_factory)
    set_task_memory_store(isolated_mem_store)

    state = {
        "task_id": "task-no-ws-102",
        "repository_id": "repo-no-ws",
        "user_goal": "Refactor math utility logic",
        "verification_status": "verified",
        "test_results": {"passed": 1, "failed": 0, "errors": 0},
        "build_results": {"status": "passed"},
        "files_changed": [],
        "workspace_path": None,
        "failure_history": [],
    }

    result = finalize_task(state)
    assert result["final_result"]["status"] == "verified"

    mem_store = get_task_memory_store()
    rec = mem_store.get_task_memory("task-no-ws-102")
    assert rec is not None
    assert rec.goal == "Refactor math utility logic"
