from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.logging import logger


@dataclass
class ConversationMessage:
    id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    task_id: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "task_id": self.task_id,
            "files_changed": self.files_changed,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentSession:
    id: str
    title: str
    repository_path: Optional[str] = None
    workspace_path: Optional[str] = None
    active_branch: str = "main"
    model: str = "ollama/qwen2.5-coder:3b"
    mode: str = "autonomous"
    messages: List[ConversationMessage] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    context_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "repository_path": self.repository_path,
            "workspace_path": self.workspace_path,
            "active_branch": self.active_branch,
            "model": self.model,
            "mode": self.mode,
            "messages": [m.to_dict() for m in self.messages],
            "tasks": self.tasks,
            "context_summary": self.context_summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ConversationSessionManager:
    """
    ASTRA Conversational Agent Session Manager (P5).
    Maintains persistent conversational context, shared isolated workspace state,
    and history across sequential turns of user instructions.
    """

    def __init__(self):
        self._sessions: Dict[str, AgentSession] = {}
        self._task_to_session: Dict[str, str] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        repository_path: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[str] = "autonomous",
        initial_title: Optional[str] = None,
    ) -> AgentSession:
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        title = initial_title or "New Autonomous Engineering Session"

        selected_model = model or "ollama/qwen2.5-coder:3b"
        if selected_model in ["ollama", "local", "qwen"]:
            selected_model = "ollama/qwen2.5-coder:3b"
        elif selected_model in ["gemini", "cloud"]:
            selected_model = "gemini/gemini-2.5-flash"

        session = AgentSession(
            id=session_id,
            title=title,
            repository_path=repository_path,
            model=selected_model,
            mode=mode or "autonomous",
        )

        with self._lock:
            self._sessions[session_id] = session

        logger.info(f"Created conversation session {session_id} for repo: {repository_path}")
        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_session_by_task(self, task_id: str) -> Optional[AgentSession]:
        with self._lock:
            sid = self._task_to_session.get(task_id)
            if sid:
                return self._sessions.get(sid)
            return None

    def list_sessions(self) -> List[AgentSession]:
        with self._lock:
            return sorted(
                list(self._sessions.values()),
                key=lambda s: s.updated_at,
                reverse=True,
            )

    def add_user_message(
        self,
        session_id: str,
        content: str,
        task_id: Optional[str] = None,
    ) -> ConversationMessage:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(f"Session {session_id} not found")

            # Update session title from first user message if default
            if len(session.messages) == 0 or session.title.startswith("New Autonomous"):
                session.title = content[:60] + ("..." if len(content) > 60 else "")

            msg = ConversationMessage(
                id=str(uuid.uuid4()),
                role="user",
                content=content,
                task_id=task_id,
            )
            session.messages.append(msg)
            if task_id:
                session.tasks.append(task_id)
                self._task_to_session[task_id] = session_id

            session.updated_at = datetime.now(timezone.utc).isoformat()
            return msg

    def record_agent_completion(
        self,
        task_id: str,
        summary: str,
        files_changed: Optional[List[str]] = None,
    ) -> Optional[ConversationMessage]:
        with self._lock:
            session_id = self._task_to_session.get(task_id)
            if not session_id or session_id not in self._sessions:
                return None

            session = self._sessions[session_id]
            files = files_changed or []

            msg = ConversationMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=summary,
                task_id=task_id,
                files_changed=files,
            )
            session.messages.append(msg)

            # Update cumulative context summary
            prev_summary = session.context_summary
            new_entry = f"Turn on {datetime.now(timezone.utc).strftime('%H:%M:%S')}: {summary[:120]}"
            if files:
                new_entry += f" (Touched: {', '.join(files[:3])})"
            session.context_summary = f"{prev_summary}\n- {new_entry}".strip()
            session.updated_at = datetime.now(timezone.utc).isoformat()

            return msg

    def build_contextual_prompt(self, session_id: str, current_goal: str) -> str:
        """
        Builds a rich conversational prompt incorporating past turns, previous decisions,
        and files modified in this session so the agent understands continuous context.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or len(session.messages) <= 1:
                return current_goal

            history_parts = ["PREVIOUS CONVERSATION CONTEXT IN THIS SESSION:"]
            # Include up to last 6 messages
            recent_msgs = session.messages[:-1][-6:]
            for m in recent_msgs:
                role_label = "User" if m.role == "user" else "ASTRA Engineer"
                history_parts.append(f"{role_label}: {m.content}")
                if m.files_changed:
                    history_parts.append(f"  [Files modified: {', '.join(m.files_changed)}]")

            if session.context_summary:
                history_parts.append("\nSESSION SUMMARY OF CHANGES SO FAR:")
                history_parts.append(session.context_summary)

            history_parts.append("\nCURRENT GOAL TO EXECUTE (Focus strictly on this goal; only refer to previous context if this goal explicitly refers to prior work):")
            history_parts.append(current_goal)

            return "\n".join(history_parts)


# Global singleton conversation session manager
conversation_manager = ConversationSessionManager()
