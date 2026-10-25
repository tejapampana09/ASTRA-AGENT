"""Persistent local request admission. Provider quotas remain authoritative.

Reservations count attempts, including failures; no prompt, API key or response is stored.
Use the same data directory and project ID for processes sharing a Gemini project.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from astra.config import settings


class RequestBudgetExceeded(RuntimeError):
    pass


class ProviderBudgetExceeded(RuntimeError):
    pass


def pacific_window(now: float | None = None) -> tuple[float, float]:
    local = datetime.fromtimestamp(time.time() if now is None else now, ZoneInfo('America/Los_Angeles'))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


def quota_scope(provider: str, model: str) -> str:
    # Unconfigured keys share a conservative local bucket. Set the project ID when
    # using multiple projects; rotating keys must not reset the local daily counter.
    project = settings.gemini_project_id if provider == 'gemini' else provider
    account = hashlib.sha256((project or 'default-project').encode()).hexdigest()[:16]
    return f'{provider}:{account}:{model}'


class RequestLedger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS llm_attempts (
                    id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, scope TEXT NOT NULL,
                    provider TEXT NOT NULL, model TEXT NOT NULL, created_at REAL NOT NULL,
                    outcome TEXT NOT NULL DEFAULT 'reserved', usage TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS llm_attempt_scope ON llm_attempts(scope, created_at);
                CREATE INDEX IF NOT EXISTS llm_attempt_task ON llm_attempts(task_id);
                CREATE TABLE IF NOT EXISTS llm_cooldowns (
                    scope TEXT PRIMARY KEY, state TEXT NOT NULL, until_time REAL NOT NULL
                );
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def reserve(self, task_id: str, provider: str, model: str) -> int:
        now = time.time()
        scope = quota_scope(provider, model)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            count = conn.execute('SELECT count(*) FROM llm_attempts WHERE task_id=?', (task_id,)).fetchone()[0]
            if settings.max_llm_calls_per_task > 0 and count >= settings.max_llm_calls_per_task:
                raise RequestBudgetExceeded('LLM request budget reached. Start a new session to allocate a new budget.')
            if provider == 'gemini':
                start, reset = pacific_window(now)
                for limit, since, label in (
                    (settings.gemini_rpd_budget, start, 'daily'),
                    (settings.gemini_rpm_budget, now - 60, 'minute'),
                ):
                    used = conn.execute('SELECT count(*) FROM llm_attempts WHERE scope=? AND created_at>=?', (scope, since)).fetchone()[0]
                    if limit > 0 and used >= limit:
                        wait = reset - now if label == 'daily' else 60
                        raise ProviderBudgetExceeded(f'Gemini local {label} budget reached; retry in at most {wait:.0f}s or select another provider.')
            cursor = conn.execute('INSERT INTO llm_attempts(task_id,scope,provider,model,created_at) VALUES(?,?,?,?,?)',
                                  (task_id, scope, provider, model, now))
            return cursor.lastrowid

    def finish(self, attempt_id: int, outcome: str, usage: dict | None = None):
        with self.connect() as conn:
            conn.execute('UPDATE llm_attempts SET outcome=?, usage=? WHERE id=?', (outcome, json.dumps(usage or {}), attempt_id))

    def summary(self) -> dict:
        start, reset = pacific_window()
        with self.connect() as conn:
            rows = conn.execute(
                'SELECT provider,model,outcome,usage,created_at FROM llm_attempts ORDER BY id'
            ).fetchall()
        tokens, measured, today = 0, 0, 0
        providers: dict[str, int] = {}
        for provider, model, outcome, raw, created in rows:
            providers[provider] = providers.get(provider, 0) + 1
            if created >= start:
                today += 1
            usage = json.loads(raw)
            if usage:
                measured += 1
                tokens += usage.get('total_token_count') or (
                    (usage.get('prompt_token_count') or 0) + (usage.get('candidates_token_count') or 0)
                )
        return {
            'requests': len(rows), 'requests_today': today, 'tokens': tokens,
            'requests_with_token_usage': measured, 'providers': providers,
            'daily_reset_at': reset,
            'local_limits': {'gemini_rpd_per_model': settings.gemini_rpd_budget,
                             'gemini_rpm_per_model': settings.gemini_rpm_budget,
                             'requests_per_session': settings.max_llm_calls_per_task},
            'scope': 'Local recorded attempts only; provider usage from other apps is not included.',
        }

    def save_cooldown(self, scope: str, state: str, until: float):
        with self.connect() as conn:
            conn.execute('INSERT OR REPLACE INTO llm_cooldowns VALUES(?,?,?)', (scope, state, until))

    def cooldown(self, scope: str):
        with self.connect() as conn:
            return conn.execute('SELECT state, until_time FROM llm_cooldowns WHERE scope=?', (scope,)).fetchone()

    def clear_cooldown(self, scope: str | None = None):
        with self.connect() as conn:
            if scope is None:
                conn.execute('DELETE FROM llm_cooldowns')
            else:
                conn.execute('DELETE FROM llm_cooldowns WHERE scope=?', (scope,))


_ledgers: dict[str, RequestLedger] = {}
import threading
_ledger_lock = threading.Lock()


def request_ledger() -> RequestLedger:
    path = str(settings.data_dir / 'llm_usage.db')
    with _ledger_lock:
        if path not in _ledgers:
            _ledgers[path] = RequestLedger(path)
        return _ledgers[path]
