import React from 'react';
import { GitPullRequest, GitBranch, GitCommit, ShieldAlert, CheckCircle, ExternalLink } from 'lucide-react';

interface Props {
  commit?: {
    commit_sha?: string;
    commit_message?: string;
    branch?: string;
    conventional_prefix?: string;
  };
  pullRequest?: {
    pr_number?: number;
    pr_url?: string;
    base_branch?: string;
    head_branch?: string;
    title?: string;
  };
}

export const PullRequestCard: React.FC<Props> = ({ commit, pullRequest }) => {
  if (!commit && !pullRequest) {
    return null;
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <GitPullRequest className="w-4 h-4 text-indigo-400" />
          Git & Pull Request Status
        </h3>
        <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
          Ready for Review
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        {/* Branch & Commit Info */}
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 space-y-2">
          <div className="flex items-center gap-1.5 text-slate-400">
            <GitBranch className="w-3.5 h-3.5 text-indigo-400" />
            <span className="font-semibold text-slate-300">Isolated Branch:</span>
          </div>
          <p className="font-mono text-indigo-300 truncate">
            {commit?.branch || pullRequest?.head_branch || 'main'}
          </p>

          {commit && (
            <div className="pt-2 border-t border-slate-800/60 space-y-1">
              <div className="flex items-center gap-1.5 text-slate-400">
                <GitCommit className="w-3.5 h-3.5 text-emerald-400" />
                <span className="font-semibold text-slate-300">Conventional Commit:</span>
              </div>
              <p className="font-mono text-slate-300 truncate">{commit.commit_message}</p>
              {commit.commit_sha && (
                <span className="text-[10px] font-mono text-slate-500">SHA: {commit.commit_sha.slice(0, 8)}</span>
              )}
            </div>
          )}
        </div>

        {/* Pull Request Card */}
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 space-y-2 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <div className="flex items-center gap-1.5">
                <GitPullRequest className="w-3.5 h-3.5 text-purple-400" />
                <span className="font-semibold text-slate-300">Pull Request #{pullRequest?.pr_number || 1}</span>
              </div>
              {pullRequest?.pr_url && (
                <a
                  href={pullRequest.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-medium"
                >
                  View on GitHub
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            <p className="font-medium text-slate-200 line-clamp-2">
              {pullRequest?.title || 'ASTRA: Automated code implementation'}
            </p>
          </div>

          <div className="bg-amber-950/30 border border-amber-500/20 p-2 rounded text-[11px] text-amber-300 flex items-start gap-1.5 mt-2">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
            <span>
              <strong>Human Gate Enforced:</strong> Merging requires manual approval. Automated merge is disabled.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
