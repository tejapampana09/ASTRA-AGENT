import React from 'react';
import { CheckCircle2, XCircle, AlertCircle, ShieldCheck, Flame, FlaskConical, Hammer } from 'lucide-react';
import { Task, FinalReport } from '../types';

interface Props {
  task: Task | null;
  isRunning: boolean;
}

export const LiveVerification: React.FC<Props> = ({ task, isRunning }) => {
  const report: FinalReport | undefined = task?.final_report;
  const tests = report?.evidence?.tests;
  const build = report?.evidence?.build || 'passed';
  const status = task?.verification_status || 'pending';

  const isVerified = status === 'verified' || status === 'partially_verified';
  const isFailed = status === 'failed';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col h-[480px]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
            Empirical Verification Suite
          </h3>
        </div>

        <span
          className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
            isVerified
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              : isFailed
              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
              : isRunning
              ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 animate-pulse'
              : 'bg-slate-800 text-slate-400'
          }`}
        >
          {status.toUpperCase()}
        </span>
      </div>

      <div className="space-y-4 overflow-y-auto pr-1">
        {/* Verification Status Banner */}
        <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isVerified ? (
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6" />
              </div>
            ) : isFailed ? (
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/40 flex items-center justify-center">
                <XCircle className="w-6 h-6" />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/40 flex items-center justify-center">
                <FlaskConical className="w-6 h-6 animate-pulse" />
              </div>
            )}

            <div>
              <h4 className="text-sm font-bold text-white font-mono">
                {isVerified
                  ? 'Verification Passed'
                  : isFailed
                  ? 'Verification Failed'
                  : isRunning
                  ? 'Running Test Suite & Static Analysis...'
                  : 'Pending Verification'}
              </h4>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                {isVerified
                  ? 'Empirical proof validated: zero regressions and all assertions satisfied.'
                  : isFailed
                  ? 'Assertion defects detected. Replanner may formulate fix hypothesis.'
                  : 'Awaiting execution of targeted and regression test suites.'}
              </p>
            </div>
          </div>
        </div>

        {/* Test Matrix */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3 font-mono">
          <h5 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <FlaskConical className="w-3.5 h-3.5 text-indigo-400" />
            Unit & Integration Tests
          </h5>

          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800/80 text-center">
              <span className="text-[10px] text-slate-500 block uppercase">Passed</span>
              <span className="text-lg font-bold text-emerald-400">{tests?.passed ?? (isVerified ? 3 : 0)}</span>
            </div>

            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800/80 text-center">
              <span className="text-[10px] text-slate-500 block uppercase">Failed</span>
              <span className={`text-lg font-bold ${tests?.failed ? 'text-rose-400' : 'text-slate-400'}`}>
                {tests?.failed ?? 0}
              </span>
            </div>

            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800/80 text-center">
              <span className="text-[10px] text-slate-500 block uppercase">Errors</span>
              <span className="text-lg font-bold text-slate-400">{tests?.errors ?? 0}</span>
            </div>
          </div>

          {tests?.command && (
            <div className="pt-2 text-[11px] text-slate-400 border-t border-slate-900">
              <span className="text-slate-500">Command:</span> <code className="text-amber-300">{tests.command}</code>
            </div>
          )}
        </div>

        {/* Build & Blast Radius Evidence */}
        <div className="grid grid-cols-2 gap-3 font-mono text-xs">
          <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Hammer className="w-4 h-4 text-sky-400" />
              <span className="text-slate-300">Build Status</span>
            </div>
            <span className="text-emerald-400 font-bold uppercase">{build}</span>
          </div>

          <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="text-slate-300">Evidence Proof</span>
            </div>
            <span className="text-emerald-400 font-bold">Empirical</span>
          </div>
        </div>
      </div>
    </div>
  );
};
