import React from 'react';
import { GitCompare, FileCode } from 'lucide-react';

interface Props {
  diff?: string;
  filesChanged?: string[];
}

export const DiffViewer: React.FC<Props> = ({ diff, filesChanged = [] }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col h-[400px]">
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-cyan-400" />
          Git Diff & Workspace Changes
        </h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
          {filesChanged.length} files modified
        </span>
      </div>

      {filesChanged.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {filesChanged.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 text-[11px] bg-slate-800 text-slate-300 px-2 py-1 rounded">
              <FileCode className="w-3 h-3 text-slate-400" />
              {f}
            </span>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto bg-slate-950 p-3 rounded-lg border border-slate-800/80 font-mono text-xs text-slate-300">
        {diff ? (
          <pre className="whitespace-pre-wrap">{diff}</pre>
        ) : (
          <div className="text-slate-500 italic py-8 text-center">
            No active diff recorded.
          </div>
        )}
      </div>
    </div>
  );
};
