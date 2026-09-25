import React from 'react';
import { AlertCircle, Check, X } from 'lucide-react';
import { ApprovalTicket } from '../types';

interface Props {
  ticket: ApprovalTicket;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export const ApprovalModal: React.FC<Props> = ({ ticket, onApprove, onReject }) => {
  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full p-6 shadow-2xl">
        <div className="flex items-center gap-3 mb-4 text-amber-400">
          <AlertCircle className="w-6 h-6" />
          <h3 className="text-lg font-bold text-white">Human Approval Required</h3>
        </div>
        <p className="text-sm text-slate-300 mb-4">
          The agent has planned an action with risk level{' '}
          <span className="font-bold text-rose-400 uppercase tracking-wider">{ticket.risk_level}</span>.
        </p>

        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs font-mono text-slate-300 space-y-2 mb-6">
          <div>
            <span className="text-slate-500">Tool:</span> {ticket.tool_name}
          </div>
          <div>
            <span className="text-slate-500">Task:</span> {ticket.task_id}
          </div>
          <div>
            <span className="text-slate-500">Arguments:</span>
            <pre className="text-amber-300 mt-1 whitespace-pre-wrap">
              {JSON.stringify(ticket.arguments, null, 2)}
            </pre>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={() => onReject(ticket.id)}
            className="flex items-center gap-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm font-medium transition cursor-pointer"
          >
            <X className="w-4 h-4 text-rose-400" />
            Reject
          </button>
          <button
            onClick={() => onApprove(ticket.id)}
            className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition cursor-pointer"
          >
            <Check className="w-4 h-4" />
            Authorize Execution
          </button>
        </div>
      </div>
    </div>
  );
};
