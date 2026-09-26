import React, { useState } from 'react';
import { Play, FolderGit2, Cpu, Shield, Zap, Sparkles, Check } from 'lucide-react';

interface Props {
  onSubmit: (goal: string, repoPath?: string, model?: string, mode?: string) => void;
  isLoading: boolean;
}

const TEMPLATES = [
  {
    label: 'Leaf Detector Tests',
    goal: 'Add unit tests for leaf detector isolation in tests/test_leaf_detector.py with synthetic numpy images and run pytest',
  },
  {
    label: 'Inference Validation',
    goal: 'Add defensive input validation and error handling for image dimensions in research/inference/predict.py and verify with pytest',
  },
  {
    label: 'Audit & Manifest Check',
    goal: 'Run test suite, verify dataset manifest in research/split_manifest.json, and prepare clean verification evidence',
  },
];

export const TaskInput: React.FC<Props> = ({ onSubmit, isLoading }) => {
  const [goal, setGoal] = useState('');
  const [repoPath, setRepoPath] = useState('https://github.com/tejapampana09/QuantumCrop-AI.git');
  const [model, setModel] = useState<'gemini' | 'ollama'>('gemini');
  const [mode, setMode] = useState<'autonomous' | 'guided'>('autonomous');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!goal.trim()) return;
    onSubmit(goal, repoPath ? repoPath : undefined, model, mode);
    setGoal('');
  };

  const applyTemplate = (tGoal: string) => {
    setGoal(tGoal);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between mb-3 border-b border-slate-800/80 pb-3">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 tracking-tight">
          <FolderGit2 className="w-4 h-4 text-indigo-400" />
          Mission Control & Task Dispatch
        </h2>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/60 font-semibold">
          LIVE WORKBENCH
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Repo Input */}
        <div>
          <label className="block text-[11px] font-mono font-medium text-slate-400 uppercase tracking-wider mb-1">
            Target Repository URL / Local Path
          </label>
          <input
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            placeholder="e.g. https://github.com/owner/repo.git or local folder path"
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>

        {/* Goal Input */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-[11px] font-mono font-medium text-slate-400 uppercase tracking-wider">
              Engineering Goal / Prompt
            </label>
          </div>
          <textarea
            rows={3}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g. Implement image dimension validation helper in research/utils/io.py, write unit tests in tests/test_io.py, and verify with pytest."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
          />

          {/* Quick template chips */}
          <div className="flex items-center gap-1.5 mt-2 overflow-x-auto pb-1 scrollbar-none">
            <span className="text-[10px] font-mono text-slate-500 shrink-0">Presets:</span>
            {TEMPLATES.map((tmpl, i) => (
              <button
                key={i}
                type="button"
                onClick={() => applyTemplate(tmpl.goal)}
                className="shrink-0 text-[10px] font-mono px-2 py-0.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition cursor-pointer"
              >
                {tmpl.label}
              </button>
            ))}
          </div>
        </div>

        {/* Model & Mode Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {/* Model Selector */}
          <div>
            <label className="block text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
              <Cpu className="w-3 h-3 text-indigo-400" />
              LLM Provider
            </label>
            <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800 text-[11px] font-mono">
              <button
                type="button"
                onClick={() => setModel('gemini')}
                className={`py-1.5 px-2 rounded-lg transition text-center cursor-pointer ${
                  model === 'gemini'
                    ? 'bg-indigo-600 text-white font-semibold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                ⚡ Gemini Flash
              </button>
              <button
                type="button"
                onClick={() => setModel('ollama')}
                className={`py-1.5 px-2 rounded-lg transition text-center cursor-pointer ${
                  model === 'ollama'
                    ? 'bg-indigo-600 text-white font-semibold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🦙 Ollama Local
              </button>
            </div>
          </div>

          {/* Execution Mode */}
          <div>
            <label className="block text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
              <Shield className="w-3 h-3 text-emerald-400" />
              Execution Mode
            </label>
            <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800 text-[11px] font-mono">
              <button
                type="button"
                onClick={() => setMode('autonomous')}
                className={`py-1.5 px-2 rounded-lg transition text-center cursor-pointer ${
                  mode === 'autonomous'
                    ? 'bg-emerald-600 text-white font-semibold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🚀 Autonomous
              </button>
              <button
                type="button"
                onClick={() => setMode('guided')}
                className={`py-1.5 px-2 rounded-lg transition text-center cursor-pointer ${
                  mode === 'guided'
                    ? 'bg-amber-600 text-white font-semibold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🛡️ Guided
              </button>
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading || !goal.trim()}
          className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium text-xs font-mono transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-lg shadow-indigo-600/20"
        >
          <Play className="w-3.5 h-3.5 fill-current" />
          {isLoading ? 'Agent Executing Mission...' : 'Dispatch Autonomous Agent'}
        </button>
      </form>
    </div>
  );
};
