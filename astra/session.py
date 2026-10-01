"""ASTRA V4 Session Management and SQLite Local Persistence.

Stores and restores full agent sessions, conversation history, tool calls,
structured events, file modifications, and verification histories.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from astra.config import settings
from astra.events import AgentEvent, AgentState


class SessionManager:
    """Manages SQLite storage for all agent interactions and workspaces."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path or settings.db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                model TEXT NOT NULL,
                state TEXT NOT NULL,
                summary TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                state TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS file_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                passed INTEGER NOT NULL,
                summary TEXT NOT NULL,
                details TEXT NOT NULL,
                phase TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS task_states (
                session_id TEXT PRIMARY KEY,
                state_data TEXT NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                description TEXT NOT NULL,
                git_head TEXT,
                file_snapshots TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """)
            conn.commit()

    def create_session(
        self,
        workspace_path: Optional[str] = None,
        model: Optional[str] = None,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        s_id = session_id or str(uuid.uuid4())
        ws = str(Path(workspace_path or settings.workspace_path).resolve())
        m = model or settings.default_model
        t = title or f"Session {s_id[:8]}"
        now = time.time()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, title, workspace_path, model, state, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (s_id, t, ws, m, AgentState.IDLE.value, "", now, now),
            )
            conn.commit()
        return s_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
            if not row:
                return None
            session_data = dict(row)

            # Fetch messages
            cur_msgs = conn.execute(
                "SELECT role, content, tool_calls, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            messages = []
            for m in cur_msgs.fetchall():
                tc = json.loads(m["tool_calls"]) if m["tool_calls"] else []
                messages.append({
                    "role": m["role"],
                    "content": m["content"],
                    "tool_calls": tc,
                    "created_at": m["created_at"],
                })
            session_data["messages"] = messages

            # Fetch file changes
            cur_files = conn.execute(
                "SELECT file_path, action, created_at FROM file_changes WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            session_data["files_modified"] = [f["file_path"] for f in cur_files.fetchall()]

            # Fetch latest verification
            cur_verif = conn.execute(
                "SELECT * FROM verifications WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
            v_row = cur_verif.fetchone()
            session_data["latest_verification"] = dict(v_row) if v_row else None

            return session_data

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
            return [dict(r) for r in cur.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cur.rowcount > 0

    def update_session(
        self,
        session_id: str,
        state: Optional[AgentState | str] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> None:
        updates = ["updated_at = ?"]
        params: List[Any] = [time.time()]

        if state is not None:
            updates.append("state = ?")
            params.append(state if isinstance(state, str) else state.value)
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)

        params.append(session_id)
        with self._get_connection() as conn:
            conn.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        tc_json = json.dumps(tool_calls) if tool_calls else None
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, tool_calls, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, str(content), tc_json, now),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            conn.commit()

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT role, content, tool_calls FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            res: List[Dict[str, Any]] = []
            for r in cur.fetchall():
                tc = None
                if r["tool_calls"]:
                    try:
                        tc = json.loads(r["tool_calls"])
                    except Exception:
                        tc = None
                msg: Dict[str, Any] = {"role": r["role"], "content": r["content"]}
                if tc:
                    msg["tool_calls"] = tc
                res.append(msg)
            return res

    def add_event(self, session_id: str, event: AgentEvent) -> None:
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO events (session_id, event_type, state, data, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event.event_type if isinstance(event.event_type, str) else event.event_type.value,
                    event.state if isinstance(event.state, str) else event.state.value,
                    json.dumps(event.data),
                    now,
                ),
            )
            conn.commit()

    def add_file_change(self, session_id: str, file_path: str, action: str = "modified") -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO file_changes (session_id, file_path, action, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, file_path, action, time.time()),
            )
            conn.commit()

    def add_verification(self, session_id: str, passed: bool, summary: str, details: str, phase: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO verifications (session_id, passed, summary, details, phase, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, 1 if passed else 0, summary, details, phase, time.time()),
            )
            conn.commit()

    def save_task_state(self, state_dict: Dict[str, Any]) -> None:
        session_id = state_dict.get("session_id")
        if not session_id:
            return
        now = time.time()
        data_json = json.dumps(state_dict)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO task_states (session_id, state_data, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_data = excluded.state_data,
                    updated_at = excluded.updated_at
                """,
                (session_id, data_json, now),
            )
            conn.commit()

    def get_task_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT state_data FROM task_states WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if row and row["state_data"]:
                try:
                    return json.loads(row["state_data"])
                except Exception:
                    return None
        return None

    def save_checkpoint(
        self,
        checkpoint_id: str,
        session_id: str,
        description: str,
        git_head: Optional[str],
        file_snapshots: Dict[str, Optional[str]],
        timestamp: Optional[float] = None,
    ) -> None:
        now = timestamp or time.time()
        snapshots_json = json.dumps(file_snapshots)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (checkpoint_id, session_id, description, git_head, file_snapshots, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(checkpoint_id) DO UPDATE SET
                    description = excluded.description,
                    git_head = excluded.git_head,
                    file_snapshots = excluded.file_snapshots,
                    timestamp = excluded.timestamp
                """,
                (checkpoint_id, session_id, description, git_head, snapshots_json, now),
            )
            conn.commit()

    def get_checkpoints(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if session_id:
                cur = conn.execute(
                    "SELECT * FROM checkpoints WHERE session_id = ? ORDER BY timestamp ASC",
                    (session_id,),
                )
            else:
                cur = conn.execute("SELECT * FROM checkpoints ORDER BY timestamp ASC")
            rows = cur.fetchall()
            results = []
            for r in rows:
                try:
                    snaps = json.loads(r["file_snapshots"])
                except Exception:
                    snaps = {}
                results.append({
                    "checkpoint_id": r["checkpoint_id"],
                    "session_id": r["session_id"],
                    "description": r["description"],
                    "git_head": r["git_head"],
                    "file_snapshots": snaps,
                    "timestamp": r["timestamp"],
                })
            return results

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,))
            r = cur.fetchone()
            if not r:
                return None
            try:
                snaps = json.loads(r["file_snapshots"])
            except Exception:
                snaps = {}
            return {
                "checkpoint_id": r["checkpoint_id"],
                "session_id": r["session_id"],
                "description": r["description"],
                "git_head": r["git_head"],
                "file_snapshots": snaps,
                "timestamp": r["timestamp"],
            }


# Global default session manager
session_manager = SessionManager()
