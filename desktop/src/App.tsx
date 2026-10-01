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
import { Sparkles, Terminal, FileCode, CheckCircle2, RotateCcw } from 'lucide-react';

const getRelativePath = (p: string, wsPath?: string): string => {
  if (!p) return '';
  let clean = p.replace(/\\/g, '/');
  if (wsPath) {
    const wsClean = wsPath.replace(/\\/g, '/').replace(/\/$/, '');
    if (clean.toLowerCase().startsWith(wsClean.toLowerCase())) {
      clean = clean.slice(wsClean.length).replace(/^\//, '');
    }
  }
  const parts = clean.split('/');
  return parts.length > 2 && clean.includes(':') ? parts.slice(-2).join('/') : clean;
};

const formatToolAction = (name: string, args: Record<string, any>, wsPath?: string) => {
  const relPath = getRelativePath(args?.file_path || '', wsPath);
  switch (name) {
    case 'create_file':
      return {
        type: 'file' as const,
        title: `Create ${relPath}`,
        detail: args.content ? `${args.content.split('\n').length} lines` : 'new file',
      };
    case 'write_file':
      return {
        type: 'file' as const,
        title: `Write ${relPath}`,
        detail: args.content ? `${args.content.split('\n').length} lines` : 'overwrite',
      };
    case 'edit_file':
      return {
        type: 'file' as const,
        title: `Edit ${relPath}`,
        detail: 'surgical edit',
      };
    case 'read_file':
      return {
        type: 'file' as const,
        title: `Read ${relPath}`,
        detail: args.start_line ? `lines ${args.start_line}-${args.end_line || ''}` : '',
      };
    case 'delete_file':
      return {
        type: 'file' as const,
        title: `Delete ${relPath}`,
        detail: '',
      };
    case 'run_command':
      return {
        type: 'command' as const,
        title: `$ ${args.command || 'command'}`,
        detail: '',
      };
    case 'list_dir':
      return {
        type: 'tool' as const,
        title: `List ${getRelativePath(args.dir_path || '.', wsPath)}`,
        detail: '',
      };
    case 'search_code':
      return {
        type: 'tool' as const,
        title: `Search "${args.query}"`,
        detail: args.search_dir ? `in ${getRelativePath(args.search_dir, wsPath)}` : '',
      };
    case 'git_status':
      return {
        type: 'tool' as const,
        title: 'Git Status',
        detail: '',
      };
    case 'git_diff':
      return {
        type: 'tool' as const,
        title: 'Git Diff',
        detail: '',
      };
    case 'web_search':
      return {
        type: 'tool' as const,
        title: `Web Search: ${args.query}`,
        detail: '',
      };
    default:
      return {
        type: 'tool' as const,
        title: name,
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
      case 'agent_started':
        setCurrentAction(data.is_conversational ? '' : 'Starting agent...');
        setTerminalLogs((prev) => [...prev, `$ Starting task: "${data.goal}"`]);
        break;

      case 'planning':
        if (data.thought) {
          updateAssistantMessage((msg) => ({
            ...msg,
            thought: data.thought,
          }));
        }
        break;

      case 'exploration_started':
        setCurrentAction('Exploring repository architecture...');
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
                status: 'running',
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
              acts[i] = {
                ...acts[i],
                status: data.success === false ? 'failed' : 'completed',
                output: data.output || '(completed)',
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

      case 'agent_completed':
        setAgentState('COMPLETED');
        setCurrentAction('');
        updateAssistantMessage((msg) => {
          const finalActs = (msg.actions || []).map((a) =>
            a.status === 'running' ? { ...a, status: 'completed' as const } : a
          );
          return {
            ...msg,
            content: data.summary || msg.content || 'Task completed successfully.',
            actions: finalActs,
          };
        });
        api.getWorkspaceDiff().then(setDiffResult).catch(() => {});
        break;

      case 'agent_failed':
        setAgentState('FAILED');
        setCurrentAction('');
        updateAssistantMessage((msg) => {
          const finalActs = (msg.actions || []).map((a) =>
            a.status === 'running' ? { ...a, status: 'failed' as const } : a
          );
          return {
            ...msg,
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
          return {
            ...msg,
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
    setMessages((prev) => [...prev, userMsg]);
    setFilesModified([]);
    setFilesCreated([]);
    setAgentState('PLANNING');

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
        const mapped = s.messages.map((m: any, idx: number) => ({
          id: String(idx),
          role: m.role,
          content: m.content,
          timestamp: m.created_at,
        }));
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

  const isRunning =
    agentState !== 'IDLE' &&
    agentState !== 'COMPLETED' &&
    agentState !== 'FAILED' &&
    agentState !== 'CANCELLED';

  const toolCallsCount = events.filter((e) =>
    ['tool_started', 'tool_completed', 'file_changed', 'command_started'].includes(e.event_type)
  ).length;

  return (
    <div className="flex h-screen w-screen bg-[#121316] text-[#c9d1d9] overflow-hidden font-sans select-none ambient-glow">
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
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Minimal Bar */}
        <div className="h-12 px-6 flex items-center justify-between border-b border-[#1c1d24]">
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-zinc-500 font-medium">Workspace:</span>
            <span className="text-zinc-300 font-mono font-medium max-w-sm truncate">
              {metadata?.workspace_path || 'No workspace selected'}
            </span>
            {metadata?.project_type && metadata.project_type !== 'unknown' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono uppercase">
                {metadata.project_type}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3 text-xs">
            {/* Live State Badge */}
            <div
              className={`px-2.5 py-1 rounded-full font-mono text-[10px] uppercase font-semibold border ${
                isRunning
                  ? 'bg-purple-950/60 text-purple-300 border-purple-700/60 animate-pulse'
                  : agentState === 'COMPLETED'
                  ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                  : 'bg-zinc-900 text-zinc-500 border-zinc-800'
              }`}
            >
              ● {agentState}
            </div>

            {/* Sources / Tool Calls Toggle */}
            <button
              onClick={() => setShowSourcesDrawer(!showSourcesDrawer)}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-[#1a1b22] hover:bg-[#22242e] border border-[#2b2d39] text-zinc-300 transition-colors"
            >
              <span>Tool Calls ({toolCallsCount})</span>
            </button>
          </div>
        </div>

        {/* Conversation / Welcome Screen Scroll Area */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 ? (
            /* Welcome / Empty Screen (Image 1 & 2) */
            <div className="h-full flex flex-col items-center justify-center text-center px-4 max-w-2xl mx-auto space-y-6 -mt-8">
              {/* Glowing Center Logo */}
              <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-purple-600 to-violet-400 flex items-center justify-center text-white orb-glow shadow-2xl">
                <Sparkles className="w-8 h-8" />
              </div>

              <div>
                <p className="text-zinc-400 text-sm font-medium tracking-wide">Welcome to ASTRA AI</p>
                <h1 className="text-3xl font-semibold text-white tracking-tight mt-1.5">
                  How Can I Assist You?
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
                    className="p-4 rounded-2xl bg-[#171820] hover:bg-[#1f202a] border border-[#282a35] hover:border-purple-500/40 cursor-pointer transition-all duration-200 shadow-md group"
                  >
                    <h3 className="font-medium text-zinc-200 text-xs group-hover:text-white line-clamp-2">
                      {item.title}
                    </h3>
                    <p className="text-[11px] text-zinc-500 mt-2 line-clamp-3 leading-relaxed">
                      {item.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Active Chat Messages (Image 3 & 4) */
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.map((m) => (
                <ChatMessageView
                  key={m.id}
                  message={m}
                  sourcesCount={toolCallsCount}
                  onOpenSourcesDrawer={() => setShowSourcesDrawer(true)}
                />
              ))}

              {/* Live Autonomous Working Indicator */}
              {isRunning && (
                <div className="p-3 rounded-xl bg-[#12131d] border border-purple-500/40 text-xs shadow-lg shadow-purple-950/30 max-w-lg transition-all">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2.5">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-purple-500"></span>
                      </span>
                      <span className="font-semibold text-zinc-100 tracking-wide text-xs">ASTRA is executing</span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-950/70 border border-purple-700/50 text-purple-300">
                        {agentState}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-zinc-500 animate-pulse">Running autonomous cycle...</span>
                  </div>
                  {currentAction && (
                    <div className="mt-2 text-zinc-300 font-mono text-[11px] pl-5 flex items-center gap-1.5 border-t border-purple-950/40 pt-2 truncate">
                      <Terminal className="w-3 h-3 text-cyan-400 shrink-0" />
                      <span className="truncate">{currentAction}</span>
                    </div>
                  )}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
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
