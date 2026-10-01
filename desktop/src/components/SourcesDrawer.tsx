import React from 'react';
import { X, Layers, FileCode, Terminal, Wrench, CheckCircle2 } from 'lucide-react';
import { AgentEvent } from '../types';

interface SourcesDrawerProps {
  events: AgentEvent[];
  onClose: () => void;
}

export const SourcesDrawer: React.FC<SourcesDrawerProps> = ({ events, onClose }) => {
  const toolEvents = events.filter((e) =>
    ['tool_started', 'tool_completed', 'file_changed', 'command_started', 'verification_passed'].includes(e.event_type)
  );

  return (
    <div className="w-80 bg-white border-l border-slate-200 flex flex-col h-full select-none text-slate-700 z-40 shadow-md">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-slate-700" />
          <h3 className="font-semibold text-sm text-slate-900">Sources & Tools</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-700 font-mono">
            {toolEvents.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {toolEvents.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-400 italic">No tool calls recorded yet.</div>
        ) : (
          toolEvents.map((ev, i) => (
            <div
              key={i}
              className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1.5 hover:border-slate-300 transition-colors"
            >
              <div className="flex items-center space-x-2">
                {ev.event_type === 'file_changed' ? (
                  <FileCode className="w-3.5 h-3.5 text-blue-600" />
                ) : ev.event_type === 'command_started' ? (
                  <Terminal className="w-3.5 h-3.5 text-slate-700" />
                ) : ev.event_type === 'verification_passed' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <Wrench className="w-3.5 h-3.5 text-amber-600" />
                )}
                <span className="font-semibold text-slate-900 text-[11px] truncate">
                  {ev.data.name || ev.data.command || ev.event_type}
                </span>
              </div>
              <p className="text-slate-600 text-[10px] font-mono line-clamp-2">
                {ev.data.output || ev.data.file_path || ev.data.summary || JSON.stringify(ev.data)}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
