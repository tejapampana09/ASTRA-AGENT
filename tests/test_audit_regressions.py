"""Regression coverage for the security, lifecycle and quota audit. No live LLM calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import threading
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from astra.config import settings
from astra.quota import (RequestLedger, RequestBudgetExceeded, ProviderBudgetExceeded,
                         pacific_window, quota_scope)
from astra.llm import LLMClient, LLMResponse, ProviderState, QuotaCircuitBreaker
from astra.session import SessionManager
from astra.checkpoints import CheckpointManager
from astra.workspace import WorkspaceManager
import astra.server as server


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    monkeypatch.setattr(settings, 'gemini_rpd_budget', 50)
    monkeypatch.setattr(settings, 'gemini_rpm_budget', 5)
    monkeypatch.setattr(settings, 'max_llm_calls_per_task', 20)
    monkeypatch.setattr(settings, 'gemini_project_id', 'audit-project')
    return tmp_path


@pytest.fixture
def api_env(isolated, monkeypatch):
    root = isolated / 'workspace'
    root.mkdir()
    monkeypatch.setattr(server, 'current_workspace', WorkspaceManager(root))
    monkeypatch.setattr(server, 'approved_workspace_roots', (root,))
    monkeypatch.setattr(server, 'session_manager', SessionManager(isolated / 'sessions.db'))
    monkeypatch.setattr(settings, 'api_token', '')
    monkeypatch.setattr(settings, 'require_auth', False)
    monkeypatch.setattr(settings, 'is_loopback', True)
    monkeypatch.setattr(server.router.ollama, 'health', lambda: {'connected': False})
    yield root


def test_workspace_switch_cannot_walk_trust_roots(api_env):
    child = api_env / 'child'
    child.mkdir()
    assert server.set_workspace(server.SetWorkspaceRequest(workspace_path=str(child)))['success']
    assert server.validate_authorized_workspace(str(api_env)) == api_env
    with pytest.raises(HTTPException) as exc:
        server.validate_authorized_workspace(str(api_env.parent))
    assert exc.value.status_code == 403


def test_workspace_symlink_escape(api_env):
    outside = api_env.parent / 'outside'
    outside.mkdir()
    try:
        (api_env / 'link').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlink creation requires elevated privilege on Windows')
    with pytest.raises(HTTPException):
        server.validate_authorized_workspace(str(api_env / 'link'))


@pytest.mark.parametrize('required,loopback', [(True, True), (False, False)])
def test_websocket_fails_closed_without_server_token(api_env, monkeypatch, required, loopback):
    monkeypatch.setattr(settings, 'require_auth', required)
    monkeypatch.setattr(settings, 'is_loopback', loopback)
    with TestClient(server.app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect('/ws/events'):
                pass
    assert exc.value.code == 1008


def test_websocket_rejects_cross_origin_even_with_token(api_env, monkeypatch):
    monkeypatch.setattr(settings, 'api_token', 'correct')
    with TestClient(server.app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws/events?token=correct', headers={'origin': 'https://evil.example'}):
                pass


@pytest.mark.parametrize('route', ['/api/health', '/api/models', '/api/workspace', '/api/sessions'])
def test_metadata_reads_require_configured_auth(api_env, monkeypatch, route):
    monkeypatch.setattr(settings, 'api_token', 'correct')
    with TestClient(server.app) as client:
        assert client.get(route).status_code == 401


def test_only_one_worker_and_cancel_does_not_release_reservation(api_env, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    class FakeAgent:
        def __init__(self, **kwargs):
            self.cancelled = False
        def run(self, goal, existing_messages=None):
            entered.set()
            release.wait(5)
        def cancel(self):
            self.cancelled = True
    monkeypatch.setattr(server, 'AstraAgent', FakeAgent)
    sid = server.session_manager.create_session(str(api_env))
    req = server.StartTaskRequest(session_id=sid, goal='inspect workspace')
    def start(_):
        try:
            return server.start_task(req)['status']
        except HTTPException as exc:
            return exc.status_code
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(start, range(8)))
        assert entered.wait(1)
        assert results.count('started') == 1
        assert results.count(409) == 7
        server.stop_task(sid)
        for operation in (lambda: server.start_task(req), lambda: server.resume_task(sid),
                          lambda: server.rollback_task(sid), lambda: server.delete_session(sid)):
            with pytest.raises(HTTPException) as exc:
                operation()
            assert exc.value.status_code == 409
        thread = server.agent_threads[sid]
    finally:
        release.set()
        thread = server.agent_threads.get(sid)
        if thread:
            thread.join(2)
    assert sid not in server.agent_threads
    assert sid not in server.active_agents


def test_resume_revalidates_persisted_workspace(api_env):
    sid = server.session_manager.create_session(str(api_env.parent))
    with pytest.raises(HTTPException) as exc:
        server.resume_task(sid)
    assert exc.value.status_code == 403


def test_task_must_reference_existing_session(api_env):
    with pytest.raises(HTTPException) as exc:
        server.start_task(server.StartTaskRequest(session_id='unknown', goal='inspect'))
    assert exc.value.status_code == 404


def test_checkpoint_rejects_other_session_and_workspace(isolated):
    ws1, ws2 = isolated / 'one', isolated / 'two'
    ws1.mkdir(); ws2.mkdir()
    db = SessionManager(isolated / 'sessions.db')
    a, b = db.create_session(str(ws1)), db.create_session(str(ws2))
    (ws1 / 'same.txt').write_text('first')
    (ws2 / 'same.txt').write_text('second')
    ma, mb = CheckpointManager(ws1, db, a), CheckpointManager(ws2, db, b)
    cp = ma.create_checkpoint(a, 'snapshot', ['same.txt'])
    assert not mb.rollback(cp.checkpoint_id)['success']
    assert (ws2 / 'same.txt').read_text() == 'second'
    assert not CheckpointManager(ws2, db, b).checkpoints


def test_checkpoint_read_error_never_becomes_delete_snapshot(isolated):
    (isolated / 'binary.bin').write_bytes(b'\xff\xfe')
    manager = CheckpointManager(isolated, SessionManager(isolated / 'sessions.db'))
    with pytest.raises(ValueError, match='Cannot safely snapshot'):
        manager.create_checkpoint('s', 'binary', ['binary.bin'])


def test_tool_history_survives_database_restart(isolated):
    db_path = isolated / 'sessions.db'
    db = SessionManager(db_path)
    sid = db.create_session(str(isolated))
    raw = {'role': 'model', 'parts': [{'function_call': {'name': 'read_file', 'args': {'file_path': 'a.py'}}, 'thought_signature': 'c2lnbmF0dXJl'}]}
    db.add_message(sid, 'assistant', '', [{'id': 'c1', 'function': {'name': 'read_file'}}], raw_content=raw)
    db.add_message(sid, 'tool', 'contents', name='read_file', tool_call_id='c1')
    history = SessionManager(db_path).get_messages(sid)
    assert history[0]['raw_content'] == raw
    assert history[1]['name'] == 'read_file'
    assert history[1]['tool_call_id'] == 'c1'


def test_deleting_session_removes_private_records(isolated):
    db = SessionManager(isolated / 'sessions.db')
    sid = db.create_session(str(isolated))
    db.add_message(sid, 'user', 'private content')
    db.save_task_state({'session_id': sid, 'goal': 'private goal'})
    db.save_checkpoint('cp', sid, 'private', None, {'a.txt': 'private'})
    assert db.delete_session(sid)
    assert not db.get_messages(sid)
    assert db.get_task_state(sid) is None
    assert db.get_checkpoint('cp') is None


def test_atomic_daily_reservations_survive_new_ledger(isolated, monkeypatch):
    monkeypatch.setattr(settings, 'gemini_rpd_budget', 3)
    monkeypatch.setattr(settings, 'gemini_rpm_budget', 0)
    path = isolated / 'ledger.db'
    RequestLedger(path)
    def reserve(n):
        try:
            RequestLedger(path).reserve(str(n), 'gemini', 'model')
            return True
        except ProviderBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(12))) == 3
    with pytest.raises(ProviderBudgetExceeded):
        RequestLedger(path).reserve('new-process', 'gemini', 'model')


def test_per_session_budget_persists_across_model_changes(isolated, monkeypatch):
    monkeypatch.setattr(settings, 'max_llm_calls_per_task', 1)
    ledger = RequestLedger(isolated / 'ledger.db')
    ledger.reserve('task', 'gemini', 'model-a')
    with pytest.raises(RequestBudgetExceeded):
        ledger.reserve('task', 'groq', 'model-b')


@pytest.mark.parametrize('date,hours', [('2026-03-08T12:00:00+00:00', 23), ('2026-11-01T12:00:00+00:00', 25)])
def test_pacific_quota_windows_follow_daylight_saving(date, hours):
    start, end = pacific_window(datetime.fromisoformat(date).timestamp())
    assert end - start == hours * 3600


def test_structured_quota_dimensions_and_retry_delay(isolated):
    class APIError(Exception):
        code = 429
        response_json = {'error': {'details': [
            {'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel'},
            {'retryDelay': '12s'},
        ]}}
    cb = QuotaCircuitBreaker()
    assert cb.record_error('g', APIError('quota exceeded')) == ProviderState.RATE_LIMITED
    assert 10 <= cb.get_status('g')['cooldown_remaining_sec'] <= 12
    APIError.response_json = {'error': {'details': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel'}]}}
    assert cb.record_error('g', APIError('RESOURCE_EXHAUSTED')) == ProviderState.QUOTA_EXHAUSTED
    assert 0 < cb.get_status('g')['cooldown_remaining_sec'] <= 25 * 3600


def test_breaker_restores_cooldown_after_restart(isolated):
    a = QuotaCircuitBreaker(persistent=True)
    a.record_error('gemini:project:model', RuntimeError('GenerateRequestsPerDay'))
    b = QuotaCircuitBreaker(persistent=True)
    assert not b.is_available('gemini:project:model')
    assert b.is_available('gemini:project:other-model')


def test_quota_status_refreshes_expired_state(isolated, monkeypatch):
    cb = QuotaCircuitBreaker()
    cb.record_error('g', RuntimeError('429'))
    monkeypatch.setattr('astra.llm.time.time', lambda: 999999999999)
    status = cb.get_status('g')
    assert status['available']
    assert status['state'] == 'healthy'


def test_budget_exhaustion_cannot_trigger_fallback(isolated, monkeypatch):
    monkeypatch.setattr(settings, 'max_llm_calls_per_task', 1)
    client = LLMClient()
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(content='ok')
    monkeypatch.setattr(client.router, 'get_provider_and_model', lambda _: (provider, 'model'))
    monkeypatch.setattr(client.router, 'get_provider_name', lambda _: 'gemini')
    fallback = MagicMock()
    monkeypatch.setattr(client, '_get_fallback_candidates', fallback)
    assert client.complete([{'role': 'user', 'content': 'hi'}]).content == 'ok'
    with pytest.raises(RequestBudgetExceeded):
        client.complete([{'role': 'user', 'content': 'again'}])
    provider.complete.assert_called_once()
    fallback.assert_not_called()


def test_sdk_configuration_and_response_usage_without_network(isolated, monkeypatch):
    from google import genai
    from google.genai import types
    from astra.llm import GeminiProvider
    fake = MagicMock()
    fake.models.generate_content.return_value = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role='model', parts=[types.Part(text='hello')]))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=12, candidates_token_count=3),
    )
    factory = MagicMock(return_value=fake)
    monkeypatch.setattr(genai, 'Client', factory)
    response = GeminiProvider('test-key').complete([{'role': 'user', 'content': 'hi'}])
    assert factory.call_args.kwargs['http_options'].retry_options.attempts == 1
    config = fake.models.generate_content.call_args.kwargs['config']
    assert config.automatic_function_calling.disable
    assert response.usage['prompt_token_count'] == 12
    fake.models.generate_content.assert_called_once()
    fake.close.assert_called_once()


def test_failed_command_is_not_success(isolated):
    from astra.tools import ToolRegistry
    reg = ToolRegistry(isolated)
    result = reg.execute('run_command', {'command': 'python -c "raise SystemExit(7)"'}, approval_callback=lambda *args: True)
    assert not result.success
    assert result.exit_code == 7


def test_unanswered_question_is_not_fabricated(isolated):
    from astra.tools import ToolRegistry
    result = ToolRegistry(isolated).execute('ask_question', {'question': 'Choose?', 'options': ['delete', 'keep']})
    assert not result.success
    assert 'User input is required' in result.error


def test_typescript_compiler_rejects_real_type_error(isolated):
    import shutil
    from astra.verifier import IndependentVerifier
    compiler = Path(__file__).resolve().parents[1] / 'desktop/node_modules/typescript'
    if not compiler.exists():
        pytest.skip('Run npm ci in desktop for compiler integration test')
    (isolated / 'node_modules').mkdir()
    try:
        (isolated / 'node_modules/typescript').symlink_to(compiler, target_is_directory=True)
    except OSError:
        shutil.copytree(compiler, isolated / 'node_modules/typescript')
    (isolated / 'tsconfig.json').write_text(json.dumps({'compilerOptions': {'skipLibCheck': True}, 'files': ['bad.ts']}))
    (isolated / 'bad.ts').write_text('const value: number = "wrong";')
    error, status = IndependentVerifier(isolated)._check_typescript()
    assert status == 'failed'
    assert 'TS2322' in error


def test_usage_reports_recorded_attempts_instead_of_demo_numbers(isolated):
    ledger = RequestLedger(isolated / 'ledger.db')
    assert ledger.summary()['requests'] == 0
    one = ledger.reserve('task', 'gemini', 'model')
    ledger.finish(one, 'success', {'prompt_token_count': 10, 'candidates_token_count': 4})
    ledger.reserve('task', 'groq', 'model')
    usage = ledger.summary()
    assert usage['requests'] == 2
    assert usage['tokens'] == 14
    assert usage['requests_with_token_usage'] == 1
    assert usage['providers'] == {'gemini': 1, 'groq': 1}


def test_settings_apply_to_runtime_and_validate(api_env, monkeypatch):
    for name in ('default_model', 'ollama_base_url', 'max_iterations', 'command_timeout', 'permission_mode'):
        monkeypatch.setattr(settings, name, getattr(settings, name))
    monkeypatch.setattr(server.router.ollama, 'base_url', server.router.ollama.base_url)
    with TestClient(server.app) as client:
        data = client.get('/api/settings').json()
        data.update(model='ollama/test-model', maxIterations=12, commandTimeout=40)
        assert client.put('/api/settings', json=data).status_code == 200
        assert settings.default_model == 'ollama/test-model'
        assert settings.max_iterations == 12
        data['maxIterations'] = -1
        assert client.put('/api/settings', json=data).status_code == 422
        data['maxIterations'] = 12
        data['ollamaBaseUrl'] = 'file:///tmp/config'
        assert client.put('/api/settings', json=data).status_code == 400


def test_distinct_file_reads_are_valid_investigation_progress(isolated):
    from astra.progress import ProgressTracker, ProgressAction
    tracker = ProgressTracker(isolated)
    for filename in ['one.py', 'two.py', 'three.py', 'four.py']:
        report = tracker.record_step('read_file', {'file_path': filename}, True, 'different evidence')
    assert report.is_progressing
    assert report.recommended_action == ProgressAction.CONTINUE


def test_verifier_does_not_pass_when_no_checks_ran(isolated):
    from astra.verifier import IndependentVerifier
    result = IndependentVerifier(isolated).verify(['README.md'])
    assert not result.passed
    assert result.status.value == 'inconclusive'


def test_followup_passes_saved_history_to_worker(api_env, monkeypatch):
    received = []
    class FakeAgent:
        def __init__(self, **kwargs):
            pass
        def run(self, goal, existing_messages=None):
            received.append(existing_messages)
    monkeypatch.setattr(server, 'AstraAgent', FakeAgent)
    sid = server.session_manager.create_session(str(api_env))
    server.session_manager.add_message(sid, 'user', 'first question')
    server.session_manager.add_message(sid, 'assistant', 'earlier answer')
    server.start_task(server.StartTaskRequest(session_id=sid, goal='follow up'))
    with server.worker_lock:
        thread = server.agent_threads.get(sid)
    if thread:
        thread.join(2)
    assert received[0][-1] == {'role': 'user', 'content': 'follow up'}
    assert received[0][0]['content'] == 'first question'


def test_file_tree_does_not_enumerate_outside_symlink(isolated):
    inside, outside = isolated / 'inside', isolated / 'outside'
    inside.mkdir(); outside.mkdir()
    (outside / 'private-name.txt').write_text('private')
    try:
        (inside / 'link').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlink creation requires elevated privilege on Windows')
    assert WorkspaceManager(inside).get_file_tree() == []


def test_actual_network_listener_cannot_bypass_configured_loopback_policy(api_env):
    # Middleware uses the actual ASGI listener/client even when Config says loopback.
    with TestClient(server.app, client=('192.0.2.10', 12345)) as client:
        assert client.get('/api/health').status_code == 500
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws/events'):
                pass


def test_command_cancellation_kills_process_instead_of_raising_name_error(isolated):
    import time
    from astra.tools import ToolExecutor
    cancelled = threading.Event()
    timer = threading.Timer(0.15, cancelled.set)
    timer.start()
    start = time.monotonic()
    try:
        output = ToolExecutor(isolated).run_command(
            'python -c "import time; time.sleep(20)"', timeout=5, cancel_check=cancelled.is_set,
        )
    finally:
        timer.cancel()
    assert 'cancelled by user' in output
    assert time.monotonic() - start < 4


def test_command_drains_large_stdout_and_stderr_without_deadlock(isolated, monkeypatch):
    from astra.tools import ToolExecutor
    monkeypatch.setattr(settings, 'max_output_chars', 4096)
    result = ToolExecutor(isolated).run_command(
        'python -c "import sys; sys.stdout.write(\'A\' * 2000000); sys.stderr.write(\'B\' * 2000000)"', timeout=5,
    )
    assert '[Exit code 0]' in result
    assert '[Output truncated:' in result
    assert '[STDERR truncated:' in result
    assert len(result) < 9000
