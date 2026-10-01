import React from 'react';
import { GitCompare, FileCode, CheckCircle2 } from 'lucide-react';
import { DiffResult } from '../types';

interface DiffViewerProps {
  diffResult?: DiffResult;
  filesModified: string[];
  filesCreated: string[];
  onClose: () => void;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  diffResult,
  filesModified,
  filesCreated,
  onClose,
}) => {
  const diffLines = (diffResult?.diff || '').split('\n');

  return (
    <div className="h-64 bg-[#0d1117] border-t border-[#30363d] flex flex-col font-mono text-xs select-text">
      {/* Header */}
      <div className="h-8 bg-[#161b22] px-3 border-b border-[#30363d] flex items-center justify-between select-none">
        <div className="flex items-center space-x-2 text-zinc-300">
          <GitCompare className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-semibold text-[11px] uppercase tracking-wider">Changes & Git Diff</span>
          {diffResult?.branch && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
              branch: {diffResult.branch}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-xs text-zinc-400 hover:text-white px-2 py-0.5 rounded hover:bg-zinc-800 transition-colors"
        >
          Close
        </button>
      </div>

      {/* Files Summary Strip */}
      <div className="bg-[#11161d] px-3 py-1.5 border-b border-zinc-800 flex items-center space-x-4 text-[11px]">
        {filesModified.length > 0 && (
          <div className="flex items-center space-x-1 text-amber-400">
            <span className="font-semibold">Modified:</span>
            <span>{filesModified.join(', ')}</span>
          </div>
        )}
        {filesCreated.length > 0 && (
          <div className="flex items-center space-x-1 text-emerald-400">
            <span className="font-semibold">Created:</span>
            <span>{filesCreated.join(', ')}</span>
          </div>
        )}
        {filesModified.length === 0 && filesCreated.length === 0 && (
          <span className="text-zinc-500">No active file changes</span>
        )}
      </div>

      {/* Diff Code View */}
      <div className="flex-1 overflow-y-auto p-3 bg-black/40 space-y-0.5">
        {!diffResult?.diff || diffResult.diff === 'No changes detected.' ? (
          <div className="text-zinc-500 italic">No git differences detected in workspace.</div>
        ) : (
          diffLines.map((line, i) => {
            let color = 'text-zinc-400';
            let bg = '';
            if (line.startsWith('+') && !line.startsWith('+++')) {
              color = 'text-emerald-400';
              bg = 'bg-emerald-950/20';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              color = 'text-rose-400';
              bg = 'bg-rose-950/20';
            } else if (line.startsWith('@@')) {
              color = 'text-cyan-400 font-bold';
            }
            return (
              <div key={i} className={`whitespace-pre px-1 rounded-sm ${color} ${bg}`}>
                {line}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
