from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, asc, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.config import settings
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
    Proves that PostgresVectorStore persists chunks to SQL database with the production
    dimension (settings.EMBEDDING_DIMENSION = 1536) and executes SQL vector retrieval
    with metadata filtering.
    """
    store = PostgresVectorStore(db_session_factory=test_db_session_factory)
    emb_client = EmbeddingClient(dimension=settings.EMBEDDING_DIMENSION)

    # 1. Create sample semantic code chunks with exact production dimension (1536)
    route_content = "@router.post('/login')\ndef login():\n    return auth_service.authenticate()"
    service_content = "def authenticate():\n    return db.query(User).filter_by(email=email)"
    model_content = "class User(Base):\n    id = Column(Integer)\n    email = Column(String)"

    route_emb = emb_client.get_embedding_sync(route_content)
    service_emb = emb_client.get_embedding_sync(service_content)
    model_emb = emb_client.get_embedding_sync(model_content)

    assert len(route_emb) == settings.EMBEDDING_DIMENSION == 1536
    assert len(service_emb) == settings.EMBEDDING_DIMENSION == 1536
    assert len(model_emb) == settings.EMBEDDING_DIMENSION == 1536

    chunks = [
        IndexedCodeChunk(
            chunk_id="chunk-route-01",
            repo_id="test_repo",
            file_path="api/auth.py",
            symbol="POST /login",
            chunk_type=ChunkType.API_ROUTE,
            language="python",
            content=route_content,
            embedding=route_emb,
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
            embedding=service_emb,
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
            embedding=model_emb,
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
    assert len(query_emb) == 1536
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


def test_postgresql_pgvector_sql_compilation_and_hnsw_ddl():
    """
    CRITICAL ARCHITECTURAL PROOF:
    Proves that under the PostgreSQL dialect, SQLAlchemy compiles:
    1. CodeChunkRecord.embedding.cosine_distance(query_embedding) directly to the native pgvector `<=>` operator.
    2. The HNSW index compiles to `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`.
    """
    query_emb = [0.0] * settings.EMBEDDING_DIMENSION
    distance_expr = CodeChunkRecord.embedding.cosine_distance(query_emb)
    query = (
        select(CodeChunkRecord, distance_expr.label("distance"))
        .filter(CodeChunkRecord.repo_id == "test_repo")
        .order_by(asc("distance"))
    )

    compiled_sql = str(query.compile(dialect=postgresql.dialect()))
    assert "<=>" in compiled_sql, f"Expected pgvector '<=>' operator in compiled SQL, got: {compiled_sql}"
    assert "ORDER BY distance ASC" in compiled_sql

    # Verify HNSW index DDL compilation
    hnsw_index = next(idx for idx in CodeChunkRecord.__table__.indexes if "hnsw" in idx.name)
    compiled_ddl = str(CreateIndex(hnsw_index).compile(dialect=postgresql.dialect()))
    assert "USING hnsw" in compiled_ddl
    assert "vector_cosine_ops" in compiled_ddl


def test_real_postgresql_pgvector_live_execution():
    """
    LIVE POSTGRESQL + PGVECTOR INTEGRATION TEST:
    Executes actual end-to-end vector queries on PostgreSQL with the pgvector extension and HNSW index.
    Automatically skipped if PostgreSQL is not available in the current environment.
    """
    pg_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not pg_url or not ("postgresql" in pg_url or "postgres" in pg_url):
        pytest.skip("PostgreSQL not configured. Set TEST_DATABASE_URL or DATABASE_URL to run live pgvector tests.")

    try:
        engine = create_engine(pg_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    except Exception as exc:
        pytest.skip(f"Live PostgreSQL server unavailable: {exc}")

    try:
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        store = PostgresVectorStore(db_session_factory=session_factory)
        emb_client = EmbeddingClient(dimension=settings.EMBEDDING_DIMENSION)

        chunk_id = f"live-pg-chunk-{os.getpid()}"
        repo_id = "live_pg_test_repo"
        content = "def authenticate_user_pgvector(user, token): return True"
        emb = emb_client.get_embedding_sync(content)

        chunk = IndexedCodeChunk(
            chunk_id=chunk_id,
            repo_id=repo_id,
            file_path="auth/pg_test.py",
            symbol="authenticate_user_pgvector",
            chunk_type=ChunkType.FUNCTION,
            language="python",
            content=content,
            embedding=emb,
            start_line=1,
            end_line=2,
        )

        store.upsert_chunks([chunk])
        search_res = store.search(repo_id=repo_id, query_embedding=emb, top_k=1)
        assert len(search_res) >= 1
        assert search_res[0][0].chunk_id == chunk_id

        # Clean up test rows
        store.delete_file_chunks(repo_id=repo_id, file_path="auth/pg_test.py")
    finally:
        engine.dispose()


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

    # Instance B has an EMPTY in-memory cache
    assert task1_id not in store_b._in_memory_cache

    # When queried, Instance B fetches the memory directly from the SQL database
    recalled_memories = store_b.retrieve_relevant_task_memories(
        repo_id=repo_id,
        current_goal="Add token refresh logic to authentication service",
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
    Validates production EmbeddingClient batching, dimensions (1536), and semantic properties.
    """
    client = EmbeddingClient(dimension=settings.EMBEDDING_DIMENSION)
    texts = [
        "FastAPI router handling user registration",
        "SQLAlchemy database model for user credentials",
        "Pytest unit test verifying token revocation"
    ]

    # Batch embedding with production dimension 1536
    batch_embeddings = client.get_embeddings_batch(texts)
    assert len(batch_embeddings) == 3
    assert all(len(emb) == settings.EMBEDDING_DIMENSION == 1536 for emb in batch_embeddings)

    # Verify semantic similarity:
    # "FastAPI router login" should have higher similarity to text 0 than to an unrelated string
    query_emb = client.get_embedding("FastAPI router login endpoint")
    assert len(query_emb) == 1536
    sim_related = sum(a * b for a, b in zip(query_emb, batch_embeddings[0]))
    unrelated_emb = client.get_embedding("CSS style color border margin padding")
    assert len(unrelated_emb) == 1536
    sim_unrelated = sum(a * b for a, b in zip(unrelated_emb, batch_embeddings[0]))

    assert sim_related > sim_unrelated
