import React from 'react';
import { ShieldAlert } from 'lucide-react';

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
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center z-50 p-4 select-none">
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl max-w-md w-full p-5 shadow-2xl space-y-4 animate-in fade-in zoom-in duration-150 text-[#c9d1d9]">
        <div className="flex items-center space-x-3 text-amber-400">
          <div className="p-2 rounded-lg bg-amber-950/40 border border-amber-800/60">
            <ShieldAlert className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <h3 className="font-semibold text-[#f0f6fc] text-sm">Action Approval Needed</h3>
            <p className="text-[#8b949e] text-xs">ASTRA requires your authorization before running this command</p>
          </div>
        </div>

        <div className="p-3 bg-[#010409] rounded-lg border border-[#30363d] font-mono text-xs text-amber-300 break-all">
          {command?.startsWith('$') ? command : `$ ${command || 'action'}`}
        </div>

        {description && <p className="text-xs text-[#8b949e]">{description}</p>}

        <div className="flex items-center justify-end space-x-3 pt-2">
          <button
            onClick={() => onReject(approvalId)}
            className="px-4 py-2 rounded-lg bg-[#21262d] hover:bg-[#30363d] text-[#c9d1d9] text-xs font-medium transition-colors border border-[#30363d]"
          >
            Reject
          </button>
          <button
            onClick={() => onApprove(approvalId)}
            className="px-4 py-2 rounded-lg bg-[#1f6feb] hover:bg-[#388bfd] text-white text-xs font-semibold shadow-xs transition-colors"
          >
            Allow Execution
          </button>
        </div>
      </div>
    </div>
  );
};
