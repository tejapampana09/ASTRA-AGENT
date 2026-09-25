import React, { useState, useEffect } from 'react';
import { Bot, RefreshCw } from 'lucide-react';
import { TaskInput } from './components/TaskInput';
import { Timeline } from './components/Timeline';
import { DiffViewer } from './components/DiffViewer';
import { TestResults } from './components/TestResults';
import { ApprovalModal } from './components/ApprovalModal';
import { createTask, getTask, listTasks, listApprovals, approveTicket, rejectTicket } from './services/api';
import { Task, AgentEvent, ApprovalTicket } from './types';

export const App: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [approvals, setApprovals] = useState<ApprovalTicket[]>([]);
  const [isLoading, setIsLoading] = useState(false);

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
    } catch (e) {
      console.error('Error fetching state:', e);
    }
  };

  useEffect(() => {
    refreshState();
    const interval = setInterval(refreshState, 3000);
    return () => clearInterval(interval);
  }, []);

  // Subscribe to SSE stream for active task
  useEffect(() => {
    if (!activeTask) return;

    const eventSource = new EventSource(`http://localhost:8000/api/events/stream/${activeTask.task_id}`);

    eventSource.onmessage = (e) => {
      if (e.data && e.data.trim() !== '' && !e.data.startsWith(':')) {
        try {
          const parsed: AgentEvent = JSON.parse(e.data);
          setEvents((prev) => [...prev, parsed]);
          if (parsed.event_type === 'TASK_COMPLETED' || parsed.event_type === 'TASK_FAILED') {
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
          <div className="p-2 bg-indigo-600 rounded-lg">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white tracking-tight">ASTRA 2.0</h1>
            <p className="text-xs text-slate-400">Autonomous Software Engineering Agent Platform</p>
          </div>
        </div>
        <button
          onClick={refreshState}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Task Input & Task History */}
        <div className="space-y-6">
          <TaskInput onSubmit={handleLaunchTask} isLoading={isLoading} />

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
            <h3 className="text-sm font-semibold text-white mb-3">Recent Tasks</h3>
            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
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
                            : t.status === 'failed'
                            ? 'bg-rose-500/10 text-rose-400'
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

        {/* Center & Right Columns: Live Execution, Tests, and Diffs */}
        <div className="lg:col-span-2 space-y-6">
          <TestResults
            evidence={activeTask?.final_report?.evidence}
            status={activeTask?.verification_status}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Timeline events={events} />
            <DiffViewer
              diff={activeTask?.final_report?.git_diff}
              filesChanged={activeTask?.final_report?.evidence?.files_changed}
            />
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
