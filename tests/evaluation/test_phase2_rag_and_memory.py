from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from app.agents.graph import finalize_task
from app.agents.planner import plan_task
from app.agents.state import AstraAgentState
from app.agents.supervisor import load_repository_context
from app.memory.store import TaskEpisodicMemory, TaskMemoryStore
from app.rag.context_builder import ContextBuilder
from app.rag.embeddings import EmbeddingClient
from app.rag.incremental import IncrementalIndexer
from app.rag.indexer import ChunkType, RepositorySemanticIndexer, SemanticCodeChunker
from app.rag.retrieval import SemanticRetriever
from app.rag.vector_store import InMemoryVectorStore
from app.runtime.workspace import WorkspaceManager
from app.verification.tests import TestRunner


def setup_unfamiliar_auth_repository(repo_path: Path):
    """
    Creates a realistic multi-layered repository with:
    - API router layer (FastAPI)
    - Service / Business logic layer
    - Database ORM model layer
    - Configuration
    - Unit tests
    - Documentation
    """
    (repo_path / "api").mkdir(parents=True, exist_ok=True)
    (repo_path / "services").mkdir(parents=True, exist_ok=True)
    (repo_path / "models").mkdir(parents=True, exist_ok=True)
    (repo_path / "config").mkdir(parents=True, exist_ok=True)
    (repo_path / "tests").mkdir(parents=True, exist_ok=True)

    # 1. Models Layer
    model_code = (
        "from sqlalchemy.orm import declarative_base\n"
        "from sqlalchemy import Column, Integer, String\n\n"
        "Base = declarative_base()\n\n"
        "class User(Base):\n"
        "    __tablename__ = 'users'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    email = Column(String, unique=True, nullable=False)\n"
        "    hashed_password = Column(String, nullable=False)\n"
    )
    (repo_path / "models" / "user.py").write_text(model_code, encoding="utf-8")

    # 2. Config Layer
    config_code = (
        "class AuthSettings:\n"
        "    JWT_SECRET = 'super-secret-key'\n"
        "    ALGORITHM = 'HS256'\n"
        "    ACCESS_TOKEN_EXPIRE_MINUTES = 30\n"
    )
    (repo_path / "config" / "settings.py").write_text(config_code, encoding="utf-8")

    # 3. Service Layer
    service_code = (
        "import time\n"
        "from models.user import User\n"
        "from config.settings import AuthSettings\n\n"
        "def authenticate_user(email: str, password: str) -> dict:\n"
        "    \"\"\"Authenticates user against User model and returns tokens.\"\"\"\n"
        "    if email == 'admin@example.com' and password == 'secret123':\n"
        "        return {'id': 1, 'email': email}\n"
        "    return None\n\n"
        "def create_access_token(user_id: int) -> str:\n"
        "    \"\"\"Generates JWT token with expiration.\"\"\"\n"
        "    expires = time.time() + (AuthSettings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)\n"
        "    return f'token-{user_id}-{int(expires)}'\n\n"
        "def verify_token(token: str) -> bool:\n"
        "    parts = token.split('-')\n"
        "    if len(parts) == 3:\n"
        "        exp = int(parts[2])\n"
        "        return time.time() < exp\n"
        "    return False\n"
    )
    (repo_path / "services" / "auth_service.py").write_text(service_code, encoding="utf-8")

    # 4. API Layer
    api_code = (
        "from fastapi import APIRouter, HTTPException\n"
        "from services.auth_service import authenticate_user, create_access_token\n\n"
        "router = APIRouter(prefix='/auth')\n\n"
        "@router.post('/login')\n"
        "def login_endpoint(payload: dict):\n"
        "    user = authenticate_user(payload.get('email'), payload.get('password'))\n"
        "    if not user:\n"
        "        raise HTTPException(status_code=401, detail='Invalid credentials')\n"
        "    token = create_access_token(user['id'])\n"
        "    return {'access_token': token, 'token_type': 'bearer'}\n"
    )
    (repo_path / "api" / "auth.py").write_text(api_code, encoding="utf-8")

    # 5. Tests
    test_code = (
        "from services.auth_service import authenticate_user, create_access_token, verify_token\n\n"
        "def test_authenticate_success():\n"
        "    user = authenticate_user('admin@example.com', 'secret123')\n"
        "    assert user is not None\n"
        "    assert user['email'] == 'admin@example.com'\n\n"
        "def test_verify_token_valid():\n"
        "    token = create_access_token(1)\n"
        "    assert verify_token(token) is True\n"
    )
    (repo_path / "tests" / "test_auth.py").write_text(test_code, encoding="utf-8")

    # 6. Requirements
    (repo_path / "requirements.txt").write_text("fastapi\nsqlalchemy\npytest\n", encoding="utf-8")

    # 7. Documentation
    readme_code = (
        "# Enterprise Authentication Service\n\n"
        "Architecture overview:\n"
        "Client -> FastAPI Router (/auth/login) -> auth_service -> User DB Model.\n"
    )
    (repo_path / "README.md").write_text(readme_code, encoding="utf-8")


def test_benchmark_pillar_1_repository_indexing_and_classification():
    """Benchmark 1: Validates rich semantic chunking across all code layers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        setup_unfamiliar_auth_repository(repo_path)

        chunks = RepositorySemanticIndexer.index_repository(repo_path, repo_id="auth_repo")
        assert len(chunks) >= 6

        chunk_types = {c.chunk_type for c in chunks}
        assert ChunkType.API_ROUTE in chunk_types
        assert ChunkType.DB_MODEL in chunk_types
        assert ChunkType.FUNCTION in chunk_types
        assert ChunkType.TEST in chunk_types
        assert ChunkType.DOCUMENTATION in chunk_types

        # Verify route chunk metadata
        route_chunks = [c for c in chunks if c.chunk_type == ChunkType.API_ROUTE]
        assert len(route_chunks) >= 1
        assert "login" in route_chunks[0].symbol.lower()
        assert route_chunks[0].metadata.get("http_method") == "POST"
        assert "authenticate_user" in route_chunks[0].metadata.get("calls", [])

        # Verify model chunk
        model_chunks = [c for c in chunks if c.chunk_type == ChunkType.DB_MODEL]
        assert any(m.symbol == "User" for m in model_chunks)


def test_benchmark_pillar_2_vector_search_and_call_chain_synthesis():
    """
    Benchmark 2: Validates semantic retrieval of execution chain:
    'Where is authentication handled and how does login flow from API -> service -> database?'
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        setup_unfamiliar_auth_repository(repo_path)

        v_store = InMemoryVectorStore()
        emb_client = EmbeddingClient()
        chunks = RepositorySemanticIndexer.index_repository(repo_path, repo_id="auth_chain_repo")
        for c in chunks:
            c.embedding = emb_client.get_embedding_sync(c.content)
        v_store.upsert_chunks(chunks)

        retriever = SemanticRetriever(vector_store=v_store, embedding_client=emb_client)
        query = "Where is authentication handled and how does login flow from API to service to database?"

        res = retriever.retrieve(repo_id="auth_chain_repo", query=query, top_k=5)
        assert len(res.chunks) > 0
        assert res.flow_chain is not None

        # Verify exact chain resolution
        chain = res.flow_chain
        assert chain.entrypoint_route is not None
        assert "login" in chain.entrypoint_route.symbol.lower()

        assert chain.service_function is not None
        assert "authenticate_user" in chain.service_function.symbol

        assert chain.database_model is not None
        assert chain.database_model.symbol == "User"

        assert "API Route:" in chain.flow_summary
        assert "Service:" in chain.flow_summary
        assert "DB Model: User" in chain.flow_summary


def test_benchmark_pillar_3_incremental_indexing_efficiency():
    """
    Benchmark 3: Ensures ONLY modified files are re-parsed and re-embedded,
    preventing costly full-repository re-indexing.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        setup_unfamiliar_auth_repository(repo_path)

        v_store = InMemoryVectorStore()
        emb_client = EmbeddingClient()
        chunks = RepositorySemanticIndexer.index_repository(repo_path, repo_id="incremental_repo")
        for c in chunks:
            c.embedding = emb_client.get_embedding_sync(c.content)
        v_store.upsert_chunks(chunks)
        initial_chunk_count = len(v_store.get_all_chunks("incremental_repo"))

        # Modify only services/auth_service.py
        service_file = repo_path / "services" / "auth_service.py"
        service_file.write_text(
            service_file.read_text(encoding="utf-8") + "\ndef revoke_token(token: str) -> bool:\n    return True\n",
            encoding="utf-8"
        )

        indexer = IncrementalIndexer(vector_store=v_store, embedding_client=emb_client)
        stats = indexer.index_changes(
            repo_path=repo_path,
            repo_id="incremental_repo",
            explicit_changed_files=["services/auth_service.py"]
        )

        assert stats["modified_files"] == ["services/auth_service.py"]
        assert stats["chunks_embedded"] > 0
        # Total chunks should have increased by 1 (the new revoke_token function)
        new_total = len(v_store.get_all_chunks("incremental_repo"))
        assert new_total == initial_chunk_count + 1


def test_benchmark_pillar_4_and_5_multi_turn_task_memory_continuity():
    """
    Benchmark 4 & 5:
    Task 1 fixes an issue in auth_service and logs discoveries into TaskMemoryStore.
    Task 2 receives a new task on authentication, loads Task 1's memory,
    and grounds the dynamic plan in prior findings!
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        setup_unfamiliar_auth_repository(repo_path)

        repo_id = "multi_turn_auth_repo"

        # --- TASK 1: Fix JWT expiry ---
        task1_id = "task-auth-001"
        mem_store = TaskMemoryStore()

        # Simulate Task 1 finding and resolving JWT expiry bug
        task1_discovery = "JWT expiry timestamp must use integer seconds, not float or milliseconds."
        task1_solution = "Updated expires calculation in services/auth_service.py to int(expires)."
        mem_store.record_task_experience(
            task_id=task1_id,
            repo_id=repo_id,
            goal="Fix JWT token expiration handling in auth_service",
            files_modified=["services/auth_service.py"],
            test_status="verified",
            discoveries=[task1_discovery],
            solution_summary=task1_solution,
            conventions_learned=["Always test token expiration boundary conditions"]
        )

        # --- TASK 2: Add Refresh Token ---
        task2_id = "task-auth-002"
        task2_goal = "Add refresh token endpoint to authentication service and router"

        # Retrieve relevant memories for Task 2
        relevant_memories = mem_store.retrieve_relevant_task_memories(
            repo_id=repo_id,
            current_goal=task2_goal,
            candidate_files=["services/auth_service.py", "api/auth.py"]
        )

        assert len(relevant_memories) >= 1
        top_mem = relevant_memories[0]
        assert top_mem.task_id == task1_id
        assert task1_discovery in top_mem.discoveries

        # Test Planning with Memory Context
        state_task2: AstraAgentState = {
            "task_id": task2_id,
            "repository_id": repo_id,
            "user_goal": task2_goal,
            "workspace_path": str(repo_path),
            "repository_context": {
                "files": ["api/auth.py", "services/auth_service.py", "models/user.py"],
                "summary": {"backend": "FastAPI", "test_command": "pytest"},
                "flow_chain": {
                    "summary": "API Route: POST /auth/login -> Service: authenticate_user() -> DB Model: User"
                },
                "past_memories": [top_mem.to_dict()]
            },
            "iteration_count": 0,
            "retry_count": 0,
        }

        plan_result = plan_task(state_task2)
        plan_steps = plan_result["plan"]

        # Assert Step 1 references the architectural flow chain
        assert any("API Route:" in s.get("flow_chain", "") for s in plan_steps if s.get("flow_chain"))

        # Assert Step 2 reflects Task 1's memory
        memory_steps = [s for s in plan_steps if s.get("past_task_id") == task1_id]
        assert len(memory_steps) == 1
        assert "JWT expiry" in memory_steps[0]["description"]


def test_benchmark_end_to_end_unfamiliar_repo_rag_and_memory_execution():
    """
    Ultimate Phase 2 Success Criterion:
    ASTRA receives a task in an unfamiliar repository:
    1. Retrieves relevant architecture/code context (API -> Service -> DB Model).
    2. Makes a grounded plan.
    3. Executes the fix in an isolated workspace.
    4. Autonomous verification engine verifies the changes with empirical evidence.
    5. Finalizes task and records episodic memory.
    6. Next task in same repo automatically retrieves prior task findings and plans accordingly!
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_mgr = WorkspaceManager(base_dir=tmpdir)
        ws = ws_mgr.create_workspace(task_id="e2e_unfamiliar_repo_task")
        setup_unfamiliar_auth_repository(ws.path)

        repo_id = "e2e_unfamiliar_auth_service"

        # Introduce a bug into auth_service.py that breaks verification
        buggy_service = (ws.path / "services" / "auth_service.py").read_text(encoding="utf-8")
        buggy_service = buggy_service.replace(
            "return time.time() < exp",
            "return False  # BUG: always fails verification"
        )
        (ws.path / "services" / "auth_service.py").write_text(buggy_service, encoding="utf-8")

        # --- STEP 1: Task 1 Context Loading & Planning ---
        state_t1: AstraAgentState = {
            "task_id": "task_1_fix_token",
            "repository_id": repo_id,
            "user_goal": "Find and fix token verification failure in auth_service and verify with pytest",
            "workspace_path": str(ws.path),
            "iteration_count": 0,
            "retry_count": 0,
            "observations": [],
            "failure_history": [],
            "errors": [],
        }

        # Load deep repository context with Semantic RAG
        context_result = load_repository_context(state_t1)
        state_t1.update(context_result)

        assert "flow_chain" in state_t1["repository_context"]
        assert state_t1["repository_context"]["summary"]["backend"] == "FastAPI"

        # Plan Task 1
        plan_t1 = plan_task(state_t1)
        state_t1.update(plan_t1)
        assert len(state_t1["plan"]) >= 4

        # Initial verification fails as expected
        initial_test_report = TestRunner.run_tests(ws.path)
        assert initial_test_report.status == "failed"
        assert initial_test_report.failed >= 1

        # --- STEP 2: Agent fixes the bug ---
        fixed_service = (ws.path / "services" / "auth_service.py").read_text(encoding="utf-8")
        fixed_service = fixed_service.replace(
            "return False  # BUG: always fails verification",
            "return time.time() < exp"
        )
        (ws.path / "services" / "auth_service.py").write_text(fixed_service, encoding="utf-8")

        # Autonomous Verification Engine runs pytest
        verified_test_report = TestRunner.run_tests(ws.path)
        assert verified_test_report.status == "passed"
        assert verified_test_report.passed == 2
        assert verified_test_report.failed == 0

        state_t1["verification_status"] = "verified"
        state_t1["test_results"] = verified_test_report.to_dict()
        state_t1["files_changed"] = ["services/auth_service.py"]
        state_t1["failure_history"] = [{"error": "AssertionError in test_verify_token_valid"}]

        # Finalize Task 1 -> Saves episodic memory and triggers incremental indexing
        final_t1 = finalize_task(state_t1)
        assert final_t1["final_result"]["status"] == "verified"

        # --- STEP 3: Task 2 in the same repository ---
        state_t2: AstraAgentState = {
            "task_id": "task_2_add_revocation",
            "repository_id": repo_id,
            "user_goal": "Add token revocation logic to auth_service and route",
            "workspace_path": str(ws.path),
            "iteration_count": 0,
            "retry_count": 0,
            "observations": [],
            "failure_history": [],
            "errors": [],
        }

        # Load context for Task 2
        context_t2 = load_repository_context(state_t2)
        state_t2.update(context_t2)

        # Verify Task 2 retrieved Task 1's memory
        memories = state_t2["repository_context"].get("past_memories", [])
        assert len(memories) >= 1
        assert any(m["task_id"] == "task_1_fix_token" for m in memories)

        # Plan Task 2 -> grounded in Task 1's experience
        plan_t2 = plan_task(state_t2)
        state_t2.update(plan_t2)

        past_steps = [s for s in state_t2["plan"] if s.get("past_task_id") == "task_1_fix_token"]
        assert len(past_steps) == 1
        assert "task_1_fix_token" in past_steps[0]["description"]

        ws.cleanup()

