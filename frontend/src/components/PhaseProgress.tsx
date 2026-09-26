import React from 'react';
import { Check, Circle, Loader2 } from 'lucide-react';
import { AgentPhase, AgentEvent } from '../types';

interface Props {
  currentPhase: AgentPhase;
  events: AgentEvent[];
  isCompleted: boolean;
  isFailed: boolean;
}

const ORDERED_PHASES: Array<{ id: AgentPhase; label: string }> = [
  { id: 'UNDERSTAND', label: 'Understand' },
  { id: 'REPOSITORY_CONTEXT', label: 'Repo Context' },
  { id: 'IMPACT_ANALYSIS', label: 'Impact' },
  { id: 'PLAN', label: 'Plan' },
  { id: 'EXECUTE', label: 'Execute' },
  { id: 'VERIFY', label: 'Verify' },
  { id: 'DEBUG', label: 'Debug' },
  { id: 'COMMIT', label: 'Commit' },
  { id: 'PUSH', label: 'Push' },
  { id: 'PR', label: 'Pull Request' },
];

export const PhaseProgress: React.FC<Props> = ({ currentPhase, events, isCompleted, isFailed }) => {
  // Compute visited phases based on actual backend event types
  const visitedPhases = React.useMemo(() => {
    const set = new Set<AgentPhase>();
    for (const ev of events) {
      const type = ev.event_type;
      if (['TASK_CREATED', 'TASK_STARTED', 'UNDERSTAND'].includes(type)) set.add('UNDERSTAND');
      if (['WORKSPACE_INITIALIZED', 'REPOSITORY_CONTEXT'].includes(type)) set.add('REPOSITORY_CONTEXT');
      if (['IMPACT_ANALYSIS'].includes(type)) set.add('IMPACT_ANALYSIS');
      if (['PLANNING', 'PLANNING_STARTED', 'PLAN_GENERATED'].includes(type)) set.add('PLAN');
      if (['TOOL_CALL_STARTED', 'TOOL_CALL_COMPLETED', 'FILE_CHANGED'].includes(type)) set.add('EXECUTE');
      if (['TEST_STARTED', 'TEST_COMPLETED', 'DIFF_GENERATED'].includes(type)) set.add('VERIFY');
      if (['DEBUG_STARTED', 'HYPOTHESIS_FORMULATED'].includes(type)) set.add('DEBUG');
      if (['COMMIT_CREATED'].includes(type)) set.add('COMMIT');
      if (['BRANCH_PUSHED'].includes(type)) set.add('PUSH');
      if (['PR_CREATED'].includes(type)) set.add('PR');
    }

    if (isCompleted) {
      set.add('UNDERSTAND');
      set.add('REPOSITORY_CONTEXT');
      set.add('PLAN');
      set.add('EXECUTE');
      set.add('VERIFY');
    }

    return set;
  }, [events, isCompleted]);

  // Find index of current phase
  const currentIndex = ORDERED_PHASES.findIndex((p) => p.id === currentPhase);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 shadow-md">
      <div className="flex items-center justify-between gap-1 overflow-x-auto pb-1 scrollbar-none">
        {ORDERED_PHASES.map((p, idx) => {
          const isVisited = visitedPhases.has(p.id) || (isCompleted && idx <= currentIndex);
          const isCurrent = p.id === currentPhase && !isCompleted && !isFailed;
          const isPending = !isVisited && !isCurrent;

          return (
            <React.Fragment key={p.id}>
              <div className="flex items-center gap-1.5 shrink-0 px-2 py-1 rounded-lg text-xs font-mono transition">
                {isCurrent ? (
                  <span className="w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500 flex items-center justify-center">
                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                  </span>
                ) : isVisited ? (
                  <span className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center">
                    <Check className="w-2.5 h-2.5" />
                  </span>
                ) : (
                  <span className="w-4 h-4 rounded-full bg-slate-800 text-slate-500 flex items-center justify-center">
                    <Circle className="w-2 h-2" />
                  </span>
                )}

                <span
                  className={`${
                    isCurrent
                      ? 'text-indigo-300 font-semibold'
                      : isVisited
                      ? 'text-slate-300'
                      : 'text-slate-500'
                  }`}
                >
                  {p.label}
                </span>
              </div>

              {idx < ORDERED_PHASES.length - 1 && (
                <div
                  className={`w-3 h-[1px] shrink-0 ${
                    isVisited ? 'bg-emerald-500/40' : 'bg-slate-800'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
