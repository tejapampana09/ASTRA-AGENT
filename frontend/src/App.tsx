import React, { useState, useEffect } from 'react';
import {
  Activity,
  Terminal,
  FileCode,
  FlaskConical,
  GitBranch,
  StopCircle,
  RefreshCw,
  FolderGit2,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Play,
} from 'lucide-react';
import { TaskInput } from './components/TaskInput';
import { AgentHeader } from './components/AgentHeader';
import { PhaseProgress } from './components/PhaseProgress';
import { AgentConsole } from './components/AgentConsole';
import { LiveTerminal } from './components/LiveTerminal';
import { LiveFileChanges } from './components/LiveFileChanges';
import { LiveVerification } from './components/LiveVerification';
import { LiveGitPanel } from './components/LiveGitPanel';
import { CompletedSummary } from './components/CompletedSummary';
import { ApprovalModal } from './components/ApprovalModal';
import { useAgentEvents } from './hooks/useAgentEvents';
import {
  createTask,
  listTasks,
  cancelTask,
  listApprovals,
  approveTicket,
  rejectTicket,
} from './services/api';
import { Task, ApprovalTicket } from './types';

export const App: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [approvals, setApprovals] = useState<ApprovalTicket[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'timeline' | 'terminal' | 'diff' | 'tests' | 'git'>('timeline');

  // Dedicated resilient event store hook for the active task
  const {
    events,
    translatedActivities,
    latestEvent,
    connectionState,
    currentPhase,
    currentActivity,
    changedFiles,
    terminalCommands,
    reconnect,
  } = useAgentEvents(activeTask?.task_id);

  // Poll tasks & approvals
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
  }, [activeTask?.task_id]);

  const handleCreateTask = async (
    goal: string,
    repoPath?: string,
    model?: string,
    mode?: string
  ) => {
    setIsLoading(true);
    try {
      const newTask = await createTask(goal, repoPath, model, mode);
      setTasks((prev) => [newTask, ...prev]);
      setActiveTask(newTask);
      setActiveTab('timeline');
    } catch (e) {
      console.error('Failed to create task:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectTask = (task: Task) => {
    if (activeTask?.task_id !== task.task_id) {
      setActiveTask(task);
      setActiveTab('timeline');
    }
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
      await approveTicket(ticketId, 'Approved via Antigravity console');
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

  const isCompleted = activeTask?.status === 'completed' || activeTask?.verification_status === 'verified';
  const isFailed = activeTask?.status === 'failed' || activeTask?.status === 'cancelled';

  // Find relevant approvals for the active task
  const activeApproval = approvals.find((a) => a.task_id === activeTask?.task_id && a.status === 'pending');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-600 selection:text-white">
      {/* Top System Bar */}
      <header className="border-b border-slate-900 bg-slate-950/80 backdrop-blur sticky top-0 z-40 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
            <span className="font-bold text-white text-sm">A</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-tight text-white">ASTRA 2.0</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-indigo-400 border border-slate-800">
                LIVE AUTONOMOUS AGENT CONSOLE
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
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
            <span className="text-slate-400 uppercase text-[11px]">
              {connectionState === 'connected'
                ? 'CORE ONLINE'
                : connectionState === 'reconnecting'
                ? 'RECONNECTING...'
                : 'IDLE'}
            </span>
          </div>

          <div className="h-4 w-[1px] bg-slate-800" />

          <button
            onClick={refreshTasksAndApprovals}
            className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 transition bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Sync
          </button>
        </div>
      </header>

      {/* Main Dual-Pane Studio Body */}
      <main className="flex-1 p-4 md:p-6 max-w-[1720px] mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Mission Control & Task Queue (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <TaskInput onSubmit={handleCreateTask} isLoading={isLoading} />

          {/* Task Queue Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <h3 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <FolderGit2 className="w-3.5 h-3.5 text-indigo-400" />
                Active Engineering Tasks
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                {tasks.length} total
              </span>
            </div>

            <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
              {tasks.length === 0 ? (
                <div className="py-8 text-center text-xs font-mono text-slate-500">
                  No tasks recorded yet.
                </div>
              ) : (
                tasks.map((t) => {
                  const isSelected = activeTask?.task_id === t.task_id;
                  const isTaskRunning = t.status === 'running' || t.status === 'created';
                  const isTaskVerified = t.status === 'completed' || t.verification_status === 'verified';

                  return (
                    <button
                      key={t.task_id}
                      onClick={() => handleSelectTask(t)}
                      className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer font-mono ${
                        isSelected
                          ? 'bg-slate-950 border-indigo-500 shadow-md shadow-indigo-500/10'
                          : 'bg-slate-950/60 border-slate-800/80 hover:bg-slate-900 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[11px] font-bold text-indigo-300">
                          {t.task_id}
                        </span>

                        {isTaskRunning ? (
                          <span className="flex items-center gap-1 text-[10px] text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full font-bold">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping" />
                            RUNNING
                          </span>
                        ) : isTaskVerified ? (
                          <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full font-bold">
                            <CheckCircle2 className="w-3 h-3" />
                            VERIFIED
                          </span>
                        ) : (
                          <span className="text-[10px] text-slate-500 uppercase">
                            {t.status}
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate-300 line-clamp-2 font-sans font-normal">
                        {t.goal}
                      </p>

                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-900 text-[10px] text-slate-500">
                        <span>{t.model?.includes('ollama') ? '🦙 Ollama' : '⚡ Gemini'}</span>
                        <span>{t.mode === 'guided' ? '🛡️ Guided' : '🚀 Auto'}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Codex Agent Canvas & Execution Studio (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {/* Active Task Live Header */}
          <AgentHeader
            task={activeTask}
            connectionState={connectionState}
            currentPhase={currentPhase}
            currentActivity={currentActivity}
            actionCount={events.length}
            onRefresh={refreshTasksAndApprovals}
            onCancel={isRunning ? handleCancelTask : undefined}
          />

          {/* Visual Execution Phase Progress */}
          <PhaseProgress
            currentPhase={currentPhase}
            events={events}
            isCompleted={isCompleted}
            isFailed={isFailed}
          />

          {/* Human Approval Required Alert Banner (Guided Mode) */}
          {activeApproval && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/40 flex items-center justify-between gap-4 font-mono text-xs">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
                <div>
                  <h4 className="font-bold text-amber-300">HUMAN APPROVAL GATE REQUIRED</h4>
                  <p className="text-slate-300 text-[11px] mt-0.5">
                    Agent requested execution of tool <strong className="text-white">{activeApproval.tool_name}</strong> (Risk:{' '}
                    <span className="text-rose-400 font-bold">{activeApproval.risk_level}</span>)
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => handleReject(activeApproval.id)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
                >
                  Reject
                </button>
                <button
                  onClick={() => handleApprove(activeApproval.id)}
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition cursor-pointer shadow-lg shadow-emerald-600/30"
                >
                  Authorize Execution
                </button>
              </div>
            </div>
          )}

          {/* Completed Task Summary Card (Only shown when verified) */}
          {isCompleted && activeTask && (
            <CompletedSummary task={activeTask} onViewTab={setActiveTab} />
          )}

          {/* Canvas Tabs Navigation */}
          <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2 overflow-x-auto scrollbar-none font-mono text-xs">
            <button
              onClick={() => setActiveTab('timeline')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition cursor-pointer ${
                activeTab === 'timeline'
                  ? 'bg-indigo-600 text-white font-semibold shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              Live Codex Stream
            </button>

            <button
              onClick={() => setActiveTab('terminal')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition cursor-pointer ${
                activeTab === 'terminal'
                  ? 'bg-indigo-600 text-white font-semibold shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Shell Terminal
              {terminalCommands.length > 0 && (
                <span className="text-[10px] px-1.5 rounded-full bg-slate-950 text-indigo-300">
                  {terminalCommands.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('diff')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition cursor-pointer ${
                activeTab === 'diff'
                  ? 'bg-indigo-600 text-white font-semibold shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              Files & Diff
              {changedFiles.length > 0 && (
                <span className="text-[10px] px-1.5 rounded-full bg-slate-950 text-sky-300">
                  {changedFiles.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('tests')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition cursor-pointer ${
                activeTab === 'tests'
                  ? 'bg-indigo-600 text-white font-semibold shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
            >
              <FlaskConical className="w-3.5 h-3.5" />
              Verification Suite
            </button>

            <button
              onClick={() => setActiveTab('git')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition cursor-pointer ${
                activeTab === 'git'
                  ? 'bg-indigo-600 text-white font-semibold shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
            >
              <GitBranch className="w-3.5 h-3.5" />
              Git & PR
            </button>
          </div>

          {/* Active Canvas Tab Content */}
          <div>
            {activeTab === 'timeline' && (
              <AgentConsole activities={translatedActivities} isRunning={isRunning} />
            )}

            {activeTab === 'terminal' && (
              <LiveTerminal commands={terminalCommands} isRunning={isRunning} />
            )}

            {activeTab === 'diff' && (
              <LiveFileChanges
                files={changedFiles}
                liveDiff={activeTask?.final_report?.git_diff}
              />
            )}

            {activeTab === 'tests' && (
              <LiveVerification task={activeTask} isRunning={isRunning} />
            )}

            {activeTab === 'git' && (
              <LiveGitPanel task={activeTask} isRunning={isRunning} />
            )}
          </div>
        </div>
      </main>

      {/* Global Human Approval Modal (if approval exists) */}
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
