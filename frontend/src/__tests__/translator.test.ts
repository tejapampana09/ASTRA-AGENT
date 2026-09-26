import { describe, it, expect } from 'vitest';
import { translateEvent } from '../services/translator';
import { AgentEvent } from '../types';

describe('Agent Activity Translator', () => {
  it('translates TOOL_CALL_STARTED terminal to readable command', () => {
    const event: AgentEvent = {
      task_id: 'task-123',
      sequence_id: 1,
      event_type: 'TOOL_CALL_STARTED',
      message: 'Running pytest tests/test_auth.py',
      payload: {
        tool: 'terminal',
        command: 'pytest tests/test_auth.py',
      },
      timestamp: '2026-09-26T12:00:00Z',
    };

    const translated = translateEvent(event);
    expect(translated.title).toBe('Running pytest tests/test_auth.py');
    expect(translated.iconType).toBe('terminal');
    expect(translated.phase).toBe('EXECUTE');
  });

  it('translates TOOL_CALL_STARTED file_editor to editing message', () => {
    const event: AgentEvent = {
      task_id: 'task-123',
      sequence_id: 2,
      event_type: 'TOOL_CALL_STARTED',
      message: 'Editing backend/auth/service.py',
      payload: {
        tool: 'file_editor',
        path: 'backend/auth/service.py',
        command: 'edit',
      },
      timestamp: '2026-09-26T12:00:01Z',
    };

    const translated = translateEvent(event);
    expect(translated.title).toBe('Editing backend/auth/service.py');
    expect(translated.iconType).toBe('file');
  });

  it('translates FILE_CHANGED cleanly', () => {
    const event: AgentEvent = {
      task_id: 'task-123',
      sequence_id: 3,
      event_type: 'FILE_CHANGED',
      message: 'Modified backend/auth/service.py',
      payload: {
        path: 'backend/auth/service.py',
        operation: 'modified',
      },
      timestamp: '2026-09-26T12:00:02Z',
    };

    const translated = translateEvent(event);
    expect(translated.title).toBe('Modified backend/auth/service.py');
    expect(translated.iconType).toBe('file');
  });

  it('translates TEST_COMPLETED with passed and failed counts', () => {
    const failEvent: AgentEvent = {
      task_id: 'task-123',
      sequence_id: 4,
      event_type: 'TEST_COMPLETED',
      message: 'Tests failed',
      payload: {
        passed: 4,
        failed: 1,
        command: 'pytest',
      },
      timestamp: '2026-09-26T12:00:03Z',
    };

    const translatedFail = translateEvent(failEvent);
    expect(translatedFail.title).toBe('Tests failed — 1 failed, 4 passed');
    expect(translatedFail.iconType).toBe('test_fail');
    expect(translatedFail.phase).toBe('VERIFY');

    const passEvent: AgentEvent = {
      task_id: 'task-123',
      sequence_id: 5,
      event_type: 'TEST_COMPLETED',
      message: 'Tests passed',
      payload: {
        passed: 5,
        failed: 0,
        command: 'pytest',
      },
      timestamp: '2026-09-26T12:00:04Z',
    };

    const translatedPass = translateEvent(passEvent);
    expect(translatedPass.title).toBe('Tests passed — 5 passed');
    expect(translatedPass.iconType).toBe('test_pass');
  });

  it('translates COMMIT_CREATED with short SHA', () => {
    const event: AgentEvent = {
      task_id: 'task-123',
      sequence_id: 6,
      event_type: 'COMMIT_CREATED',
      message: 'Created commit',
      payload: {
        sha: '8f31c2a1b2c3d4e5',
        message: 'fix: resolve authentication validation',
      },
      timestamp: '2026-09-26T12:00:05Z',
    };

    const translated = translateEvent(event);
    expect(translated.title).toBe('Created commit 8f31c2a');
    expect(translated.subtitle).toBe('fix: resolve authentication validation');
    expect(translated.phase).toBe('COMMIT');
  });
});
