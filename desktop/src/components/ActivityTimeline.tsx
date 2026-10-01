import React from 'react';
import {
  Activity,
  Play,
  Brain,
  Search,
  Wrench,
  CheckCircle2,
  XCircle,
  FileCode,
  Terminal,
  RotateCcw,
  AlertTriangle,
} from 'lucide-react';
import { AgentEvent } from '../types';

interface ActivityTimelineProps {
  events: AgentEvent[];
}

export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({ events }) => {
  const getEventIcon = (type: string) => {
    switch (type) {
      case 'agent_started':
        return <Play className="w-3.5 h-3.5 text-cyan-400" />;
      case 'planning':
        return <Brain className="w-3.5 h-3.5 text-blue-400" />;
      case 'exploration_started':
        return <Search className="w-3.5 h-3.5 text-indigo-400" />;
      case 'tool_started':
      case 'tool_completed':
        return <Wrench className="w-3.5 h-3.5 text-amber-400" />;
      case 'file_changed':
        return <FileCode className="w-3.5 h-3.5 text-emerald-400" />;
      case 'command_started':
      case 'command_output':
        return <Terminal className="w-3.5 h-3.5 text-purple-400" />;
      case 'verification_started':
        return <Activity className="w-3.5 h-3.5 text-purple-400" />;
      case 'verification_passed':
      case 'agent_completed':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
      case 'verification_failed':
      case 'agent_failed':
        return <XCircle className="w-3.5 h-3.5 text-rose-400" />;
      case 'fix_started':
        return <RotateCcw className="w-3.5 h-3.5 text-orange-400" />;
      default:
        return <Activity className="w-3.5 h-3.5 text-zinc-400" />;
    }
  };

  const formatEventTitle = (event: AgentEvent) => {
    switch (event.event_type) {
      case 'agent_started':
        return 'Task started';
      case 'planning':
        return 'Reasoning & planning';
      case 'exploration_started':
        return 'Repository exploration';
      case 'tool_started':
        return `Executing ${event.data.name || 'tool'}`;
      case 'tool_completed':
        return `Completed ${event.data.name || 'tool'} (${Math.round(event.data.duration_ms || 0)}ms)`;
      case 'file_changed':
        return `File ${event.data.action || 'modified'}: ${event.data.file_path}`;
      case 'command_started':
        return `Running command: ${event.data.command}`;
      case 'verification_started':
        return 'Independent verification check';
      case 'verification_passed':
        return 'Verification PASSED';
      case 'verification_failed':
        return 'Verification FAILED';
      case 'fix_started':
        return `Self-healing fix loop (attempt ${event.data.attempt || 1})`;
      case 'agent_completed':
        return 'Task completed successfully';
      case 'agent_failed':
        return 'Task halted with error';
      case 'agent_cancelled':
        return 'Task cancelled by user';
      default:
        return event.event_type;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#161b22] border-l border-[#30363d] w-80 select-none">
      <div className="p-3 border-b border-[#30363d] flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Activity Timeline</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
          {events.length} events
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {events.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center text-xs text-zinc-500">
            No activity yet. Enter a task to begin.
          </div>
        ) : (
          events.map((ev, idx) => (
            <div key={idx} className="flex space-x-2.5 text-xs">
              <div className="mt-0.5 flex-shrink-0">{getEventIcon(ev.event_type)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-zinc-300 truncate">{formatEventTitle(ev)}</span>
                  <span className="text-[10px] text-zinc-500 font-mono flex-shrink-0">
                    {new Date(ev.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                {ev.data.details && (
                  <p className="text-[11px] text-zinc-400 line-clamp-2 mt-0.5 font-mono">{ev.data.details}</p>
                )}
                {ev.data.error && (
                  <p className="text-[11px] text-rose-400 line-clamp-2 mt-0.5 font-mono">{ev.data.error}</p>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
