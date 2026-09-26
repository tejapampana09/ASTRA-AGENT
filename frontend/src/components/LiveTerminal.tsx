import React, { useState, useRef, useEffect } from 'react';
import { Terminal, Copy, Check, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { TerminalCommandItem } from '../types';

interface Props {
  commands: TerminalCommandItem[];
  isRunning: boolean;
}

export const LiveTerminal: React.FC<Props> = ({ commands, isRunning }) => {
  const [copied, setCopied] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [commands]);

  const handleCopy = () => {
    const text = commands
      .map((c) => `$ ${c.command}\n${c.output || (c.status === 'running' ? 'Running...' : '')}`)
      .join('\n\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col h-[480px]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
            Execution Shell Terminal
          </h3>
          {isRunning && (
            <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              SESSION ACTIVE
            </span>
          )}
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 transition bg-slate-800 px-2 py-1 rounded cursor-pointer"
        >
          {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-950 p-3.5 rounded-lg border border-slate-800/80 font-mono text-[11px] text-slate-300 space-y-4">
        {commands.length === 0 ? (
          isRunning ? (
            <div className="py-16 text-center flex flex-col items-center justify-center gap-2 text-slate-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <p className="text-emerald-400 font-medium">Session initialized in workspace sandbox...</p>
              <p className="text-[11px] text-slate-500">Awaiting initial command invocation.</p>
            </div>
          ) : (
            <div className="py-16 text-center text-slate-500">
              No terminal or test commands dispatched for this task yet.
            </div>
          )
        ) : (
          commands.map((cmd, idx) => {
            const isLast = idx === commands.length - 1;

            return (
              <div key={cmd.id || idx} className="space-y-1">
                <div className="flex items-center justify-between text-slate-400">
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 select-none">$</span>
                    <span className="text-slate-200 font-semibold">{cmd.command}</span>
                  </div>

                  <div className="flex items-center gap-2 text-[10px]">
                    {cmd.status === 'running' ? (
                      <span className="flex items-center gap-1 text-amber-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                        Running...
                      </span>
                    ) : cmd.status === 'completed' ? (
                      <span className="flex items-center gap-1 text-emerald-400">
                        <CheckCircle2 className="w-3 h-3" />
                        {cmd.duration_ms ? `${cmd.duration_ms}ms` : '0ms'}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-rose-400">
                        <XCircle className="w-3 h-3" />
                        Exit {cmd.exit_code}
                      </span>
                    )}
                  </div>
                </div>

                {cmd.output && (
                  <pre className="text-slate-400 whitespace-pre-wrap pl-4 border-l border-slate-800/80 max-h-48 overflow-y-auto">
                    {cmd.output}
                  </pre>
                )}

                {cmd.status === 'running' && isLast && (
                  <div className="flex items-center gap-1 pl-4 text-emerald-400">
                    <span className="w-1.5 h-3.5 bg-emerald-400 animate-pulse" />
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
