import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  AgentEvent,
  ConnectionState,
  AgentPhase,
  TranslatedActivity,
  FileChangeItem,
  TerminalCommandItem,
} from '../types';
import { API_BASE, getEventHistory } from '../services/api';
import { translateEvent } from '../services/translator';

interface UseAgentEventsReturn {
  events: AgentEvent[];
  translatedActivities: TranslatedActivity[];
  latestEvent: AgentEvent | null;
  connectionState: ConnectionState;
  currentPhase: AgentPhase;
  currentActivity: string;
  changedFiles: FileChangeItem[];
  terminalCommands: TerminalCommandItem[];
  reconnect: () => void;
}

export function useAgentEvents(taskId?: string | null): UseAgentEventsReturn {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [currentPhase, setCurrentPhase] = useState<AgentPhase>('UNDERSTAND');
  const [currentActivity, setCurrentActivity] = useState<string>('Initializing...');

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const backoffRef = useRef<number>(1000); // 1s initial
  const lastSequenceIdRef = useRef<number>(0);
  const isRecoveringRef = useRef<boolean>(false);
  const activeTaskIdRef = useRef<string | null>(null);

  // Helper to merge and deduplicate events by sequence_id
  const mergeEvents = useCallback((existing: AgentEvent[], incoming: AgentEvent[]): AgentEvent[] => {
    const seen = new Set<number>();
    const combined: AgentEvent[] = [];

    // Add existing
    for (const ev of existing) {
      const seq = ev.sequence_id ?? 0;
      if (!seen.has(seq)) {
        seen.add(seq);
        combined.push(ev);
      }
    }

    // Add incoming
    for (const ev of incoming) {
      const seq = ev.sequence_id ?? 0;
      if (!seen.has(seq)) {
        seen.add(seq);
        combined.push(ev);
      }
    }

    // Sort strictly by sequence_id
    combined.sort((a, b) => (a.sequence_id ?? 0) - (b.sequence_id ?? 0));
    return combined;
  }, []);

  // Recover gaps from history endpoint
  const recoverGap = useCallback(async (currentTaskId: string) => {
    if (isRecoveringRef.current) return;
    isRecoveringRef.current = true;
    try {
      const history = await getEventHistory(currentTaskId, 300);
      if (activeTaskIdRef.current !== currentTaskId) return;

      setEvents((prev) => {
        const merged = mergeEvents(prev, history);
        if (merged.length > 0) {
          lastSequenceIdRef.current = Math.max(...merged.map((e) => e.sequence_id ?? 0));
        }
        return merged;
      });
    } catch (e) {
      console.warn(`[useAgentEvents] Gap recovery failed for task ${currentTaskId}:`, e);
    } finally {
      isRecoveringRef.current = false;
    }
  }, [mergeEvents]);

  // Connect to SSE stream
  const connectSSE = useCallback((currentTaskId: string) => {
    if (!currentTaskId) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const url = `${API_BASE}/events/stream/${currentTaskId}?from_sequence_id=${lastSequenceIdRef.current}`;
    setConnectionState((prev) => (prev === 'connected' ? 'connected' : 'connecting'));

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      if (activeTaskIdRef.current !== currentTaskId) {
        es.close();
        return;
      }
      setConnectionState('connected');
      backoffRef.current = 1000; // Reset backoff on success
    };

    es.onmessage = (msg) => {
      if (activeTaskIdRef.current !== currentTaskId) return;

      try {
        const data = JSON.parse(msg.data);
        if (!data || !data.event_type) return;

        // Skip internal connection ack
        if (data.event_type === 'CONNECTED') return;

        const seq = Number(data.sequence_id ?? 0);
        const lastSeq = lastSequenceIdRef.current;

        // Sequence deduplication guarantee:
        if (seq > 0 && seq <= lastSeq) {
          // Already have this event, ignore duplicate
          return;
        }

        // Sequence gap detection guarantee:
        if (seq > 0 && lastSeq > 0 && seq > lastSeq + 1) {
          // Gap detected, fetch history
          recoverGap(currentTaskId);
          return;
        }

        const validEvent: AgentEvent = {
          task_id: data.task_id || currentTaskId,
          sequence_id: seq || lastSeq + 1,
          event_type: data.event_type,
          message: data.message || '',
          payload: data.payload || {},
          source: data.source || 'system',
          timestamp: data.timestamp || new Date().toISOString(),
        };

        lastSequenceIdRef.current = validEvent.sequence_id;

        setEvents((prev) => {
          if (prev.some((e) => e.sequence_id === validEvent.sequence_id)) {
            return prev;
          }
          return [...prev, validEvent];
        });

        // Check if task finished
        if (['TASK_COMPLETED', 'TASK_FAILED', 'TASK_CANCELLED', 'TASK_TIMEOUT'].includes(validEvent.event_type)) {
          setConnectionState('completed');
          es.close();
        }
      } catch (err) {
        console.warn('[useAgentEvents] Failed to parse SSE event:', err);
      }
    };

    es.onerror = () => {
      es.close();
      if (activeTaskIdRef.current !== currentTaskId) return;

      setConnectionState('reconnecting');

      // Exponential backoff: 1s, 2s, 4s, 8s, max 15s
      const delay = backoffRef.current;
      backoffRef.current = Math.min(15000, delay * 2);

      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }

      reconnectTimeoutRef.current = window.setTimeout(async () => {
        if (activeTaskIdRef.current !== currentTaskId) return;
        // Re-hydrate any missed history before reconnecting
        await recoverGap(currentTaskId);
        connectSSE(currentTaskId);
      }, delay);
    };
  }, [recoverGap]);

  // Main lifecycle when taskId changes
  useEffect(() => {
    // 1. Teardown previous task connection
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    activeTaskIdRef.current = taskId || null;
    lastSequenceIdRef.current = 0;
    backoffRef.current = 1000;
    setEvents([]);
    setConnectionState('disconnected');

    if (!taskId) return;

    // 2. Hydrate historical events BEFORE relying on live SSE
    let isCancelled = false;
    const initTask = async () => {
      setConnectionState('connecting');
      try {
        const history = await getEventHistory(taskId, 300);
        if (isCancelled) return;

        if (history && history.length > 0) {
          history.sort((a, b) => (a.sequence_id ?? 0) - (b.sequence_id ?? 0));
          setEvents(history);
          lastSequenceIdRef.current = Math.max(...history.map((e) => e.sequence_id ?? 0));
        }

        // Check if task already ended in history
        const last = history[history.length - 1];
        if (last && ['TASK_COMPLETED', 'TASK_FAILED', 'TASK_CANCELLED', 'TASK_TIMEOUT'].includes(last.event_type)) {
          setConnectionState('completed');
          return; // No need to open SSE if already completed
        }

        // Connect SSE for live updates
        connectSSE(taskId);
      } catch (err) {
        console.warn(`[useAgentEvents] History fetch failed, connecting SSE directly:`, err);
        if (!isCancelled) {
          connectSSE(taskId);
        }
      }
    };

    initTask();

    return () => {
      isCancelled = true;
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [taskId, connectSSE]);

  const reconnect = useCallback(() => {
    if (taskId) {
      backoffRef.current = 1000;
      connectSSE(taskId);
    }
  }, [taskId, connectSSE]);

  // Derived: Translated activities
  const translatedActivities = useMemo(() => {
    return events.map((ev) => translateEvent(ev));
  }, [events]);

  const latestEvent = useMemo(() => {
    return events.length > 0 ? events[events.length - 1] : null;
  }, [events]);

  // Update currentPhase and currentActivity whenever translatedActivities update
  useEffect(() => {
    if (translatedActivities.length > 0) {
      const latest = translatedActivities[translatedActivities.length - 1];
      setCurrentPhase(latest.phase);
      setCurrentActivity(latest.title);
    } else {
      setCurrentPhase('UNDERSTAND');
      setCurrentActivity('Ready');
    }
  }, [translatedActivities]);

  // Derived: Changed files list
  const changedFiles = useMemo(() => {
    const fileMap = new Map<string, FileChangeItem>();

    for (const ev of events) {
      if (ev.event_type === 'FILE_CHANGED' && ev.payload?.path) {
        fileMap.set(ev.payload.path, {
          path: ev.payload.path,
          operation: ev.payload.operation || 'modified',
          timestamp: ev.timestamp,
        });
      } else if (ev.event_type === 'TOOL_CALL_STARTED' && ev.payload?.path) {
        if (!fileMap.has(ev.payload.path)) {
          fileMap.set(ev.payload.path, {
            path: ev.payload.path,
            operation: 'modified',
            timestamp: ev.timestamp,
          });
        }
      }
    }

    return Array.from(fileMap.values());
  }, [events]);

  // Derived: Live terminal command history
  const terminalCommands = useMemo(() => {
    const cmds: TerminalCommandItem[] = [];

    for (const ev of events) {
      const type = ev.event_type;
      const p = ev.payload || {};

      if (type === 'TOOL_CALL_STARTED' && (p.command || p.tool === 'terminal')) {
        cmds.push({
          id: `cmd-${ev.sequence_id}`,
          command: p.command || p.tool || 'command',
          tool: p.tool || 'terminal',
          status: 'running',
          timestamp: ev.timestamp,
        });
      } else if (type === 'TOOL_CALL_COMPLETED') {
        const last = cmds.length > 0 ? cmds[cmds.length - 1] : null;
        if (last && last.status === 'running') {
          last.status = p.exit_code === 0 ? 'completed' : 'failed';
          last.output = p.output || p.summary;
          last.exit_code = p.exit_code ?? 0;
          last.duration_ms = p.duration_ms;
        } else if (p.command) {
          cmds.push({
            id: `cmd-${ev.sequence_id}`,
            command: p.command,
            tool: p.tool || 'terminal',
            status: p.exit_code === 0 ? 'completed' : 'failed',
            output: p.output || p.summary,
            exit_code: p.exit_code ?? 0,
            duration_ms: p.duration_ms,
            timestamp: ev.timestamp,
          });
        }
      } else if (type === 'TEST_STARTED') {
        cmds.push({
          id: `test-${ev.sequence_id}`,
          command: p.command || 'pytest',
          tool: 'test_runner',
          status: 'running',
          timestamp: ev.timestamp,
        });
      } else if (type === 'TEST_COMPLETED') {
        const last = cmds.length > 0 ? cmds[cmds.length - 1] : null;
        if (last && last.status === 'running') {
          last.status = p.failed > 0 ? 'failed' : 'completed';
          last.output = `${p.passed} passed, ${p.failed} failed${p.errors ? `, ${p.errors} errors` : ''}`;
          last.exit_code = p.failed > 0 ? 1 : 0;
          last.duration_ms = p.duration_ms;
        }
      }
    }

    return cmds;
  }, [events]);

  return {
    events,
    translatedActivities,
    latestEvent,
    connectionState,
    currentPhase,
    currentActivity,
    changedFiles,
    terminalCommands,
    reconnect,
  };
}
