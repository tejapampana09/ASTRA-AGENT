import React from 'react';
import { GitBranch, GitCommit, GitPullRequest, ExternalLink, CheckCircle2, Circle } from 'lucide-react';
import { Task } from '../types';

interface Props {
  task: Task | null;
  isRunning: boolean;
}

export const LiveGitPanel: React.FC<Props> = ({ task, isRunning }) => {
  const report = task?.final_report;
  const commit = report?.commit;
  const pr = report?.pull_request;
  const filesChanged = report?.evidence?.files_changed || [];

  const hasCommit = Boolean(commit?.commit_sha);
  const hasPR = Boolean(pr?.pr_url || pr?.url);
  const isSimulatedPR = pr?.simulated || (pr?.url && pr.url.includes('simulated'));

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col h-[480px]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-purple-400" />
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
            Git & Pull Request Pipeline
          </h3>
        </div>

        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
          {commit?.branch || 'main'}
        </span>
      </div>

      <div className="space-y-4 overflow-y-auto font-mono text-xs pr-1">
        {/* Step 1: Workspace & Tree */}
        <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-start gap-3">
          <span className="mt-0.5 text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
          </span>
          <div>
            <h5 className="font-semibold text-slate-200">Working Tree & Boundary Check</h5>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Isolated workspace created at <code className="text-slate-300">{task?.workspace_path || 'sandbox'}</code>
            </p>
          </div>
        </div>

        {/* Step 2: Changes Detected */}
        <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-start gap-3">
          <span className="mt-0.5 text-emerald-400">
            {filesChanged.length > 0 || hasCommit ? (
              <CheckCircle2 className="w-4 h-4" />
            ) : (
              <Circle className="w-4 h-4 text-slate-600" />
            )}
          </span>
          <div>
            <h5 className="font-semibold text-slate-200">Changes Detected</h5>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {filesChanged.length > 0
                ? `${filesChanged.length} files modified and verified clean`
                : isRunning
                ? 'Scanning workspace modifications...'
                : 'No unstaged modifications'}
            </p>
          </div>
        </div>

        {/* Step 3: Git Commit */}
        <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 flex items-start gap-3">
          <span className="mt-0.5">
            {hasCommit ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <Circle className="w-4 h-4 text-slate-600" />
            )}
          </span>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <h5 className="font-semibold text-slate-200 flex items-center gap-1.5">
                <GitCommit className="w-3.5 h-3.5 text-indigo-400" />
                Commit Created
              </h5>
              {commit?.commit_sha && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                  {commit.commit_sha.slice(0, 8)}
                </span>
              )}
            </div>

            {commit?.commit_message ? (
              <p className="text-[11px] text-slate-300 mt-1 whitespace-pre-wrap pl-2 border-l border-slate-800">
                {commit.commit_message.split('\n')[0]}
              </p>
            ) : (
              <p className="text-[11px] text-slate-500 mt-0.5">
                {isRunning ? 'Will be created upon empirical test verification' : 'Commit pending verification'}
              </p>
            )}
          </div>
        </div>

        {/* Step 4: Branch Pushed */}
        <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-start gap-3">
          <span className="mt-0.5">
            {hasCommit ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <Circle className="w-4 h-4 text-slate-600" />
            )}
          </span>
          <div>
            <h5 className="font-semibold text-slate-200">Branch Pushed</h5>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Remote: <code className="text-slate-300">origin/{commit?.branch || 'main'}</code>
            </p>
          </div>
        </div>

        {/* Step 5: Pull Request */}
        <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 flex items-start gap-3">
          <span className="mt-0.5">
            {hasPR ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <Circle className="w-4 h-4 text-slate-600" />
            )}
          </span>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <h5 className="font-semibold text-slate-200 flex items-center gap-1.5">
                <GitPullRequest className="w-3.5 h-3.5 text-purple-400" />
                Pull Request
              </h5>
              {hasPR && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                  {isSimulatedPR ? 'Simulated Sandbox PR' : `PR #${pr?.pr_number || pr?.number || '42'}`}
                </span>
              )}
            </div>

            {hasPR ? (
              <div className="mt-2 space-y-1.5">
                <p className="text-slate-300 font-medium">{pr?.title || 'ASTRA Autonomous PR'}</p>
                <a
                  href={pr?.pr_url || pr?.url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 underline"
                >
                  {pr?.pr_url || pr?.url}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            ) : (
              <p className="text-[11px] text-slate-500 mt-1">
                ○ PR not created (requires GITHUB_TOKEN configured in backend .env to push to remote GitHub)
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
