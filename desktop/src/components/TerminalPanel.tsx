import React, { useRef, useEffect } from 'react';
import { Terminal, Trash2, Square } from 'lucide-react';

interface TerminalPanelProps {
  logs: string[];
  onClear: () => void;
  isRunning?: boolean;
  onStop?: () => void;
}

export const TerminalPanel: React.FC<TerminalPanelProps> = ({
  logs,
  onClear,
  isRunning,
  onStop,
}) => {
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="h-52 bg-white border-t border-slate-200 flex flex-col font-mono text-xs select-text">
      {/* Header Bar */}
      <div className="h-8 bg-slate-50 px-3 border-b border-slate-200 flex items-center justify-between select-none">
        <div className="flex items-center space-x-2 text-slate-700">
          <Terminal className="w-3.5 h-3.5 text-slate-600" />
          <span className="font-semibold text-[11px] uppercase tracking-wider">Terminal Execution</span>
        </div>
        <div className="flex items-center space-x-2">
          {isRunning && onStop && (
            <button
              onClick={onStop}
              className="flex items-center space-x-1 px-2 py-0.5 rounded bg-rose-600 hover:bg-rose-700 text-white text-[10px] transition-colors"
            >
              <Square className="w-2.5 h-2.5 fill-current" />
              <span>Kill</span>
            </button>
          )}
          <button
            onClick={onClear}
            className="p-1 rounded hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-colors"
            title="Clear terminal"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Output Console */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1 bg-slate-950 text-slate-200">
        {logs.length === 0 ? (
          <div className="text-slate-500 select-none">$ Terminal ready. Commands executed by ASTRA will appear here.</div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="whitespace-pre-wrap leading-relaxed text-[11px]">
              {log.startsWith('$ ') ? (
                <span className="text-blue-400 font-bold">{log}</span>
              ) : log.includes('[Exit code 0]') ? (
                <span className="text-emerald-400">{log}</span>
              ) : log.includes('Error:') || log.includes('[STDERR]') || log.includes('FAILED') ? (
                <span className="text-rose-400">{log}</span>
              ) : (
                <span className="text-slate-300">{log}</span>
              )}
            </div>
          ))
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
};
