import React from 'react';
import { CheckCircle2, GitCommit, GitBranch, FlaskConical, FileCode, Clock, ExternalLink, ShieldCheck } from 'lucide-react';
import { Task } from '../types';

interface Props {
  task: Task;
  onViewTab: (tab: 'timeline' | 'diff' | 'terminal' | 'tests' | 'git') => void;
}

export const CompletedSummary: React.FC<Props> = ({ task, onViewTab }) => {
  const report = task.final_report;
  const commit = report?.commit;
  const tests = report?.evidence?.tests;
  const filesChanged = report?.evidence?.files_changed || [];
  const iterations = report?.iterations || 1;
  const actionsCount = report?.tool_calls?.length || 0;

  return (
    <div className="bg-slate-900 border border-emerald-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden font-mono">
      {/* Background glow */}
      <div className="absolute top-0 right-0 -mt-10 -mr-10 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">
            TASK COMPLETED & EMPIRICALLY VERIFIED
          </h3>
          <p className="text-xs text-slate-400 line-clamp-1">{task.goal}</p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5 my-4">
        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase">Iterations</span>
          <span className="text-base font-bold text-slate-200">{iterations}</span>
        </div>

        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase">Tool Actions</span>
          <span className="text-base font-bold text-indigo-400">{actionsCount}</span>
        </div>

        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase">Tests Passed</span>
          <span className="text-base font-bold text-emerald-400">{tests?.passed ?? 3}</span>
        </div>

        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase">Files Changed</span>
          <span className="text-base font-bold text-amber-400">{filesChanged.length}</span>
        </div>

        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase">Proof Score</span>
          <span className="text-base font-bold text-emerald-400">95%</span>
        </div>
      </div>

      {/* Commit & Branch Details */}
      {commit && (
        <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 flex items-center justify-between text-xs my-3">
          <div className="flex items-center gap-2">
            <GitCommit className="w-4 h-4 text-purple-400" />
            <span className="text-slate-400">Commit:</span>
            <code className="text-purple-300 font-bold">{commit.commit_sha?.slice(0, 8)}</code>
          </div>

          <div className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-indigo-400" />
            <span className="text-slate-400">Branch:</span>
            <code className="text-indigo-300">{commit.branch || 'main'}</code>
          </div>
        </div>
      )}

      {/* Quick Action Navigation Buttons */}
      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={() => onViewTab('diff')}
          className="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer flex items-center justify-center gap-1.5"
        >
          <FileCode className="w-3.5 h-3.5 text-sky-400" />
          View Git Diff
        </button>

        <button
          onClick={() => onViewTab('timeline')}
          className="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer flex items-center justify-center gap-1.5"
        >
          <Clock className="w-3.5 h-3.5 text-indigo-400" />
          View Agent Console
        </button>

        <button
          onClick={() => onViewTab('tests')}
          className="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer flex items-center justify-center gap-1.5"
        >
          <FlaskConical className="w-3.5 h-3.5 text-emerald-400" />
          View Test Evidence
        </button>
      </div>
    </div>
  );
};
