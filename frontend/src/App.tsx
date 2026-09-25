import React, { useState, useEffect } from 'react';
import { Bot, RefreshCw, StopCircle, RotateCcw, Heart, ShieldAlert, FileText, CheckCircle } from 'lucide-react';
import { TaskInput } from './components/TaskInput';
import { Timeline } from './components/Timeline';
import { DiffViewer } from './components/DiffViewer';
import { TestResults } from './components/TestResults';
import { ApprovalModal } from './components/ApprovalModal';
import { PullRequestCard } from './components/PullRequestCard';
import { TerminalOutput } from './components/TerminalOutput';
import {
  createTask,
  getTask,
  listTasks,
  cancelTask,
  recoverTask,
  getTaskHealth,
  getTaskAudit,
  listApprovals,
  approveTicket,
  rejectTicket,
} from './services/api';
import { Task, AgentEvent, ApprovalTicket } from './types';

export const App: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [approvals, setApprovals] = useState<ApprovalTicket[]>([]);
  const [taskHealth, setTaskHealth] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'timeline' | 'diff' | 'terminal'>('timeline');

  // Poll tasks & approvals
  const refreshState = async () => {
    try {
      const taskList = await listTasks();
      setTasks(taskList);
      if (taskList.length > 0 && !activeTask) {
        setActiveTask(taskList[0]);
      }
      const pendingApprovals = await listApprovals();
      setApprovals(pendingApprovals);

      if (activeTask) {
        try {
          const h = await getTaskHealth(activeTask.task_id);
          setTaskHealth(h);
        } catch {
          // Ignore health fetch if task is brand new
        }
      }
    } catch (e) {
      console.error('Error fetching state:', e);
    }
  };

  useEffect(() => {
    refreshState();
    const interval = setInterval(refreshState, 3000);
    return () => clearInterval(interval);
  }, [activeTask?.task_id]);

  // Subscribe to SSE stream for active task
  useEffect(() => {
    if (!activeTask) return;

    const eventSource = new EventSource(`http://localhost:8000/api/events/stream/${activeTask.task_id}`);

    eventSource.onmessage = (e) => {
      if (e.data && e.data.trim() !== '' && !e.data.startsWith(':')) {
        try {
          const parsed: AgentEvent = JSON.parse(e.data);
          setEvents((prev) => [...prev, parsed]);
          if (
            parsed.event_type === 'TASK_COMPLETED' ||
            parsed.event_type === 'TASK_FAILED' ||
            parsed.event_type === 'TASK_CANCELLED' ||
            parsed.event_type === 'TASK_TIMEOUT'
          ) {
            refreshState();
            getTask(activeTask.task_id).then(setActiveTask);
          }
        } catch (err) {
          console.warn('Failed to parse SSE event:', err);
        }
      }
    };

    return () => {
      eventSource.close();
    };
  }, [activeTask?.task_id]);

  const handleLaunchTask = async (goal: string, repoPath?: string) => {
    setIsLoading(true);
    try {
      const newTask = await createTask(goal, repoPath);
      setActiveTask(newTask);
      setEvents([]);
      await refreshState();
    } catch (err) {
      alert(`Error launching task: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelTask = async () => {
    if (!activeTask) return;
    if (confirm(`Cancel active task ${activeTask.task_id}?`)) {
      await cancelTask(activeTask.task_id);
      await refreshState();
    }
  };

  const handleRecoverTask = async () => {
    if (!activeTask) return;
    try {
      const res = await recoverTask(activeTask.task_id);
      alert(`Recovery initiated: ${res.message}`);
      await refreshState();
    } catch (err) {
      alert(`Recovery failed: ${err}`);
    }
  };

  const handleApprove = async (id: string) => {
    await approveTicket(id, 'Approved via dashboard');
    await refreshState();
  };

  const handleReject = async (id: string) => {
    await rejectTicket(id, 'Rejected via dashboard');
    await refreshState();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-600 rounded-lg shadow-md shadow-indigo-500/20">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white tracking-tight">ASTRA 2.0</h1>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-mono">
                Phase 4 Platform
              </span>
            </div>
            <p className="text-xs text-slate-400">Autonomous Software Engineering Agent Platform</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {activeTask && (
            <div className="hidden md:flex items-center gap-2 text-xs bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
              <Heart className={`w-3.5 h-3.5 ${taskHealth?.is_alive ? 'text-emerald-400 animate-pulse' : 'text-slate-600'}`} />
              <span className="text-slate-400">Heartbeat:</span>
              <span className="font-mono text-slate-200">
                {taskHealth?.heartbeat_age_seconds !== null && taskHealth?.heartbeat_age_seconds !== undefined
                  ? `${taskHealth.heartbeat_age_seconds}s ago`
                  : 'N/A'}
              </span>
            </div>
          )}
          <button
            onClick={refreshState}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Task Input & Task History */}
        <div className="space-y-6">
          <TaskInput onSubmit={handleLaunchTask} isLoading={isLoading} />

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white">Recent Tasks</h3>
              <span className="text-xs text-slate-500 font-mono">{tasks.length} total</span>
            </div>
            <div className="space-y-2 max-h-[340px] overflow-y-auto pr-1">
              {tasks.length === 0 ? (
                <div className="text-xs text-slate-500 italic py-4 text-center">No tasks recorded yet.</div>
              ) : (
                tasks.map((t) => (
                  <button
                    key={t.task_id}
                    onClick={() => {
                      setActiveTask(t);
                      setEvents([]);
                    }}
                    className={`w-full text-left p-3 rounded-lg border text-xs transition cursor-pointer ${
                      activeTask?.task_id === t.task_id
                        ? 'bg-indigo-950/40 border-indigo-500/50 text-white'
                        : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-[10px] text-slate-500">{t.task_id}</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-medium uppercase ${
                          t.status === 'completed'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : t.status === 'failed' || t.status === 'timed_out'
                            ? 'bg-rose-500/10 text-rose-400'
                            : t.status === 'cancelled'
                            ? 'bg-slate-800 text-slate-400'
                            : 'bg-amber-500/10 text-amber-400'
                        }`}
                      >
                        {t.status}
                      </span>
                    </div>
                    <p className="line-clamp-2">{t.goal}</p>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Center & Right Columns: Live Execution, Tests, PR, and Diffs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Active Task Action Bar */}
          {activeTask && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg flex items-center justify-between flex-wrap gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-indigo-400 font-semibold">{activeTask.task_id}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 uppercase font-medium">
                    {activeTask.status}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium">
                    {activeTask.verification_status}
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-1 line-clamp-1">{activeTask.goal}</p>
              </div>

              <div className="flex items-center gap-2">
                {activeTask.status === 'running' && (
                  <button
                    onClick={handleCancelTask}
                    className="flex items-center gap-1 px-2.5 py-1.5 bg-rose-900/40 hover:bg-rose-900/60 border border-rose-700/50 text-rose-300 rounded text-xs transition cursor-pointer"
                  >
                    <StopCircle className="w-3.5 h-3.5" />
                    Cancel
                  </button>
                )}
                {(activeTask.status === 'failed' || activeTask.status === 'stale' || activeTask.status === 'running') && (
                  <button
                    onClick={handleRecoverTask}
                    className="flex items-center gap-1 px-2.5 py-1.5 bg-indigo-900/40 hover:bg-indigo-900/60 border border-indigo-700/50 text-indigo-300 rounded text-xs transition cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Recover & Resume
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Test Verification Evidence */}
          <TestResults
            evidence={activeTask?.final_report?.evidence}
            status={activeTask?.verification_status}
          />

          {/* Pull Request & Git Summary Card (P4.1 & P4.4) */}
          {activeTask?.final_report && (
            <PullRequestCard
              commit={activeTask.final_report.commit}
              pullRequest={activeTask.final_report.pull_request}
            />
          )}

          {/* Tabbed Interactive Section: Timeline / Terminal / Diff */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              <button
                onClick={() => setActiveTab('timeline')}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
                  activeTab === 'timeline'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                Live Event Activity
              </button>
              <button
                onClick={() => setActiveTab('terminal')}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
                  activeTab === 'terminal'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                Terminal Output & Tools
              </button>
              <button
                onClick={() => setActiveTab('diff')}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
                  activeTab === 'diff'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                Git Diff Viewer
              </button>
            </div>

            {activeTab === 'timeline' && <Timeline events={events} />}
            {activeTab === 'terminal' && (
              <TerminalOutput
                commands={activeTask?.final_report?.tool_calls}
                rawOutput={activeTask?.final_report?.evidence?.tests?.command}
              />
            )}
            {activeTab === 'diff' && (
              <DiffViewer
                diff={activeTask?.final_report?.git_diff}
                filesChanged={activeTask?.final_report?.evidence?.files_changed}
              />
            )}
          </div>
        </div>
      </main>

      {/* Human Approval Modal */}
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
