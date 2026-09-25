from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

from app.config import settings

JSONType = JSON().with_variant(JSONB(), "postgresql")
Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRecord(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    repositories = relationship("RepositoryRecord", back_populates="project", cascade="all, delete-orphan")


class RepositoryRecord(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    name = Column(String, nullable=False)
    url_or_path = Column(String, nullable=False)
    default_branch = Column(String, default="main")
    architecture_summary = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    project = relationship("ProjectRecord", back_populates="repositories")
    tasks = relationship("TaskRecord", back_populates="repository", cascade="all, delete-orphan")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: f"task-{uuid.uuid4().hex[:8]}")
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=True)
    goal = Column(Text, nullable=False)
    status = Column(String, default="created")  # created, running, paused, verified, failed, cancelled
    verification_status = Column(String, default="pending")  # pending, verified, failed, uncertain
    workspace_path = Column(String, nullable=True)
    iterations = Column(Integer, default=0)
    retries = Column(Integer, default=0)
    timeout_seconds = Column(Integer, default=1800)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    final_report = Column(JSONType, nullable=True)
    error_message = Column(Text, nullable=True)

    repository = relationship("RepositoryRecord", back_populates="tasks")
    steps = relationship("TaskStepRecord", back_populates="task", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCallRecord", back_populates="task", cascade="all, delete-orphan")
    file_changes = relationship("FileChangeRecord", back_populates="task", cascade="all, delete-orphan")
    test_runs = relationship("TestRunRecord", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("ApprovalRecord", back_populates="task", cascade="all, delete-orphan")
    events = relationship("AgentEventRecord", back_populates="task", cascade="all, delete-orphan")


class TaskStepRecord(Base):
    __tablename__ = "task_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")
    result = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord", back_populates="steps")


class ToolCallRecord(Base):
    __tablename__ = "tool_calls"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(JSONType, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord", back_populates="tool_calls")


class FileChangeRecord(Base):
    __tablename__ = "file_changes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    file_path = Column(String, nullable=False)
    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    diff = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord", back_populates="file_changes")


class TestRunRecord(Base):
    __tablename__ = "test_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    status = Column(String, nullable=False)  # passed, failed, error
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    output = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord", back_populates="test_runs")


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(JSONType, nullable=True)
    risk_level = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    reviewer_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("TaskRecord", back_populates="approvals")


class AgentEventRecord(Base):
    __tablename__ = "agent_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    sequence_id = Column(Integer, default=1)
    event_type = Column(String, nullable=False)
    source = Column(String, default="system")
    message = Column(Text, nullable=False)
    payload = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord", back_populates="events")


class MemoryEntryRecord(Base):
    __tablename__ = "memory_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String, nullable=True)
    key = Column(String, nullable=False)
    value = Column(JSONType, nullable=False)
    category = Column(String, default="architecture")  # architecture, convention, issue, past_run
    created_at = Column(DateTime(timezone=True), default=utc_now)


from pgvector.sqlalchemy import Vector
from sqlalchemy import Index


class CodeChunkRecord(Base):
    __tablename__ = "code_chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id = Column(String, index=True, nullable=False)
    file_path = Column(String, index=True, nullable=False)
    symbol = Column(String, nullable=True)
    chunk_type = Column(String, index=True, nullable=False)  # file_header, class, function, api_route, db_model, test, config, documentation
    language = Column(String, default="python")
    content = Column(Text, nullable=False)
    commit_sha = Column(String, nullable=True)
    start_line = Column(Integer, default=1)
    end_line = Column(Integer, default=1)
    metadata_json = Column(JSONType, nullable=True)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index(
            "ix_code_chunks_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )



class TaskEpisodicMemoryRecord(Base):
    __tablename__ = "task_episodic_memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id = Column(String, index=True, nullable=False)
    task_id = Column(String, index=True, nullable=False)
    goal = Column(Text, nullable=False)
    modified_files = Column(JSONType, nullable=True)
    test_status = Column(String, default="verified")
    discoveries = Column(JSONType, nullable=True)
    solution_summary = Column(Text, nullable=True)
    conventions_learned = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class EngineeringDecisionRecord(Base):
    __tablename__ = "engineering_decisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)  # architecture, problematic_module, proven_fix, convention, rule
    subject = Column(String, nullable=False)  # e.g. "auth/jwt.py" or "FastAPI Pydantic v2"
    decision = Column(Text, nullable=False)  # detailed explanation or rule
    evidence = Column(JSONType, nullable=True)  # rationale, related tasks, code patterns
    created_at = Column(DateTime(timezone=True), default=utc_now)


class CheckpointRecord(Base):
    __tablename__ = "langgraph_checkpoints"

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default="")
    checkpoint_id = Column(String, primary_key=True)
    parent_checkpoint_id = Column(String, nullable=True)
    checkpoint_type = Column(String, default="msgpack")
    checkpoint_data = Column(Text, nullable=False)  # base64 encoded JsonPlus payload
    metadata_type = Column(String, default="msgpack")
    metadata_data = Column(Text, nullable=True)      # base64 encoded JsonPlus payload
    created_at = Column(DateTime(timezone=True), default=utc_now)


class CheckpointBlobRecord(Base):
    __tablename__ = "langgraph_checkpoint_blobs"

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default="")
    channel = Column(String, primary_key=True)
    version = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    blob_data = Column(Text, nullable=False)        # base64 encoded raw data
    created_at = Column(DateTime(timezone=True), default=utc_now)


class CheckpointWriteRecord(Base):
    __tablename__ = "langgraph_checkpoint_writes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String, nullable=False, index=True)
    checkpoint_ns = Column(String, default="", nullable=False)
    checkpoint_id = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=False)
    idx = Column(Integer, nullable=False)
    channel = Column(String, nullable=False)
    type = Column(String, nullable=False)
    value_data = Column(Text, nullable=False)       # base64 encoded JsonPlus payload
    task_path = Column(String, default="")
    created_at = Column(DateTime(timezone=True), default=utc_now)


