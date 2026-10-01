import React from 'react';
import { AlertTriangle, ShieldAlert } from 'lucide-react';

interface ApprovalModalProps {
  approvalId: string;
  command: string;
  description?: string;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  approvalId,
  command,
  description,
  onApprove,
  onReject,
}) => {
  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 select-none">
      <div className="bg-[#161b22] border border-amber-500/50 rounded-xl max-w-md w-full p-5 shadow-2xl space-y-4 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center space-x-3 text-amber-400">
          <div className="p-2 rounded-lg bg-amber-950/60 border border-amber-700/50">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-semibold text-white text-sm">Dangerous Action Approval</h3>
            <p className="text-zinc-400 text-xs">ASTRA requires your authorization before running this command</p>
          </div>
        </div>

        <div className="p-3 bg-[#0d1117] rounded-lg border border-zinc-800 font-mono text-xs text-rose-300 break-all">
          $ {command}
        </div>

        {description && <p className="text-xs text-zinc-300">{description}</p>}

        <div className="flex items-center justify-end space-x-3 pt-2">
          <button
            onClick={() => onReject(approvalId)}
            className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors"
          >
            Reject
          </button>
          <button
            onClick={() => onApprove(approvalId)}
            className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-lg shadow-amber-600/30 transition-colors"
          >
            Allow Execution
          </button>
        </div>
      </div>
    </div>
  );
};
