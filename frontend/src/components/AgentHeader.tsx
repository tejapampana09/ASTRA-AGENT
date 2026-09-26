import React, { useState, useEffect } from 'react';
import { Bot, Clock, Cpu, ShieldAlert, Sparkles, CheckCircle2, AlertCircle, RefreshCw, Zap } from 'lucide-react';
import { Task, ConnectionState, AgentPhase } from '../types';

interface Props {
  task: Task | null;
  connectionState: ConnectionState;
  currentPhase: AgentPhase;
  currentActivity: string;
  actionCount: number;
  onRefresh?: () => void;
  onCancel?: () => void;
}

export const AgentHeader: React.FC<Props> = ({
  task,
  connectionState,
  currentPhase,
  currentActivity,
  actionCount,
  onRefresh,
  onCancel,
}) => {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const isRunning =
    task?.status === 'running' ||
    task?.status === 'created' ||
    connectionState === 'connecting' ||
    connectionState === 'reconnecting';

  const isWaitingApproval = task?.status === 'paused_for_approval';
  const isCompleted = task?.status === 'completed' || task?.verification_status === 'verified';
  const isFailed = task?.status === 'failed' || task?.status === 'cancelled' || task?.status === 'timed_out';

  // Live elapsed timer
  useEffect(() => {
    if (!task?.created_at) {
      setElapsedSeconds(0);
      return;
    }

    const startTime = new Date(task.started_at || task.created_at).getTime();

    const updateTimer = () => {
      if (isCompleted && task.completed_at) {
        const endTime = new Date(task.completed_at).getTime();
        setElapsedSeconds(Math.max(0, Math.floor((endTime - startTime) / 1000)));
        return;
      }
      const now = Date.now();
      setElapsedSeconds(Math.max(0, Math.floor((now - startTime) / 1000)));
    };

    updateTimer();
    if (isRunning) {
      const interval = setInterval(updateTimer, 1000);
      return () => clearInterval(interval);
    }
  }, [task?.created_at, task?.started_at, task?.completed_at, isRunning, isCompleted]);

  const formatElapsed = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(mins).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const getStatusBadge = () => {
    if (isWaitingApproval) {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-semibold uppercase tracking-wider animate-pulse">
          <ShieldAlert className="w-3.5 h-3.5" />
          Waiting for Approval
        </span>
      );
    }

    if (isRunning) {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-xs font-semibold uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
          {currentPhase}
        </span>
      );
    }

    if (isCompleted) {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-semibold uppercase tracking-wider">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Completed & Verified
        </span>
      );
    }

    if (isFailed) {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 text-xs font-semibold uppercase tracking-wider">
          <AlertCircle className="w-3.5 h-3.5" />
          {task?.status ? task.status.toUpperCase() : 'FAILED'}
        </span>
      );
    }

    return (
      <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 text-xs font-medium uppercase tracking-wider">
        Ready
      </span>
    );
  };

  return (
    <div className="bg-slate-900/90 backdrop-blur border border-slate-800 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                ASTRA 2.0
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-normal">
                  AUTONOMOUS CODEX
                </span>
              </h1>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Task: <span className="text-indigo-300">{task?.task_id || 'No active task selected'}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {getStatusBadge()}

          {/* Model indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            <span>{task?.model?.includes('ollama') ? 'Ollama: qwen2.5-coder' : 'Gemini 3.1 Flash'}</span>
          </div>

          {/* Mode indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>{task?.mode === 'guided' ? 'Guided (Step-by-Step)' : 'Autonomous (Auto-Pilot)'}</span>
          </div>

          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Refresh State"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Task Goal & Active Activity Banner */}
      <div>
        <h2 className="text-sm font-semibold text-white mb-1.5 line-clamp-2">
          {task?.goal || 'Select or launch a new engineering task to begin autonomous execution.'}
        </h2>

        {/* Live Active Action Pulse */}
        <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl px-3.5 py-2.5 flex items-center justify-between gap-3 mt-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className={`w-2 h-2 rounded-full shrink-0 ${isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            <span className="text-xs font-mono text-slate-200 truncate">
              {currentActivity}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-slate-400 shrink-0">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              {formatElapsed(elapsedSeconds)}
            </span>
            <span>
              <strong className="text-slate-200 font-semibold">{actionCount}</strong> actions
            </span>
            <span>
              Iteration <strong className="text-slate-200 font-semibold">{task?.final_report?.iterations || (isRunning ? 1 : 0)}</strong>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
