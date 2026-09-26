import React, { useState } from 'react';
import { Terminal, CheckCircle2, XCircle, Copy, Check } from 'lucide-react';

interface Props {
  commands?: Array<{
    tool_name?: string;
    command?: string;
    arguments?: any;
    result?: string;
    error?: string;
    duration_ms?: number;
  }>;
  rawOutput?: string;
  isRunning?: boolean;
}

export const TerminalOutput: React.FC<Props> = ({ commands = [], rawOutput, isRunning }) => {
  const [copied, setCopied] = useState(false);

  const fullText = rawOutput || commands.map((c) => `$ ${c.command || c.tool_name}\n${c.result || c.error || ''}`).join('\n\n');

  const handleCopy = () => {
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col h-[320px]">
      <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          Execution Terminal Output
          {isRunning && (
            <span className="flex items-center gap-1.5 ml-2 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full font-mono font-normal">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              SESSION ACTIVE
            </span>
          )}
        </h3>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 transition bg-slate-800 px-2 py-1 rounded"
        >
          {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-950 p-3 rounded-lg border border-slate-800/80 font-mono text-[11px] text-slate-300 space-y-2 whitespace-pre-wrap">
        {commands.length === 0 && !rawOutput ? (
          isRunning ? (
            <div className="py-8 text-center flex flex-col items-center justify-center gap-2 text-slate-400">
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                Autonomous agent session active in sandbox...
              </div>
              <p className="text-[11px] text-slate-500">
                Inspecting repository files, analyzing logic, and preparing test runs.
              </p>
            </div>
          ) : (
            <div className="text-slate-600 italic py-6 text-center">
              No terminal commands or test outputs recorded yet.
            </div>
          )
        ) : rawOutput ? (
          <div>{rawOutput}</div>
        ) : (
          commands.map((cmd, idx) => (
            <div key={idx} className="border-b border-slate-900 pb-2 mb-2 last:border-b-0">
              <div className="flex items-center gap-1.5 text-indigo-400 font-semibold mb-1">
                <span>$</span>
                <span>{cmd.command || `${cmd.tool_name}(${JSON.stringify(cmd.arguments || {})})`}</span>
                {cmd.duration_ms ? (
                  <span className="text-[10px] text-slate-600 ml-auto">{Math.round(cmd.duration_ms)}ms</span>
                ) : null}
              </div>
              {cmd.result && <div className="text-slate-300 pl-3">{cmd.result}</div>}
              {cmd.error && <div className="text-rose-400 pl-3">{cmd.error}</div>}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
