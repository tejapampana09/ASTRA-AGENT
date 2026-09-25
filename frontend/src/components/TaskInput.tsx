import React, { useState } from 'react';
import { Play, FolderGit2 } from 'lucide-react';

interface Props {
  onSubmit: (goal: string, repoPath?: string) => void;
  isLoading: boolean;
}

export const TaskInput: React.FC<Props> = ({ onSubmit, isLoading }) => {
  const [goal, setGoal] = useState('');
  const [repoPath, setRepoPath] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!goal.trim()) return;
    onSubmit(goal, repoPath ? repoPath : undefined);
    setGoal('');
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
      <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
        <FolderGit2 className="w-5 h-5 text-indigo-400" />
        New Autonomous Engineering Task
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
            Repository Path (Optional)
          </label>
          <input
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            placeholder="e.g. /path/to/my-repo or leave empty for clean workspace"
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
            Engineering Goal / Instructions
          </label>
          <textarea
            rows={3}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g., Analyze this repository, find the failing authentication tests, fix the underlying issue, run the tests, verify changes, and prepare a PR."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || !goal.trim()}
          className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          <Play className="w-4 h-4 fill-current" />
          {isLoading ? 'Agent Running...' : 'Launch ASTRA Agent'}
        </button>
      </form>
    </div>
  );
};
