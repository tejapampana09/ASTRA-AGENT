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
    <div className="w-80 bg-[#16171d] border-l border-[#242630] flex flex-col h-full select-none text-zinc-300 z-40">
      {/* Header */}
      <div className="p-4 border-b border-[#242630] flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <h3 className="font-semibold text-sm text-white">Sources & Tools</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-400 font-mono">
            {toolEvents.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {toolEvents.length === 0 ? (
          <div className="p-4 text-center text-xs text-zinc-500 italic">No tool calls recorded yet.</div>
        ) : (
          toolEvents.map((ev, i) => (
            <div
              key={i}
              className="p-3 rounded-xl bg-[#1c1d25] border border-[#2b2d39] text-xs space-y-1.5 hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-center space-x-2">
                {ev.event_type === 'file_changed' ? (
                  <FileCode className="w-3.5 h-3.5 text-emerald-400" />
                ) : ev.event_type === 'command_started' ? (
                  <Terminal className="w-3.5 h-3.5 text-purple-400" />
                ) : ev.event_type === 'verification_passed' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Wrench className="w-3.5 h-3.5 text-amber-400" />
                )}
                <span className="font-semibold text-white text-[11px] truncate">
                  {ev.data.name || ev.data.command || ev.event_type}
                </span>
              </div>
              <p className="text-zinc-400 text-[10px] font-mono line-clamp-2">
                {ev.data.output || ev.data.file_path || ev.data.summary || JSON.stringify(ev.data)}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
