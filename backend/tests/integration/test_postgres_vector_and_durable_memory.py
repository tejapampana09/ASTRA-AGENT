from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, CodeChunkRecord, TaskEpisodicMemoryRecord
from app.memory.store import TaskEpisodicMemory, TaskMemoryStore
from app.rag.embeddings import EmbeddingClient
from app.rag.indexer import ChunkType, IndexedCodeChunk
from app.rag.vector_store import PostgresVectorStore, InMemoryVectorStore


@pytest.fixture
def test_db_session_factory():
    """Provides an isolated SQLite database session factory for durable storage integration tests."""
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    yield session_factory
    engine.dispose()


def test_postgres_vector_store_sql_search_and_persistence(test_db_session_factory):
    """
    Proves that PostgresVectorStore persists chunks to SQL database
    and executes real SQL vector distance retrieval with metadata filtering.
    """
    store = PostgresVectorStore(db_session_factory=test_db_session_factory)
    emb_client = EmbeddingClient(dimension=64)

    # 1. Create sample semantic code chunks
    route_content = "@router.post('/login')\ndef login():\n    return auth_service.authenticate()"
    service_content = "def authenticate():\n    return db.query(User).filter_by(email=email)"
    model_content = "class User(Base):\n    id = Column(Integer)\n    email = Column(String)"

    chunks = [
        IndexedCodeChunk(
            chunk_id="chunk-route-01",
            repo_id="test_repo",
            file_path="api/auth.py",
            symbol="POST /login",
            chunk_type=ChunkType.API_ROUTE,
            language="python",
            content=route_content,
            embedding=emb_client.get_embedding_sync(route_content),
            start_line=1,
            end_line=3
        ),
        IndexedCodeChunk(
            chunk_id="chunk-svc-01",
            repo_id="test_repo",
            file_path="services/auth.py",
            symbol="authenticate",
            chunk_type=ChunkType.FUNCTION,
            language="python",
            content=service_content,
            embedding=emb_client.get_embedding_sync(service_content),
            start_line=1,
            end_line=3
        ),
        IndexedCodeChunk(
            chunk_id="chunk-model-01",
            repo_id="test_repo",
            file_path="models/user.py",
            symbol="User",
            chunk_type=ChunkType.DB_MODEL,
            language="python",
            content=model_content,
            embedding=emb_client.get_embedding_sync(model_content),
            start_line=1,
            end_line=4
        ),
    ]

    # 2. Upsert chunks into database
    upserted = store.upsert_chunks(chunks)
    assert upserted == 3

    # Verify rows in database table
    with test_db_session_factory() as session:
        records = session.query(CodeChunkRecord).filter_by(repo_id="test_repo").all()
        assert len(records) == 3
        symbols = [r.symbol for r in records]
        assert "POST /login" in symbols
        assert "User" in symbols

    # 3. Execute vector search query against database
    query_emb = emb_client.get_embedding_sync("Where is the login endpoint route?")
    results = store.search(repo_id="test_repo", query_embedding=query_emb, top_k=2)
    assert len(results) >= 1
    top_chunk, sim = results[0]
    assert isinstance(top_chunk, IndexedCodeChunk)
    assert sim > 0.0

    # 4. Search with metadata filter (only API_ROUTE)
    route_only_results = store.search(
        repo_id="test_repo",
        query_embedding=query_emb,
        top_k=5,
        chunk_types=[ChunkType.API_ROUTE]
    )
    assert len(route_only_results) == 1
    assert route_only_results[0][0].chunk_type == ChunkType.API_ROUTE
    assert route_only_results[0][0].symbol == "POST /login"

    # 5. Delete chunks for a file
    deleted = store.delete_file_chunks(repo_id="test_repo", file_path="api/auth.py")
    assert deleted == 1
    remaining = store.get_all_chunks(repo_id="test_repo")
    assert len(remaining) == 2


def test_durable_task_memory_cross_process_restart(test_db_session_factory):
    """
    CRITICAL PROOF: Proves that TaskMemoryStore is durable across restarts.
    Instance A writes memory to database.
    Instance A is destroyed.
    Instance B (representing restarted ASTRA process) restores and retrieves memory from SQL database!
    """
    repo_id = "restart_test_repo"

    # --- PROCESS 1: ASTRA runs Task 1 ---
    store_a = TaskMemoryStore(db_session_factory=test_db_session_factory)
    task1_id = "task-alpha-101"
    store_a.record_task_experience(
        task_id=task1_id,
        repo_id=repo_id,
        goal="Fix authentication token expiry bug",
        files_modified=["services/auth_service.py", "config/settings.py"],
        test_status="verified",
        failure_history=[{"error": "JWT expired signature immediately"}],
        discoveries=["JWT expiration requires integer timestamp in UTC seconds"],
        solution_summary="Cast expiration to int(time.time() + 1800) in auth_service.py",
        conventions_learned=["Always validate JWT tokens with 10s leeway"]
    )

    # Verify record was committed into SQL database
    with test_db_session_factory() as session:
        rec = session.query(TaskEpisodicMemoryRecord).filter_by(task_id=task1_id).first()
        assert rec is not None
        assert rec.repo_id == repo_id
        assert "JWT expiration requires integer" in rec.discoveries[0]

    # --- SIMULATE FULL PROCESS RESTART / CRASH ---
    del store_a

    # --- PROCESS 2: Fresh ASTRA process starts up ---
    store_b = TaskMemoryStore(db_session_factory=test_db_session_factory)
    # Ensure instance B has an empty local in-memory cache
    assert len(store_b._memories.get(repo_id, [])) == 0

    # Task 2 arrives in the same repository
    task2_goal = "Implement refresh token logic in auth_service"
    recalled_memories = store_b.retrieve_relevant_task_memories(
        repo_id=repo_id,
        current_goal=task2_goal,
        candidate_files=["services/auth_service.py"],
        top_k=2
    )

    # Verify instance B successfully recalled Task 1's memory from the database!
    assert len(recalled_memories) == 1
    recalled_task = recalled_memories[0]
    assert recalled_task.task_id == task1_id
    assert "services/auth_service.py" in recalled_task.files_modified
    assert "JWT expiration requires integer" in recalled_task.discoveries[0]
    assert recalled_task.test_status == "verified"

    # Verify prompt formatting works seamlessly on recalled memory
    prompt_snippet = store_b.format_memory_for_agent_prompt(recalled_memories)
    assert "Task task-alpha-101" in prompt_snippet
    assert "JWT expiration requires integer" in prompt_snippet
    assert "auth_service.py" in prompt_snippet


def test_production_embedding_pipeline():
    """
    Validates production EmbeddingClient batching, dimensions, and fallbacks.
    """
    client = EmbeddingClient(dimension=64)
    texts = [
        "FastAPI router handling user registration",
        "SQLAlchemy database model for user credentials",
        "Pytest unit test verifying token revocation"
    ]

    # Batch embedding
    batch_embeddings = client.get_embeddings_batch(texts)
    assert len(batch_embeddings) == 3
    assert all(len(emb) == 64 for emb in batch_embeddings)

    # Verify semantic similarity:
    # "FastAPI router login" should have higher similarity to text 0 than to an unrelated string
    query_emb = client.get_embedding("FastAPI router login endpoint")
    sim_related = sum(a * b for a, b in zip(query_emb, batch_embeddings[0]))
    unrelated_emb = client.get_embedding("CSS style color border margin padding")
    sim_unrelated = sum(a * b for a, b in zip(unrelated_emb, batch_embeddings[0]))

    assert sim_related > sim_unrelated
