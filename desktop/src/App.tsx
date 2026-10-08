import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from './api';
import { Sidebar } from './components/Sidebar';
import { FloatingInputBar } from './components/FloatingInputBar';
import { ChatMessageView } from './components/ChatMessageView';
import { SourcesDrawer } from './components/SourcesDrawer';
import { ModelCatalogModal } from './components/ModelCatalogModal';
import { UsageDashboardModal } from './components/UsageDashboardModal';
import { TerminalPanel } from './components/TerminalPanel';
import { DiffViewer } from './components/DiffViewer';
import { ApprovalModal } from './components/ApprovalModal';
import { SettingsModal } from './components/SettingsModal';
import { CodePreviewPane } from './components/CodePreviewPane';
import { ChatMessage } from './components/ChatPanel';
import {
  AgentEvent,
  AgentState,
  DiffResult,
  FileNode,
  ModelsResponse,
  ProjectMetadata,
  SessionItem,
  SystemHealth,
} from './types';
import { Sparkles, Terminal, FileCode, CheckCircle2, RotateCcw, ChevronDown } from 'lucide-react';

const getRelativePath = (p: string, wsPath?: string): string => {
  if (!p) return '';
  let clean = p.replace(/\\/g, '/');
  if (wsPath) {
    const wsClean = wsPath.replace(/\\/g, '/').replace(/\/+$/, '');
    if (clean.toLowerCase().startsWith(wsClean.toLowerCase())) {
      clean = clean.slice(wsClean.length).replace(/^\/+/, '');
    } else {
      const wsBase = wsClean.split('/').filter(Boolean).pop();
      if (wsBase && clean.toLowerCase().includes(wsBase.toLowerCase() + '/')) {
        const idx = clean.toLowerCase().indexOf(wsBase.toLowerCase() + '/');
        clean = clean.slice(idx + wsBase.length + 1).replace(/^\/+/, '');
      }
    }
  }
  if (/^[a-zA-Z]:\//i.test(clean)) {
    clean = clean.split('/').pop() || clean;
  }
  return clean || p;
};

const getFileIcon = (filename: string): string => {
  const f = filename.toLowerCase();
  if (f.endsWith('.py')) return '🐍';
  if (f.endsWith('.tsx') || f.endsWith('.jsx')) return '⚛️';
  if (f.endsWith('.ts') || f.endsWith('.js')) return '📜';
  if (f.endsWith('.css') || f.endsWith('.html')) return '🎨';
  if (f.endsWith('.json') || f.endsWith('.yaml') || f.endsWith('.yml') || f.endsWith('.toml')) return '⚙️';
  if (f.endsWith('.md')) return '📄';
  return '📄';
};

const formatToolAction = (name: string, args: Record<string, any>, wsPath?: string) => {
  const rawPath = args?.file_path || args?.path || args?.target_path || args?.dir_path || '';
  const relPath = getRelativePath(rawPath, wsPath);
  const lineRange = args?.start_line
    ? `#L${args.start_line}${args.end_line ? `-${args.end_line}` : ''}`
    : '';

  switch (name) {
    case 'create_file':
      return {
        type: 'file' as const,
        actionVerb: 'Created' as const,
        filename: relPath,
        fileIcon: '📄',
        title: `Created 📄 ${relPath}`,
        detail: args.content ? `${args.content.split('\n').length} lines` : 'new file',
      };
    case 'write_file':
      return {
        type: 'file' as const,
        actionVerb: 'Created' as const,
        filename: relPath,
        fileIcon: '📄',
        title: `Created 📄 ${relPath}`,
        detail: args.content ? `${args.content.split('\n').length} lines` : 'overwrite',
      };
    case 'edit_file':
      return {
        type: 'file' as const,
        actionVerb: 'Edited' as const,
        filename: relPath,
        fileIcon: '✏️',
        lineRange,
        title: `Edited ✏️ ${relPath}${lineRange ? ' ' + lineRange : ''}`,
        detail: 'surgical edit',
      };
    case 'read_file': {
      const icon = getFileIcon(relPath);
      return {
        type: 'file' as const,
        actionVerb: 'Analyzed' as const,
        filename: relPath,
        fileIcon: icon,
        lineRange,
        title: `Analyzed ${icon} ${relPath}${lineRange ? ' ' + lineRange : ''}`,
        detail: lineRange,
      };
    }
    case 'delete_file':
      return {
        type: 'file' as const,
        actionVerb: 'Edited' as const,
        filename: relPath,
        fileIcon: '🗑️',
        title: `Deleted 🗑️ ${relPath}`,
        detail: '',
      };
    case 'run_command': {
      const cleanCmd = (args.command || 'command').replace(/^(\$\s*|ran\s+⚡?\s*)/i, '');
      return {
        type: 'command' as const,
        actionVerb: 'Ran' as const,
        command: cleanCmd,
        title: `Ran ⚡ ${cleanCmd}`,
        detail: '',
      };
    }
    case 'list_dir':
      return {
        type: 'file' as const,
        actionVerb: 'Analyzed' as const,
        filename: relPath || '.',
        fileIcon: '📁',
        title: `Analyzed 📁 ${relPath || '.'}`,
        detail: '',
      };
    case 'search_code': {
      const queryStr = `search_code "${args.query || ''}"`;
      return {
        type: 'command' as const,
        actionVerb: 'Ran' as const,
        command: queryStr,
        title: `Ran ⚡ ${queryStr}`,
        detail: args.search_dir ? `in ${getRelativePath(args.search_dir, wsPath)}` : '',
      };
    }
    case 'git_status':
      return {
        type: 'command' as const,
        actionVerb: 'Ran' as const,
        command: 'git status',
        title: 'Ran ⚡ git status',
        detail: '',
      };
    case 'git_diff':
      return {
        type: 'command' as const,
        actionVerb: 'Ran' as const,
        command: 'git diff',
        title: 'Ran ⚡ git diff',
        detail: '',
      };
    case 'web_search': {
      const q = `web_search "${args.query || ''}"`;
      return {
        type: 'command' as const,
        actionVerb: 'Ran' as const,
        command: q,
        title: `Ran ⚡ ${q}`,
        detail: '',
      };
    }
    default:
      return {
        type: 'tool' as const,
        actionVerb: 'Ran' as const,
        command: name,
        title: `Ran ⚡ ${name}`,
        detail: '',
      };
  }
};

export const App: React.FC = () => {
  // System & Backend Data
  const [health, setHealth] = useState<SystemHealth>();
  const [modelsData, setModelsData] = useState<ModelsResponse>();
  const [metadata, setMetadata] = useState<ProjectMetadata>();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [diffResult, setDiffResult] = useState<DiffResult>();

  // Active Session & Agent State
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('groq');
  const [agentState, setAgentState] = useState<AgentState>('IDLE');

  // Chat & Execution Data
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [filesModified, setFilesModified] = useState<string[]>([]);
  const [filesCreated, setFilesCreated] = useState<string[]>([]);
  const [currentAction, setCurrentAction] = useState<string>('');

  // UI Panels & Navigation
  const [activeNav, setActiveNav] = useState<'chat' | 'workspace' | 'models' | 'usage'>('chat');
  const [showSourcesDrawer, setShowSourcesDrawer] = useState<boolean>(false);
  const [showModelModal, setShowModelModal] = useState<boolean>(false);
  const [showUsageModal, setShowUsageModal] = useState<boolean>(false);
  const [showTerminal, setShowTerminal] = useState<boolean>(false);
  const [showDiff, setShowDiff] = useState<boolean>(false);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [pendingApproval, setPendingApproval] = useState<{ approvalId: string; command: string; description?: string } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // App Settings
  const [appSettings, setAppSettings] = useState({
    ollamaBaseUrl: 'http://localhost:11434',
    model: 'ollama/qwen2.5-coder:7b',
    maxIterations: 30,
    commandTimeout: 120,
    permissionMode: 'balanced',
  });

  // Antigravity Split-Pane & Auto-scroll State
  const [previewFile, setPreviewFile] = useState<{
    path: string;
    lineRange?: string;
    defaultTab?: 'file' | 'diff';
  } | null>(null);
  const [showScrollBottom, setShowScrollBottom] = useState<boolean>(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const handleChatScroll = () => {
    if (!chatScrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatScrollRef.current;
    const isUp = scrollHeight - scrollTop - clientHeight > 150;
    setShowScrollBottom(isUp);
  };

  const scrollToBottom = () => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: 'smooth',
      });
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    setShowScrollBottom(false);
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentAction]);

  // Load all initial data from REST API
  const refreshAll = useCallback(async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);

      const mData = await api.getModels();
      setModelsData(mData);
      if (h?.default_model) {
        setSelectedModel(h.default_model);
      } else if (mData?.models?.groq && mData.models.groq.length > 0) {
        setSelectedModel('groq');
      } else if (mData?.models?.ollama && mData.models.ollama.length > 0) {
        setSelectedModel(`ollama/${mData.models.ollama[0].id}`);
      }

      const meta = await api.getWorkspace();
      setMetadata(meta);

      const sessList = await api.listSessions();
      setSessions(sessList);

      const diff = await api.getWorkspaceDiff();
      setDiffResult(diff);
    } catch (err) {
      console.error('Failed to load data:', err);
    }
  }, []);

  useEffect(() => {
    refreshAll();
  }, []);

  // Connect WebSocket for live background agent events
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connect = () => {
      ws = api.connectWebSocket(
        (event: AgentEvent) => {
          handleIncomingEvent(event);
        },
        (connected: boolean) => {
          if (!connected) {
            reconnectTimeout = setTimeout(connect, 3000);
          }
        }
      );
    };

    connect();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  // Helper to update or append to the active assistant message
  const updateAssistantMessage = (updater: (msg: ChatMessage) => ChatMessage) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      if (last.role === 'assistant') {
        return [...prev.slice(0, -1), updater(last)];
      } else {
        const newAssistant: ChatMessage = {
          id: String(Date.now()),
          role: 'assistant',
          content: '',
          actions: [],
          timestamp: Date.now(),
        };
        return [...prev, updater(newAssistant)];
      }
    });
  };

  // Handle incoming live AgentEvent
  const handleIncomingEvent = (event: AgentEvent) => {
    setEvents((prev) => [event, ...prev.slice(0, 150)]);

    if (event.state) {
      setAgentState(event.state);
    }

    const { event_type, data } = event;

    switch (event_type) {
      case 'task_started':
      case 'agent_started':
        setCurrentAction(data.is_conversational ? '' : '● Understanding request...');
        setTerminalLogs((prev) => [...prev, `$ Starting task: "${data.goal}"`]);
        break;

      case 'task_classified':
        setCurrentAction(data.initial_objective ? `● ${data.initial_objective}` : `Task classified: ${data.task_type}`);
        break;

      case 'phase_changed': {
        const ph = data.phase || '';
        const phaseLabels: Record<string, string> = {
          UNDERSTAND: '● Understanding request',
          INVESTIGATE: data.objective ? `● Investigating: ${data.objective}` : '● Investigating subsystem',
          DIAGNOSE: '● Diagnosing root cause',
          PLAN: '● Planning implementation',
          EXECUTE: '● Implementing changes',
          VERIFY: '● Verifying solution independently',
          REPLAN: '● Replanning strategy',
          RECOVER: '● Recovering workspace from checkpoint',
          DONE: '✓ Task completed',
          BLOCKED: '✕ Task blocked',
        };
        if (phaseLabels[ph]) {
          setCurrentAction(phaseLabels[ph]);
        }
        break;
      }

      case 'investigation_started':
        setCurrentAction('● Investigating repository & tracing flow...');
        break;

      case 'hypothesis_created':
        if (data.statement) {
          updateAssistantMessage((msg) => {
            const acts = msg.actions || [];
            return {
              ...msg,
              actions: [
                ...acts,
                {
                  id: `hyp_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
                  type: 'thought',
                  actionVerb: 'Thought for',
                  thoughtSeconds: Math.max(2, Math.round(((Date.now() - (msg.startTime || Date.now())) / 1000) % 20) || 6),
                  title: `Thought for 6s`,
                  detail: `Hypothesis: ${data.statement}`,
                  status: 'completed',
                  timestamp: Date.now(),
                },
              ],
            };
          });
        }
        break;

      case 'evidence_found':
        if (data.fact) {
          updateAssistantMessage((msg) => {
            const acts = msg.actions || [];
            return {
              ...msg,
              actions: [
                ...acts,
                {
                  id: `ev_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
                  type: 'thought',
                  actionVerb: 'Thought for',
                  thoughtSeconds: Math.max(2, Math.round(((Date.now() - (msg.startTime || Date.now())) / 1000) % 20) || 5),
                  title: `Thought for 5s`,
                  detail: `Evidence: ${data.fact}`,
                  status: 'completed',
                  timestamp: Date.now(),
                },
              ],
            };
          });
        }
        break;

      case 'planning':
        if (data.thought) {
          updateAssistantMessage((msg) => {
            const acts = msg.actions || [];
            return {
              ...msg,
              thought: data.thought,
              actions: [
                ...acts,
                {
                  id: `th_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
                  type: 'thought',
                  actionVerb: 'Thought for',
                  thoughtSeconds: 8,
                  title: `Thought for 8s`,
                  detail: data.thought,
                  status: 'completed',
                  timestamp: Date.now(),
                },
              ],
            };
          });
        }
        break;

      case 'exploration_started':
        setCurrentAction('● Exploring repository architecture...');
        break;

      case 'tool_started': {
        const toolArgs = data.arguments || data.args || {};
        const formatted = formatToolAction(data.name, toolArgs, metadata?.workspace_path);
        setCurrentAction(`Running ${formatted.title}...`);
        updateAssistantMessage((msg) => {
          const acts = msg.actions || [];
          const existingIdx = acts.findIndex((a) => a.title === formatted.title);
          if (existingIdx >= 0) {
            const updated = [...acts];
            updated[existingIdx] = {
              ...updated[existingIdx],
              status: 'running',
              detail: formatted.detail || updated[existingIdx].detail,
              actionVerb: formatted.actionVerb,
              filename: (formatted as any).filename,
              fileIcon: (formatted as any).fileIcon,
              lineRange: (formatted as any).lineRange,
              command: (formatted as any).command,
            };
            return { ...msg, actions: updated };
          }
          return {
            ...msg,
            actions: [
              ...acts,
              {
                id: `tool_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
                type: formatted.type,
                title: formatted.title,
                detail: formatted.detail,
                actionVerb: formatted.actionVerb,
                filename: (formatted as any).filename,
                fileIcon: (formatted as any).fileIcon,
                lineRange: (formatted as any).lineRange,
                command: (formatted as any).command,
                status: 'running',
                timestamp: Date.now(),
              },
            ],
          };
        });
        break;
      }

      case 'tool_completed': {
        setCurrentAction('');
        if (data.name === 'run_command') {
          setTerminalLogs((prev) => [...prev, data.output || '']);
        }
        updateAssistantMessage((msg) => {
          const acts = [...(msg.actions || [])];
          for (let i = acts.length - 1; i >= 0; i--) {
            if (acts[i].status === 'running') {
              const startTs = acts[i].timestamp;
              acts[i] = {
                ...acts[i],
                status: data.success === false ? 'failed' : 'completed',
                output: data.output || '(completed)',
                durationMs: startTs ? Date.now() - startTs : undefined,
              };
              break;
            }
          }
          return { ...msg, actions: acts };
        });
        break;
      }

      case 'command_started':
        setTerminalLogs((prev) => [...prev, `$ ${data.command}`]);
        break;

      case 'command_output':
        setTerminalLogs((prev) => [...prev, data.output]);
        updateAssistantMessage((msg) => {
          const acts = [...(msg.actions || [])];
          for (let i = acts.length - 1; i >= 0; i--) {
            if (acts[i].type === 'command') {
              acts[i] = { ...acts[i], output: (acts[i].output ? acts[i].output + '\n' : '') + data.output };
              break;
            }
          }
          return { ...msg, actions: acts };
        });
        break;

      case 'file_changed': {
        const isCreated = data.action === 'created';
        const relPath = getRelativePath(data.file_path, metadata?.workspace_path);
        if (isCreated) {
          setFilesCreated((prev) => Array.from(new Set([...prev, relPath])));
        } else {
          setFilesModified((prev) => Array.from(new Set([...prev, relPath])));
        }
        updateAssistantMessage((msg) => {
          const acts = [...(msg.actions || [])];
          const cleanRel = relPath.toLowerCase().replace(/\\/g, '/');
          const existingIdx = acts.findIndex((a) => {
            const t = a.title.toLowerCase().replace(/\\/g, '/');
            return t.includes(cleanRel);
          });
          if (existingIdx >= 0) {
            acts[existingIdx] = {
              ...acts[existingIdx],
              detail: `${data.lines_changed || 0} lines changed`,
              status: 'completed',
            };
            return { ...msg, actions: acts };
          }
          return msg; // Do not append duplicate card since tool_started already tracks the file operation
        });
        api.getWorkspaceDiff().then(setDiffResult).catch(() => {});
        break;
      }

      case 'verification_started': {
        setCurrentAction('Running independent verification (AST & Test suite)...');
        updateAssistantMessage((msg) => {
          const acts = msg.actions || [];
          const existingIdx = acts.findIndex((a) => a.type === 'verification');
          if (existingIdx >= 0) {
            const updated = [...acts];
            updated[existingIdx] = {
              ...updated[existingIdx],
              status: 'running',
              detail: 'Testing AST, syntax, and automated test runners...',
            };
            return { ...msg, actions: updated };
          }
          return {
            ...msg,
            actions: [
              ...acts,
              {
                id: `verify_${Date.now()}`,
                type: 'verification',
                title: 'Verification (AST & Tests)',
                detail: 'Testing AST, syntax, and automated test runners...',
                status: 'running',
              },
            ],
          };
        });
        break;
      }

      case 'verification_passed': {
        setCurrentAction('');
        updateAssistantMessage((msg) => {
          const acts = (msg.actions || []).map((a) =>
            a.type === 'verification'
              ? {
                  ...a,
                  status: 'completed' as const,
                  title: 'Verification: PASSED',
                  detail: data.summary,
                  output: `Passed: ${data.summary}\n${data.details || ''}`,
                }
              : a
          );
          return {
            ...msg,
            verification: {
              passed: true,
              summary: data.summary,
              details: data.details,
            },
            actions: acts,
          };
        });
        api.getWorkspaceDiff().then(setDiffResult).catch(() => {});
        break;
      }

      case 'verification_failed': {
        setCurrentAction('Diagnosing failure for autonomous self-healing fix...');
        updateAssistantMessage((msg) => {
          const acts = (msg.actions || []).map((a) =>
            a.type === 'verification'
              ? {
                  ...a,
                  status: 'failed' as const,
                  title: 'Verification: FAILED',
                  detail: data.summary,
                  output: `Failed: ${data.summary}\n${data.details || ''}`,
                }
              : a
          );
          return {
            ...msg,
            verification: {
              passed: false,
              summary: data.summary,
              details: data.details,
            },
            actions: acts,
          };
        });
        break;
      }

      case 'fix_started':
        setCurrentAction(`Self-healing attempt ${data.attempt}: Diagnosing and fixing code...`);
        break;

      case 'approval_required':
        setPendingApproval({
          approvalId: data.approval_id,
          command: data.command,
          description: data.description,
        });
        break;

      case 'task_completed':
      case 'agent_completed':
        setAgentState('COMPLETED');
        setCurrentAction('');
        updateAssistantMessage((msg) => {
          const finalActs = (msg.actions || []).map((a) =>
            a.status === 'running' ? { ...a, status: 'completed' as const } : a
          );
          const endTime = Date.now();
          const durationMs = msg.startTime ? endTime - msg.startTime : undefined;
          return {
            ...msg,
            endTime,
            durationMs,
            content: data.summary || msg.content || 'Task completed successfully.',
            actions: finalActs,
          };
        });
        api.getWorkspaceDiff().then(setDiffResult).catch(() => {});
        break;

      case 'task_failed':
      case 'agent_failed':
        setAgentState('FAILED');
        setCurrentAction('');
        updateAssistantMessage((msg) => {
          const finalActs = (msg.actions || []).map((a) =>
            a.status === 'running' ? { ...a, status: 'failed' as const } : a
          );
          const endTime = Date.now();
          const durationMs = msg.startTime ? endTime - msg.startTime : undefined;
          return {
            ...msg,
            endTime,
            durationMs,
            content: `Task halted: ${data.error || 'Execution failed'}`,
            actions: finalActs,
          };
        });
        break;

      case 'agent_cancelled':
        setAgentState('CANCELLED');
        setCurrentAction('');
        updateAssistantMessage((msg) => {
          const finalActs = (msg.actions || []).map((a) =>
            a.status === 'running' ? { ...a, status: 'failed' as const, output: 'Cancelled by user.' } : a
          );
          const endTime = Date.now();
          const durationMs = msg.startTime ? endTime - msg.startTime : undefined;
          return {
            ...msg,
            endTime,
            durationMs,
            content: 'Task stopped by user.',
            actions: finalActs,
          };
        });
        break;

      default:
        break;
    }
  };

  // User submits objective from floating bar or suggestions
  const handleSendMessage = async (goal: string) => {
    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      content: goal,
      timestamp: Date.now(),
    };
    const now = Date.now();
    const initialAssistantMsg: ChatMessage = {
      id: String(now + 1),
      role: 'assistant',
      content: '',
      actions: [
        {
          id: `step_${now}`,
          type: 'thought',
          actionVerb: 'Thought for',
          thoughtSeconds: 1,
          title: 'Thought for 1s',
          detail: 'Initializing cognitive loop and classifying request...',
          status: 'running',
          timestamp: now,
        },
      ],
      timestamp: now + 1,
      startTime: now + 1,
    };
    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);
    setFilesModified([]);
    setFilesCreated([]);
    setAgentState('PLANNING');
    setCurrentAction('Analyzing objective & planning steps...');

    try {
      const res = await api.startTask(goal, metadata?.workspace_path, selectedModel, activeSessionId);
      setActiveSessionId(res.session_id);
      api.listSessions().then(setSessions).catch(() => {});
    } catch (err: any) {
      setAgentState('FAILED');
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          role: 'assistant',
          content: `Failed to start task: ${err.message}`,
          timestamp: Date.now(),
        },
      ]);
    }
  };

  // User clicks STOP
  const handleStopTask = async () => {
    if (activeSessionId) {
      try {
        await api.stopTask(activeSessionId);
      } catch (err) {
        console.error('Stop error:', err);
      }
    }
  };

  // New Chat
  const handleNewChat = () => {
    setActiveSessionId('');
    setMessages([]);
    setEvents([]);
    setFilesModified([]);
    setFilesCreated([]);
    setAgentState('IDLE');
    setCurrentAction('');
  };

  // Select previous session
  const handleSelectSession = async (id: string) => {
    try {
      const s = await api.getSession(id);
      setActiveSessionId(id);
      if (s.messages) {
        const mapped = s.messages.map((m: any, idx: number) => {
          let acts: any[] = [];
          if (m.tool_calls && Array.isArray(m.tool_calls)) {
            acts = m.tool_calls.map((tc: any, tcIdx: number) => {
              const fnName = tc.function?.name || tc.name || '';
              let fnArgs: any = {};
              try {
                fnArgs =
                  typeof tc.function?.arguments === 'string'
                    ? JSON.parse(tc.function.arguments)
                    : tc.function?.arguments || tc.args || {};
              } catch {
                fnArgs = {};
              }
              const fmt = formatToolAction(fnName, fnArgs, metadata?.workspace_path);
              return {
                id: `tc_${idx}_${tcIdx}`,
                type: fmt.type,
                title: fmt.title,
                detail: fmt.detail,
                actionVerb: fmt.actionVerb,
                filename: (fmt as any).filename,
                fileIcon: (fmt as any).fileIcon,
                lineRange: (fmt as any).lineRange,
                command: (fmt as any).command,
                status: 'completed' as const,
              };
            });
          }
          return {
            id: String(idx),
            role: m.role,
            content: m.content,
            actions: acts,
            timestamp: m.created_at || Date.now(),
          };
        });
        setMessages(mapped);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Delete session
  const handleDeleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      if (activeSessionId === id) {
        handleNewChat();
      }
      api.listSessions().then(setSessions).catch(() => {});
    } catch (err) {
      console.error(err);
    }
  };

  // Select workspace folder
  const handleSelectWorkspace = async () => {
    if (window.electronAPI?.selectDirectory) {
      const dir = await window.electronAPI.selectDirectory();
      if (dir) {
        try {
          const res = await api.setWorkspace(dir);
          setMetadata(res.metadata);
          refreshAll();
        } catch (err) {
          console.error('Workspace error:', err);
        }
      }
    } else {
      const p = prompt('Enter workspace directory path:', metadata?.workspace_path || '');
      if (p) {
        try {
          const res = await api.setWorkspace(p);
          setMetadata(res.metadata);
          refreshAll();
        } catch (err) {
          alert(`Invalid workspace: ${err}`);
        }
      }
    }
  };

  const handleNavSelect = (nav: 'chat' | 'workspace' | 'models' | 'usage') => {
    setActiveNav(nav);
    if (nav === 'models') {
      setShowModelModal(true);
    } else if (nav === 'usage') {
      setShowUsageModal(true);
    } else if (nav === 'workspace') {
      handleSelectWorkspace();
    }
  };

  const handleOpenFile = (filePath: string, lineRange?: string) => {
    if (!filePath) return;
    setPreviewFile({ path: filePath, lineRange, defaultTab: 'file' });
    api.getWorkspaceDiff().then(setDiffResult).catch(() => {});
  };

  const isRunning =
    agentState !== 'IDLE' &&
    agentState !== 'COMPLETED' &&
    agentState !== 'FAILED' &&
    agentState !== 'CANCELLED';

  const toolCallsCount = events.filter((e) =>
    ['tool_started', 'tool_completed', 'file_changed', 'command_started'].includes(e.event_type)
  ).length;

  return (
    <div className="flex h-screen w-screen bg-[#0d1117] text-[#c9d1d9] overflow-hidden font-sans select-none">
      {/* Left Sidebar (Echo AI Style) */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        ollamaHealth={health?.ollama}
        modelsData={modelsData}
        activeNav={activeNav}
        onSelectNav={handleNavSelect}
        onOpenSettings={() => setShowSettings(true)}
        workspacePath={metadata?.workspace_path || ''}
        onBrowseWorkspace={handleSelectWorkspace}
      />

      {/* Main Center Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative bg-[#0d1117]">
        {/* Top Minimal Bar */}
        <div className="h-12 px-6 flex items-center justify-between border-b border-[#21262d] bg-[#0d1117]">
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-[#8b949e] font-medium">Workspace:</span>
            <span className="text-[#f0f6fc] font-mono font-medium max-w-sm truncate">
              {metadata?.workspace_path || 'No workspace selected'}
            </span>
            {metadata?.project_type && metadata.project_type !== 'unknown' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#161b22] text-[#8b949e] border border-[#30363d] font-mono uppercase">
                {metadata.project_type}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3 text-xs">
            {/* Live State Badge */}
            <div
              className={`px-2.5 py-1 rounded-full font-mono text-[10px] uppercase font-semibold border ${
                isRunning
                  ? 'bg-blue-950/60 text-blue-400 border-blue-800 animate-pulse'
                  : agentState === 'COMPLETED'
                  ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800'
                  : 'bg-[#161b22] text-[#8b949e] border-[#30363d]'
              }`}
            >
              ● {agentState}
            </div>

            {/* Live Activity & Execution Toggle */}
            <button
              onClick={() => setShowSourcesDrawer(!showSourcesDrawer)}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg border text-xs font-medium transition-all ${
                isRunning
                  ? 'bg-blue-950/60 text-blue-300 border-blue-700 hover:bg-blue-900/60 shadow-xs'
                  : 'bg-[#161b22] hover:bg-[#21262d] border-[#30363d] text-[#c9d1d9]'
              }`}
            >
              {isRunning && <span className="w-2 h-2 rounded-full bg-[#58a6ff] animate-pulse" />}
              <span>⚡ Live Execution ({events.length})</span>
            </button>
          </div>
        </div>

        {/* Main Content Area (Chat + Antigravity Split-Pane) */}
        <div className="flex-1 flex flex-row overflow-hidden relative">
          {/* Conversation / Welcome Screen Scroll Area */}
          <div
            ref={chatScrollRef}
            onScroll={handleChatScroll}
            className="flex-1 overflow-y-auto px-6 py-4 bg-[#0d1117] relative"
          >
            {messages.length === 0 ? (
              /* Welcome / Empty Screen */
              <div className="h-full flex flex-col items-center justify-center text-center px-4 max-w-2xl mx-auto space-y-6 -mt-8">
                {/* Minimalist Antigravity Logo */}
                <div className="w-14 h-14 rounded-2xl bg-[#161b22] border border-[#30363d] flex items-center justify-center text-white shadow-md">
                  <Sparkles className="w-7 h-7 text-[#58a6ff]" />
                </div>

                <div>
                  <p className="text-[#8b949e] text-xs font-semibold uppercase tracking-wider">Antigravity Agent Engine</p>
                  <h1 className="text-2xl font-bold text-[#f0f6fc] tracking-tight mt-1.5">
                    How can I assist you today?
                  </h1>
                </div>

                {/* 3 Suggestion Prompt Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 w-full text-left pt-2">
                  {[
                    {
                      title: 'Fix failing pytest in my workspace',
                      desc: 'Autonomously inspects tests, edits code surgically, and verifies results.',
                    },
                    {
                      title: 'Inspect repository architecture & plan',
                      desc: 'Searches codebase, reads manifests, and summarizes project structure.',
                    },
                    {
                      title: 'Implement JWT auth & independent verification',
                      desc: 'Writes clean functions and runs tests until verification passes.',
                    },
                  ].map((item, idx) => (
                    <div
                      key={idx}
                      onClick={() => handleSendMessage(item.title)}
                      className="p-4 rounded-xl bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] hover:border-[#8b949e]/40 hover:shadow-md cursor-pointer transition-all duration-150 group"
                    >
                      <h3 className="font-semibold text-[#f0f6fc] text-xs group-hover:text-white line-clamp-2">
                        {item.title}
                      </h3>
                      <p className="text-[11px] text-[#8b949e] mt-1.5 line-clamp-3 leading-relaxed">
                        {item.desc}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              /* Active Chat Messages */
              <div className="max-w-3xl mx-auto space-y-4">
                {messages.map((m, idx) => (
                  <ChatMessageView
                    key={m.id}
                    message={m}
                    sourcesCount={toolCallsCount}
                    onOpenSourcesDrawer={() => setShowSourcesDrawer(true)}
                    onOpenFile={handleOpenFile}
                    isStillRunning={isRunning && m.role === 'assistant' && idx === messages.length - 1}
                  />
                ))}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Antigravity Split-Pane Code & Diff Inspector */}
          {previewFile && (
            <CodePreviewPane
              filePath={previewFile.path}
              lineRange={previewFile.lineRange}
              diffResult={diffResult}
              filesModified={filesModified}
              filesCreated={filesCreated}
              defaultTab={previewFile.defaultTab || 'file'}
              onClose={() => setPreviewFile(null)}
            />
          )}

          {/* Floating Antigravity Down-Arrow Scroll Pill Button */}
          {showScrollBottom && (
            <button
              onClick={scrollToBottom}
              className={`fixed z-40 w-8 h-8 rounded-full bg-[#21262d] hover:bg-[#30363d] text-[#f0f6fc] border border-[#30363d] shadow-2xl flex items-center justify-center transition-all animate-in fade-in ${
                previewFile ? 'bottom-24 right-[50%]' : 'bottom-24 right-10'
              }`}
              title="Scroll to bottom"
            >
              <ChevronDown className="w-4 h-4 text-[#f0f6fc]" />
            </button>
          )}
        </div>

        {/* Toggled Bottom Panels (Terminal / Diff) */}
        {showDiff && (
          <DiffViewer
            diffResult={diffResult}
            filesModified={filesModified}
            filesCreated={filesCreated}
            onClose={() => setShowDiff(false)}
          />
        )}
        {showTerminal && !showDiff && (
          <TerminalPanel
            logs={terminalLogs}
            onClear={() => setTerminalLogs([])}
            isRunning={isRunning}
            onStop={handleStopTask}
          />
        )}

        {/* Signature Floating Glowing Input Bar (Image 1, 2, 3, 4) */}
        <FloatingInputBar
          onSendMessage={handleSendMessage}
          isRunning={isRunning}
          onStop={handleStopTask}
          selectedModel={selectedModel}
          onSelectModel={setSelectedModel}
          modelsData={modelsData}
          onToggleTerminal={() => {
            setShowTerminal(!showTerminal);
            setShowDiff(false);
          }}
          onToggleDiff={() => {
            setShowDiff(!showDiff);
            setShowTerminal(false);
            api.getWorkspaceDiff().then(setDiffResult).catch(() => {});
          }}
          onSelectWorkspace={handleSelectWorkspace}
          agentState={agentState}
          isTerminalOpen={showTerminal}
          isDiffOpen={showDiff}
        />
      </main>

      {/* Right Slide-Over Sources / Tool Drawer (Image 4) */}
      {showSourcesDrawer && (
        <SourcesDrawer events={events} onClose={() => setShowSourcesDrawer(false)} />
      )}

      {/* Model Catalog Modal (Image 3 Top-Right) */}
      {showModelModal && (
        <ModelCatalogModal
          onClose={() => setShowModelModal(false)}
          selectedModel={selectedModel}
          onSelectModel={setSelectedModel}
          modelsData={modelsData}
        />
      )}

      {/* Usage Dashboard Modal (Image 3 Bottom-Right) */}
      {showUsageModal && (
        <UsageDashboardModal onClose={() => setShowUsageModal(false)} />
      )}

      {/* Approval Modal for Dangerous Commands */}
      {pendingApproval && (
        <ApprovalModal
          approvalId={pendingApproval.approvalId}
          command={pendingApproval.command}
          description={pendingApproval.description}
          onApprove={async (id) => {
            await api.submitApproval(id, true);
            setPendingApproval(null);
          }}
          onReject={async (id) => {
            await api.submitApproval(id, false);
            setPendingApproval(null);
          }}
        />
      )}

      {/* Settings Modal */}
      {showSettings && (
        <SettingsModal
          currentSettings={appSettings}
          onClose={() => setShowSettings(false)}
          onSave={(newSet) => {
            setAppSettings(newSet);
            setSelectedModel(newSet.model);
          }}
        />
      )}
    </div>
  );
};
