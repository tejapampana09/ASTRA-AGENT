import React from 'react';
import { GitCompare } from 'lucide-react';
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
    <div className="h-64 bg-white border-t border-slate-200 flex flex-col font-mono text-xs select-text">
      {/* Header */}
      <div className="h-8 bg-slate-50 px-3 border-b border-slate-200 flex items-center justify-between select-none">
        <div className="flex items-center space-x-2 text-slate-800">
          <GitCompare className="w-3.5 h-3.5 text-slate-700" />
          <span className="font-semibold text-[11px] uppercase tracking-wider">Changes & Git Diff</span>
          {diffResult?.branch && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
              branch: {diffResult.branch}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-xs text-slate-500 hover:text-slate-900 px-2 py-0.5 rounded hover:bg-slate-200 transition-colors"
        >
          Close
        </button>
      </div>

      {/* Files Summary Strip */}
      <div className="bg-slate-100/70 px-3 py-1.5 border-b border-slate-200 flex items-center space-x-4 text-[11px]">
        {filesModified.length > 0 && (
          <div className="flex items-center space-x-1 text-amber-700">
            <span className="font-semibold">Modified:</span>
            <span>{filesModified.join(', ')}</span>
          </div>
        )}
        {filesCreated.length > 0 && (
          <div className="flex items-center space-x-1 text-emerald-700">
            <span className="font-semibold">Created:</span>
            <span>{filesCreated.join(', ')}</span>
          </div>
        )}
        {filesModified.length === 0 && filesCreated.length === 0 && (
          <span className="text-slate-500">No active file changes</span>
        )}
      </div>

      {/* Diff Code View */}
      <div className="flex-1 overflow-y-auto p-3 bg-white space-y-0.5">
        {!diffResult?.diff || diffResult.diff === 'No changes detected.' ? (
          <div className="text-slate-400 italic">No git differences detected in workspace.</div>
        ) : (
          diffLines.map((line, i) => {
            let color = 'text-slate-600';
            let bg = '';
            if (line.startsWith('+') && !line.startsWith('+++')) {
              color = 'text-emerald-700';
              bg = 'bg-emerald-50';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              color = 'text-rose-700';
              bg = 'bg-rose-50';
            } else if (line.startsWith('@@')) {
              color = 'text-blue-700 font-bold';
              bg = 'bg-blue-50/50';
            }
            return (
              <div key={i} className={`whitespace-pre px-1.5 py-0.5 rounded-xs ${color} ${bg}`}>
                {line}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
