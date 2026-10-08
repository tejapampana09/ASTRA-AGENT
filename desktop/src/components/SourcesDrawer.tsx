import React, { useState } from 'react';
import {
  X,
  Layers,
  FileCode,
  Terminal,
  Wrench,
  CheckCircle2,
  Brain,
  Search,
  Activity,
  AlertTriangle,
  Play,
  RotateCcw,
  XCircle,
} from 'lucide-react';
import { AgentEvent } from '../types';

interface SourcesDrawerProps {
  events: AgentEvent[];
  onClose: () => void;
}

export const SourcesDrawer: React.FC<SourcesDrawerProps> = ({ events, onClose }) => {
  const [activeTab, setActiveTab] = useState<'timeline' | 'tools'>('timeline');

  const toolEvents = events.filter((e) =>
    ['tool_started', 'tool_completed', 'file_changed', 'command_started', 'verification_passed'].includes(e.event_type)
  );

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'task_started':
      case 'agent_started':
        return <Play className="w-3.5 h-3.5 text-blue-600" />;
      case 'task_classified':
        return <Brain className="w-3.5 h-3.5 text-indigo-600" />;
      case 'phase_changed':
        return <Brain className="w-3.5 h-3.5 text-indigo-500" />;
      case 'investigation_started':
      case 'exploration_started':
        return <Search className="w-3.5 h-3.5 text-cyan-600" />;
      case 'evidence_found':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />;
      case 'hypothesis_created':
        return <Brain className="w-3.5 h-3.5 text-amber-500" />;
      case 'action_proposed':
      case 'tool_started':
        return <Wrench className="w-3.5 h-3.5 text-blue-500" />;
      case 'tool_completed':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
      case 'action_blocked':
        return <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />;
      case 'file_changed':
        return <FileCode className="w-3.5 h-3.5 text-blue-600" />;
      case 'command_started':
      case 'command_output':
        return <Terminal className="w-3.5 h-3.5 text-purple-600" />;
      case 'diagnosis_created':
        return <AlertTriangle className="w-3.5 h-3.5 text-orange-500" />;
      case 'replan_started':
      case 'fix_started':
        return <RotateCcw className="w-3.5 h-3.5 text-orange-500" />;
      case 'verification_started':
        return <Activity className="w-3.5 h-3.5 text-purple-500" />;
      case 'verification_passed':
      case 'task_completed':
      case 'agent_completed':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />;
      case 'verification_failed':
      case 'task_failed':
      case 'agent_failed':
        return <XCircle className="w-3.5 h-3.5 text-rose-600" />;
      default:
        return <Activity className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  const formatEventTitle = (event: AgentEvent) => {
    switch (event.event_type) {
      case 'task_started':
      case 'agent_started':
        return `Task started: ${event.data.goal ? `"${event.data.goal}"` : ''}`;
      case 'task_classified':
        return `Task classified: ${event.data.task_type || 'Engineering'} (${Math.round((event.data.confidence || 1) * 100)}%)`;
      case 'phase_changed': {
        const ph = event.data.phase || 'PLAN';
        const labels: Record<string, string> = {
          UNDERSTAND: '● Understanding request',
          INVESTIGATE: '● Investigating subsystem',
          DIAGNOSE: '● Diagnosing root cause',
          PLAN: '● Planning implementation',
          EXECUTE: '● Implementing changes',
          VERIFY: '● Verifying solution independently',
          REPLAN: '● Replanning approach',
          RECOVER: '● Recovering workspace',
          DONE: '✓ Task completed',
          BLOCKED: '✕ Task blocked',
        };
        return labels[ph] || `Phase: ${ph}`;
      }
      case 'investigation_started':
        return '● Investigating repository & tracing flow';
      case 'hypothesis_created':
        return `● Hypothesis: ${event.data.statement || 'Formulated'}`;
      case 'evidence_found':
        return `✓ Evidence: ${event.data.fact || 'Observed'}`;
      case 'action_proposed':
        return `Action: ${event.data.tool || 'proposed'}`;
      case 'action_blocked':
        return `Gating: ${event.data.reason || 'Blocked action'}`;
      case 'observation_created':
        return `Observed: ${event.data.observation || ''}`;
      case 'diagnosis_created':
        return `Diagnosis: ${event.data.diagnosis || ''}`;
      case 'replan_started':
        return `Replanning: ${event.data.reason || 'Adapting strategy'}`;
      case 'tool_started':
        return `Running ${event.data.name || 'tool'}`;
      case 'tool_completed':
        return `Completed ${event.data.name || 'tool'} (${Math.round(event.data.duration_ms || 0)}ms)`;
      case 'file_changed':
        return `File ${event.data.action || 'modified'}: ${event.data.file_path}`;
      case 'command_started':
        return `$ ${event.data.command}`;
      case 'verification_started':
        return 'Independent verification check';
      case 'verification_passed':
        return '✓ Verification PASSED';
      case 'verification_failed':
        return '✕ Verification FAILED';
      case 'task_completed':
      case 'agent_completed':
        return '✓ Task completed successfully';
      case 'task_failed':
      case 'agent_failed':
        return '✕ Task failed';
      default:
        return event.event_type.replace(/_/g, ' ');
    }
  };

  return (
    <div className="w-88 bg-[#0d1117] border-l border-[#21262d] flex flex-col h-full select-none text-[#c9d1d9] z-40 shadow-2xl font-sans">
      {/* Header */}
      <div className="p-3 border-b border-[#21262d] bg-[#161b22] flex items-center justify-between">
        <div className="flex items-center space-x-1 bg-[#0d1117] p-0.5 rounded-lg border border-[#21262d] text-xs font-medium">
          <button
            onClick={() => setActiveTab('timeline')}
            className={`px-2.5 py-1 rounded-md transition-all ${
              activeTab === 'timeline'
                ? 'bg-[#21262d] text-[#f0f6fc] shadow-xs font-semibold'
                : 'text-[#8b949e] hover:text-[#f0f6fc]'
            }`}
          >
            ⚡ Live Timeline ({events.length})
          </button>
          <button
            onClick={() => setActiveTab('tools')}
            className={`px-2.5 py-1 rounded-md transition-all ${
              activeTab === 'tools'
                ? 'bg-[#21262d] text-[#f0f6fc] shadow-xs font-semibold'
                : 'text-[#8b949e] hover:text-[#f0f6fc]'
            }`}
          >
            🛠️ Tools ({toolEvents.length})
          </button>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-[#21262d] text-[#8b949e] hover:text-[#f0f6fc] transition-colors"
          title="Close drawer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-[#0d1117]">
        {activeTab === 'timeline' ? (
          events.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#8b949e] italic">No events recorded yet.</div>
          ) : (
            events.map((ev, i) => (
              <div
                key={i}
                className="p-2.5 rounded-xl bg-[#161b22] border border-[#30363d] text-xs space-y-1 hover:border-[#8b949e]/40 transition-colors"
              >
                <div className="flex items-center space-x-2">
                  <div className="shrink-0">{getEventIcon(ev.event_type)}</div>
                  <span className="font-semibold text-[#f0f6fc] text-[11px] truncate flex-1">
                    {formatEventTitle(ev)}
                  </span>
                  <span className="text-[10px] text-[#8b949e] font-mono shrink-0">
                    {new Date(ev.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                {ev.data.details && (
                  <p className="text-[#8b949e] text-[10px] font-mono line-clamp-3 bg-[#0d1117] p-1.5 rounded border border-[#21262d]">
                    {ev.data.details}
                  </p>
                )}
                {ev.data.statement && (
                  <p className="text-amber-300 text-[10px] bg-amber-950/40 p-1.5 rounded border border-amber-800/60">
                    {ev.data.statement}
                  </p>
                )}
                {ev.data.fact && (
                  <p className="text-emerald-300 text-[10px] bg-emerald-950/40 p-1.5 rounded border border-emerald-800/60">
                    {ev.data.fact}
                  </p>
                )}
              </div>
            ))
          )
        ) : (
          toolEvents.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#8b949e] italic">No tool calls recorded yet.</div>
          ) : (
            toolEvents.map((ev, i) => (
              <div
                key={i}
                className="p-3 rounded-xl bg-[#161b22] border border-[#30363d] text-xs space-y-1.5 hover:border-[#8b949e]/40 transition-colors"
              >
                <div className="flex items-center space-x-2">
                  {ev.event_type === 'file_changed' ? (
                    <FileCode className="w-3.5 h-3.5 text-[#58a6ff] shrink-0" />
                  ) : ev.event_type === 'command_started' ? (
                    <Terminal className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                  ) : ev.event_type === 'verification_passed' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  ) : (
                    <Wrench className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  )}
                  <span className="font-semibold text-[#f0f6fc] text-[11px] truncate flex-1">
                    {ev.data.name || ev.data.command || ev.event_type}
                  </span>
                </div>
                <p className="text-[#8b949e] text-[10px] font-mono line-clamp-3 bg-[#0d1117] p-1.5 rounded border border-[#21262d]">
                  {ev.data.output || ev.data.file_path || ev.data.summary || JSON.stringify(ev.data)}
                </p>
              </div>
            ))
          )
        )}
      </div>
    </div>
  );
};
