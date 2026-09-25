import React from 'react';
import { Activity, Terminal, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { AgentEvent } from '../types';

interface Props {
  events: AgentEvent[];
}

export const Timeline: React.FC<Props> = ({ events }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col h-[400px]">
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          Execution Timeline & Live Agent Events
        </h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
          {events.length} events
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 font-mono text-xs pr-2">
        {events.length === 0 ? (
          <div className="text-slate-500 italic py-8 text-center">
            No active events. Launch a task to see real-time agent execution stream.
          </div>
        ) : (
          events.map((ev, idx) => {
            const isError = ev.event_type.includes('ERROR') || ev.event_type.includes('FAIL');
            const isSuccess = ev.event_type.includes('COMPLETED') || ev.event_type.includes('PASS');
            const isTool = ev.event_type.includes('TOOL');

            return (
              <div key={idx} className="flex gap-2.5 items-start bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
                <span className="mt-0.5 text-slate-400">
                  {isError && <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />}
                  {isSuccess && <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />}
                  {isTool && <Terminal className="w-3.5 h-3.5 text-amber-400" />}
                  {!isError && !isSuccess && !isTool && <Clock className="w-3.5 h-3.5 text-indigo-400" />}
                </span>
                <div className="flex-1 overflow-hidden">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-semibold text-slate-300 uppercase tracking-wider text-[10px]">
                      {ev.event_type}
                    </span>
                    <span className="text-slate-600 text-[10px]">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-slate-300 break-words">{ev.message}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
