from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

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
    architecture_summary = Column(JSONB, nullable=True)
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
    created_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    final_report = Column(JSONB, nullable=True)

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
    arguments = Column(JSONB, nullable=True)
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
    arguments = Column(JSONB, nullable=True)
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
    event_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord", back_populates="events")


class MemoryEntryRecord(Base):
    __tablename__ = "memory_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String, nullable=True)
    key = Column(String, nullable=False)
    value = Column(JSONB, nullable=False)
    category = Column(String, default="architecture")  # architecture, convention, issue, past_run
    created_at = Column(DateTime(timezone=True), default=utc_now)
