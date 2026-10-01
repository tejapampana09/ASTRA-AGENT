import React from 'react';
import { X, BarChart2, Zap, Database } from 'lucide-react';

interface UsageDashboardModalProps {
  onClose: () => void;
  tokensCount?: number;
  requestsCount?: number;
}

export const UsageDashboardModal: React.FC<UsageDashboardModalProps> = ({
  onClose,
  tokensCount = 52672,
  requestsCount = 2590,
}) => {
  const chartBars = [
    { label: 'Jan', val: 35, color: 'bg-slate-700' },
    { label: 'Feb', val: 55, color: 'bg-slate-800' },
    { label: 'Mar', val: 20, color: 'bg-slate-600' },
    { label: 'Apr', val: 75, color: 'bg-slate-900' },
    { label: 'May', val: 90, color: 'bg-blue-600' },
    { label: 'Jun', val: 60, color: 'bg-slate-800' },
    { label: 'Jul', val: 85, color: 'bg-slate-900' },
  ];

  return (
    <div className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs flex items-center justify-center z-50 p-4 select-none">
      <div className="bg-white border border-slate-200 rounded-2xl max-w-2xl w-full p-6 shadow-xl space-y-5 animate-in fade-in zoom-in duration-150 text-slate-800">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <BarChart2 className="w-5 h-5 text-slate-800" />
              <span>Usage Dashboard</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">View your model token usage and autonomous tasks</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Top Metric Cards */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[11px] font-medium text-slate-500 flex items-center space-x-1.5">
              <Database className="w-3.5 h-3.5 text-slate-700" />
              <span>Total Tokens Processed</span>
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900">
              {tokensCount.toLocaleString()}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[11px] font-medium text-slate-500 flex items-center space-x-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-600" />
              <span>Total Autonomous Requests</span>
            </div>
            <div className="text-2xl font-bold font-mono text-slate-900">
              {requestsCount.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Bar Chart Representation */}
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
          <div className="text-xs font-semibold text-slate-800">Activity Breakdown</div>
          <div className="h-36 flex items-end justify-between gap-3 pt-4 px-2">
            {chartBars.map((bar, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                <div
                  className={`w-full rounded-t-sm transition-all duration-300 ${bar.color}`}
                  style={{ height: `${bar.val}%` }}
                />
                <span className="text-[10px] text-slate-500 font-mono">{bar.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
