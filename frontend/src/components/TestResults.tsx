import React from 'react';
import { CheckCircle2, XCircle, ShieldCheck } from 'lucide-react';

interface Props {
  evidence?: {
    tests: {
      passed: number;
      failed: number;
      errors: number;
      command: string;
    };
    build: string;
    files_changed_count: number;
  };
  status?: string;
}

export const TestResults: React.FC<Props> = ({ evidence, status }) => {
  const tests = evidence?.tests;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          Autonomous Verification Evidence
        </h3>
        <span
          className={`text-xs px-2.5 py-0.5 rounded-full font-medium uppercase tracking-wider ${
            status === 'verified'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : status === 'failed'
              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
          }`}
        >
          {status || 'Pending'}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-3 text-center">
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
          <div className="text-xl font-bold text-emerald-400 flex items-center justify-center gap-1">
            <CheckCircle2 className="w-4 h-4" />
            {tests?.passed ?? 0}
          </div>
          <div className="text-[11px] text-slate-400 uppercase tracking-wider mt-1">Passed</div>
        </div>
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
          <div className="text-xl font-bold text-rose-400 flex items-center justify-center gap-1">
            <XCircle className="w-4 h-4" />
            {tests?.failed ?? 0}
          </div>
          <div className="text-[11px] text-slate-400 uppercase tracking-wider mt-1">Failed</div>
        </div>
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
          <div className="text-xl font-bold text-indigo-400">
            {evidence?.build || 'N/A'}
          </div>
          <div className="text-[11px] text-slate-400 uppercase tracking-wider mt-1">Build</div>
        </div>
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
          <div className="text-xl font-bold text-slate-200">
            {evidence?.files_changed_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-400 uppercase tracking-wider mt-1">Files Changed</div>
        </div>
      </div>

      {tests?.command && (
        <div className="mt-3 text-xs text-slate-400 font-mono bg-slate-950 p-2 rounded border border-slate-800">
          Command: <span className="text-slate-200">{tests.command}</span>
        </div>
      )}
    </div>
  );
};
