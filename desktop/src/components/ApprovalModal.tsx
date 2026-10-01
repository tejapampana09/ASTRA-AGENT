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
    <div className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs flex items-center justify-center z-50 p-4 select-none">
      <div className="bg-white border border-amber-200 rounded-xl max-w-md w-full p-5 shadow-xl space-y-4 animate-in fade-in zoom-in duration-150 text-slate-800">
        <div className="flex items-center space-x-3 text-amber-700">
          <div className="p-2 rounded-lg bg-amber-50 border border-amber-200">
            <ShieldAlert className="w-6 h-6 text-amber-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 text-sm">Action Approval Needed</h3>
            <p className="text-slate-500 text-xs">ASTRA requires your authorization before running this command</p>
          </div>
        </div>

        <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono text-xs text-amber-300 break-all">
          {command?.startsWith('$') ? command : `$ ${command || 'action'}`}
        </div>

        {description && <p className="text-xs text-slate-600">{description}</p>}

        <div className="flex items-center justify-end space-x-3 pt-2">
          <button
            onClick={() => onReject(approvalId)}
            className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition-colors"
          >
            Reject
          </button>
          <button
            onClick={() => onApprove(approvalId)}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            Allow Execution
          </button>
        </div>
      </div>
    </div>
  );
};
