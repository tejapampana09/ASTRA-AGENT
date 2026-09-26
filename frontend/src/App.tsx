import React, { useState, useEffect } from 'react';
import {
  Terminal,
  FileCode,
  FlaskConical,
  GitBranch,
  RefreshCw,
  FolderGit2,
  Plus,
  X,
  Sparkles,
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  MessageSquare,
} from 'lucide-react';
import { AutonomousChat } from './components/AutonomousChat';
import { LiveTerminal } from './components/LiveTerminal';
import { LiveFileChanges } from './components/LiveFileChanges';
import { LiveVerification } from './components/LiveVerification';
import { LiveGitPanel } from './components/LiveGitPanel';
import { ApprovalModal } from './components/ApprovalModal';
import { useAgentEvents } from './hooks/useAgentEvents';
import {
  createTask,
  listTasks,
  getTask,
  cancelTask,
  listApprovals,
  approveTicket,
  rejectTicket,
  createSession,
  listSessions,
  getSession,
  sendSessionMessage,
  SessionData,
} from './services/api';
import { Task, ApprovalTicket } from './types';

export const App: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [activeSession, setActiveSession] = useState<SessionData | null>(null);
  const [approvals, setApprovals] = useState<ApprovalTicket[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isInspectOpen, setIsInspectOpen] = useState(false);
  const [showSessionDropdown, setShowSessionDropdown] = useState(false);
  const [workbenchTab, setWorkbenchTab] = useState<'diff' | 'terminal' | 'tests' | 'git'>('diff');

  // Dedicated resilient event store hook for the active task
  const {
    events,
    translatedActivities,
    connectionState,
    changedFiles,
    terminalCommands,
  } = useAgentEvents(activeTask?.task_id);

  // Poll tasks, sessions, and approvals
  const refreshTasksAndApprovals = async () => {
    try {
      const taskList = await listTasks();
      setTasks(taskList);

      if (taskList.length > 0 && !activeTask) {
        setActiveTask(taskList[0]);
      } else if (activeTask) {
        const fresh = taskList.find((t) => t.task_id === activeTask.task_id);
        if (
          fresh &&
          (fresh.status !== activeTask.status ||
            fresh.verification_status !== activeTask.verification_status ||
            fresh.final_report !== activeTask.final_report)
        ) {
          setActiveTask(fresh);
        }
      }

      // Fetch sessions
      try {
        const sessionList = await listSessions();
        setSessions(sessionList);
        if (activeSession) {
          const freshSession = sessionList.find((s) => s.id === activeSession.id);
          if (freshSession) {
            setActiveSession(freshSession);
          }
        } else if (sessionList.length > 0 && !activeTask) {
          setActiveSession(sessionList[0]);
        }
      } catch (sessErr) {
        console.debug('Sessions endpoint offline or loading:', sessErr);
      }

      const pendingApprovals = await listApprovals();
      setApprovals(pendingApprovals);
    } catch (e) {
      console.error('Error fetching tasks/approvals:', e);
    }
  };

  useEffect(() => {
    refreshTasksAndApprovals();
    const interval = setInterval(refreshTasksAndApprovals, 2500);
    return () => clearInterval(interval);
  }, [activeTask?.task_id, activeSession?.id]);

  const handleCreateTask = async (
    goal: string,
    repoPath?: string,
    model?: string,
    mode?: string
  ) => {
    setIsLoading(true);
    try {
      let currentSession = activeSession;
      if (!currentSession) {
        currentSession = await createSession(repoPath, model, mode, goal.slice(0, 50));
        setActiveSession(currentSession);
      }

      const res = await sendSessionMessage(currentSession.id, goal, repoPath, model, mode);
      setActiveSession(res.session);

      try {
        const newTask = await getTask(res.task_id);
        setTasks((prev) => [newTask, ...prev]);
        setActiveTask(newTask);
      } catch {
        // Fallback placeholder task while polling fills in
        const placeholder: Task = {
          task_id: res.task_id,
          goal: goal,
          status: 'running',
          verification_status: 'pending',
          created_at: new Date().toISOString(),
        };
        setTasks((prev) => [placeholder, ...prev]);
        setActiveTask(placeholder);
      }
    } catch (e) {
      console.error('Conversational session dispatch failed, falling back to direct task:', e);
      try {
        const newTask = await createTask(goal, repoPath, model, mode);
        setTasks((prev) => [newTask, ...prev]);
        setActiveTask(newTask);
      } catch (err) {
        console.error('Direct task creation also failed:', err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectSession = (sess: SessionData) => {
    setActiveSession(sess);
    setShowSessionDropdown(false);
    if (sess.tasks && sess.tasks.length > 0) {
      const latestTaskId = sess.tasks[sess.tasks.length - 1];
      const match = tasks.find((t) => t.task_id === latestTaskId);
      if (match) {
        setActiveTask(match);
      }
    }
  };

  const handleNewSession = () => {
    setActiveSession(null);
    setActiveTask(null);
    setShowSessionDropdown(false);
  };

  const handleCancelTask = async () => {
    if (!activeTask) return;
    try {
      await cancelTask(activeTask.task_id);
      await refreshTasksAndApprovals();
    } catch (e) {
      console.error('Failed to cancel task:', e);
    }
  };

  const handleApprove = async (ticketId: string) => {
    try {
      await approveTicket(ticketId, 'Approved via Autonomous Engineering Studio');
      await refreshTasksAndApprovals();
    } catch (e) {
      console.error('Failed to approve ticket:', e);
    }
  };

  const handleReject = async (ticketId: string) => {
    try {
      await rejectTicket(ticketId, 'Rejected by reviewer');
      await refreshTasksAndApprovals();
    } catch (e) {
      console.error('Failed to reject ticket:', e);
    }
  };

  const isRunning =
    activeTask?.status === 'running' ||
    activeTask?.status === 'created' ||
    connectionState === 'connecting' ||
    connectionState === 'reconnecting';

  // Find relevant approvals for active task
  const activeApproval = approvals.find(
    (a) => a.task_id === activeTask?.task_id && a.status === 'pending'
  ) || null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-600 selection:text-white">
      {/* Top Header */}
      <header className="border-b border-slate-900 bg-slate-950/80 backdrop-blur sticky top-0 z-40 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-tight text-white">ASTRA 2.0</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-indigo-400 border border-slate-800 font-semibold">
                  AUTONOMOUS SOFTWARE ENGINEER
                </span>
              </div>
            </div>
          </div>

          <div className="h-4 w-[1px] bg-slate-800 hidden sm:block" />

          {/* Conversational Session Switcher */}
          <div className="relative">
            <button
              onClick={() => setShowSessionDropdown(!showSessionDropdown)}
              className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-xs font-mono text-slate-300 transition cursor-pointer"
            >
              <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
              <span className="max-w-[200px] truncate">
                {activeSession ? activeSession.title : (activeTask ? activeTask.task_id : 'New Conversation')}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            </button>

            {showSessionDropdown && (
              <div className="absolute left-0 top-full mt-2 w-80 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-2 z-50 font-mono text-xs max-h-80 overflow-y-auto space-y-1">
                <button
                  onClick={handleNewSession}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold transition cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Start New Conversation</span>
                </button>

                {sessions.length > 0 && (
                  <div className="text-[10px] text-slate-400 font-semibold px-2 py-1 uppercase tracking-wider pt-2">
                    Conversations ({sessions.length})
                  </div>
                )}

                {sessions.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => handleSelectSession(s)}
                    className={`w-full text-left px-3 py-2 rounded-xl transition cursor-pointer flex flex-col gap-0.5 ${
                      activeSession?.id === s.id
                        ? 'bg-slate-800 text-indigo-300 font-bold'
                        : 'text-slate-300 hover:bg-slate-800/60'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="truncate max-w-[180px]">{s.title}</span>
                      <span className="text-[10px] text-slate-500">{s.messages.length} msgs</span>
                    </div>
                    <span className="text-[10px] text-slate-500 truncate font-mono">
                      {s.model?.includes('ollama') ? '🦙 Ollama' : '⚡ Gemini'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          {/* Connection status */}
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                connectionState === 'connected'
                  ? 'bg-emerald-400 animate-pulse'
                  : connectionState === 'reconnecting'
                  ? 'bg-amber-400 animate-ping'
                  : 'bg-slate-600'
              }`}
            />
            <span className="text-slate-400 uppercase text-[11px] hidden sm:inline">
              {connectionState === 'connected'
                ? 'CORE ONLINE'
                : connectionState === 'reconnecting'
                ? 'RECONNECTING...'
                : 'IDLE'}
            </span>
          </div>

          <div className="h-4 w-[1px] bg-slate-800" />

          {/* Quick Sync */}
          <button
            onClick={refreshTasksAndApprovals}
            title="Sync state with core"
            className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 transition bg-slate-900 px-2.5 py-1.5 rounded-xl border border-slate-800 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sync</span>
          </button>
        </div>
      </header>

      {/* Main Studio Viewport */}
      <main className="flex-1 p-3 md:p-5 flex flex-col lg:flex-row gap-5 items-stretch overflow-hidden">
        {/* Primary Agent Conversational Canvas */}
        <div className={`transition-all duration-300 ${isInspectOpen ? 'lg:w-7/12 xl:w-2/3' : 'w-full'}`}>
          <AutonomousChat
            tasks={tasks}
            activeTask={activeTask}
            activities={translatedActivities}
            changedFiles={changedFiles}
            terminalCommands={terminalCommands}
            activeApproval={activeApproval}
            connectionState={connectionState}
            isRunning={isRunning}
            conversationMessages={activeSession?.messages}
            onSendGoal={handleCreateTask}
            onCancelTask={handleCancelTask}
            onApprove={handleApprove}
            onReject={handleReject}
            onToggleInspect={() => setIsInspectOpen(!isInspectOpen)}
            isInspectOpen={isInspectOpen}
          />
        </div>

        {/* Developer Workbench Drawer (Terminal, Diffs, Tests, Git) */}
        {isInspectOpen && (
          <div className="lg:w-5/12 xl:w-1/3 bg-slate-900/90 border border-slate-800/80 rounded-2xl flex flex-col h-[calc(100vh-80px)] overflow-hidden shadow-2xl backdrop-blur">
            {/* Workbench Top Bar */}
            <div className="px-4 py-3 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none font-mono text-xs">
                <button
                  onClick={() => setWorkbenchTab('diff')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition cursor-pointer text-[11px] ${
                    workbenchTab === 'diff'
                      ? 'bg-indigo-600 text-white font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <FileCode className="w-3.5 h-3.5" />
                  <span>Diffs ({changedFiles.length})</span>
                </button>

                <button
                  onClick={() => setWorkbenchTab('terminal')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition cursor-pointer text-[11px] ${
                    workbenchTab === 'terminal'
                      ? 'bg-indigo-600 text-white font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Terminal className="w-3.5 h-3.5" />
                  <span>Shell ({terminalCommands.length})</span>
                </button>

                <button
                  onClick={() => setWorkbenchTab('tests')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition cursor-pointer text-[11px] ${
                    workbenchTab === 'tests'
                      ? 'bg-indigo-600 text-white font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <FlaskConical className="w-3.5 h-3.5" />
                  <span>Tests</span>
                </button>

                <button
                  onClick={() => setWorkbenchTab('git')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition cursor-pointer text-[11px] ${
                    workbenchTab === 'git'
                      ? 'bg-indigo-600 text-white font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <GitBranch className="w-3.5 h-3.5" />
                  <span>Git</span>
                </button>
              </div>

              <button
                onClick={() => setIsInspectOpen(false)}
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition cursor-pointer"
                title="Close Workbench"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Workbench Tab Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {workbenchTab === 'diff' && (
                <LiveFileChanges
                  files={changedFiles}
                  liveDiff={activeTask?.final_report?.git_diff}
                />
              )}

              {workbenchTab === 'terminal' && (
                <LiveTerminal
                  commands={terminalCommands}
                  isRunning={isRunning}
                />
              )}

              {workbenchTab === 'tests' && (
                <LiveVerification
                  task={activeTask}
                  isRunning={isRunning}
                />
              )}

              {workbenchTab === 'git' && (
                <LiveGitPanel
                  task={activeTask}
                  isRunning={isRunning}
                />
              )}
            </div>
          </div>
        )}
      </main>

      {/* Global Human Approval Modal fallback (if approval exists) */}
      {approvals.length > 0 && (
        <ApprovalModal
          ticket={approvals[0]}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}
    </div>
  );
};

export default App;
