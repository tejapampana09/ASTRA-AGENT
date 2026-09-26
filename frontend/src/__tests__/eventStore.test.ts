import { describe, it, expect } from 'vitest';
import { AgentEvent } from '../types';

describe('Event Store Deduplication and Ordering Logic', () => {
  // Test pure sequence merging and deduplication logic
  function mergeAndDeduplicate(existing: AgentEvent[], incoming: AgentEvent[]): AgentEvent[] {
    const seen = new Set<number>();
    const combined: AgentEvent[] = [];

    for (const ev of existing) {
      const seq = ev.sequence_id ?? 0;
      if (!seen.has(seq)) {
        seen.add(seq);
        combined.push(ev);
      }
    }

    for (const ev of incoming) {
      const seq = ev.sequence_id ?? 0;
      if (!seen.has(seq)) {
        seen.add(seq);
        combined.push(ev);
      }
    }

    combined.sort((a, b) => (a.sequence_id ?? 0) - (b.sequence_id ?? 0));
    return combined;
  }

  it('deduplicates events with identical sequence_id [1, 2, 2, 3]', () => {
    const existing: AgentEvent[] = [
      { task_id: 't-1', sequence_id: 1, event_type: 'TASK_STARTED', message: '1', timestamp: '2026-09-26T12:00:00Z' },
      { task_id: 't-1', sequence_id: 2, event_type: 'PLANNING', message: '2', timestamp: '2026-09-26T12:00:01Z' },
    ];

    const incoming: AgentEvent[] = [
      { task_id: 't-1', sequence_id: 2, event_type: 'PLANNING', message: 'duplicate 2', timestamp: '2026-09-26T12:00:01Z' },
      { task_id: 't-1', sequence_id: 3, event_type: 'TOOL_CALL_STARTED', message: '3', timestamp: '2026-09-26T12:00:02Z' },
    ];

    const result = mergeAndDeduplicate(existing, incoming);
    expect(result.map((e) => e.sequence_id)).toEqual([1, 2, 3]);
    expect(result.length).toBe(3);
  });

  it('detects sequence gaps and merges missing events [1, 3] -> restores [1, 2, 3]', () => {
    const current: AgentEvent[] = [
      { task_id: 't-1', sequence_id: 1, event_type: 'TASK_STARTED', message: '1', timestamp: '2026-09-26T12:00:00Z' },
    ];

    const incomingEvent: AgentEvent = {
      task_id: 't-1',
      sequence_id: 3,
      event_type: 'TEST_STARTED',
      message: '3',
      timestamp: '2026-09-26T12:00:02Z',
    };

    const lastSeq = current[current.length - 1].sequence_id;
    const isGap = incomingEvent.sequence_id > lastSeq + 1;
    expect(isGap).toBe(true);

    // Simulated history backfill
    const historyBackfill: AgentEvent[] = [
      { task_id: 't-1', sequence_id: 1, event_type: 'TASK_STARTED', message: '1', timestamp: '2026-09-26T12:00:00Z' },
      { task_id: 't-1', sequence_id: 2, event_type: 'TOOL_CALL_STARTED', message: '2', timestamp: '2026-09-26T12:00:01Z' },
      { task_id: 't-1', sequence_id: 3, event_type: 'TEST_STARTED', message: '3', timestamp: '2026-09-26T12:00:02Z' },
    ];

    const restored = mergeAndDeduplicate(current, historyBackfill);
    expect(restored.map((e) => e.sequence_id)).toEqual([1, 2, 3]);
  });

  it('isolates events between different tasks', () => {
    const taskAEvents: AgentEvent[] = [
      { task_id: 'task-A', sequence_id: 1, event_type: 'TASK_STARTED', message: 'Task A', timestamp: '2026-09-26T12:00:00Z' },
    ];
    const taskBEvents: AgentEvent[] = [
      { task_id: 'task-B', sequence_id: 1, event_type: 'TASK_STARTED', message: 'Task B', timestamp: '2026-09-26T12:00:00Z' },
    ];

    // Filter strictly by active task
    const activeTaskId = 'task-B';
    const activeEvents = [...taskAEvents, ...taskBEvents].filter((e) => e.task_id === activeTaskId);

    expect(activeEvents.length).toBe(1);
    expect(activeEvents[0].task_id).toBe('task-B');
    expect(activeEvents[0].message).toBe('Task B');
  });
});
