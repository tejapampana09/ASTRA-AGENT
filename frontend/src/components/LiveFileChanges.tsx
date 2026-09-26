import React, { useState } from 'react';
import { FileCode, FilePlus, FileEdit, Trash2, Eye } from 'lucide-react';
import { FileChangeItem } from '../types';

interface Props {
  files: FileChangeItem[];
  liveDiff?: string;
}

export const LiveFileChanges: React.FC<Props> = ({ files, liveDiff }) => {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const getBadge = (op: FileChangeItem['operation']) => {
    switch (op) {
      case 'created':
        return (
          <span className="w-5 h-5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-[10px] font-bold">
            A
          </span>
        );
      case 'deleted':
        return (
          <span className="w-5 h-5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center text-[10px] font-bold">
            D
          </span>
        );
      default:
        return (
          <span className="w-5 h-5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center text-[10px] font-bold">
            M
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col h-[480px]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-sky-400" />
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
            Files Modified Live
          </h3>
        </div>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
          {files.length} touched
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 flex-1 overflow-hidden">
        {/* File List */}
        <div className="md:col-span-1 overflow-y-auto space-y-1.5 pr-1 border-r border-slate-800/80">
          {files.length === 0 ? (
            <div className="py-16 text-center text-slate-500 text-xs font-mono">
              No files modified yet.
            </div>
          ) : (
            files.map((f) => {
              const isSelected = selectedFile === f.path;
              return (
                <button
                  key={f.path}
                  onClick={() => setSelectedFile(f.path)}
                  className={`w-full text-left p-2 rounded-lg text-xs font-mono flex items-center gap-2 transition cursor-pointer ${
                    isSelected
                      ? 'bg-indigo-600/20 text-white border border-indigo-500/40'
                      : 'bg-slate-950/60 text-slate-300 hover:bg-slate-800/50 border border-slate-800/60'
                  }`}
                >
                  {getBadge(f.operation)}
                  <span className="truncate flex-1">{f.path}</span>
                </button>
              );
            })
          )}
        </div>

        {/* Diff / Code Inspector */}
        <div className="md:col-span-2 overflow-y-auto bg-slate-950 p-3 rounded-lg border border-slate-800/80 font-mono text-[11px] text-slate-300">
          {liveDiff ? (
            <pre className="whitespace-pre-wrap font-mono">
              {liveDiff.split('\n').map((line, i) => {
                const isAdd = line.startsWith('+') && !line.startsWith('+++');
                const isDel = line.startsWith('-') && !line.startsWith('---');
                const isHeader = line.startsWith('@@') || line.startsWith('diff --git');

                return (
                  <div
                    key={i}
                    className={`${
                      isAdd
                        ? 'bg-emerald-950/30 text-emerald-300'
                        : isDel
                        ? 'bg-rose-950/30 text-rose-300'
                        : isHeader
                        ? 'text-indigo-400 font-bold mt-2'
                        : 'text-slate-400'
                    }`}
                  >
                    {line}
                  </div>
                );
              })}
            </pre>
          ) : (
            <div className="py-20 text-center text-slate-500">
              <Eye className="w-5 h-5 mx-auto mb-2 text-slate-600" />
              <p>Select a file to inspect modifications or wait for diff generation.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
