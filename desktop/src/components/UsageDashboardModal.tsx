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
    { label: 'Jan', val: 35, color: 'bg-purple-500' },
    { label: 'Feb', val: 55, color: 'bg-violet-400' },
    { label: 'Mar', val: 20, color: 'bg-cyan-500' },
    { label: 'Apr', val: 75, color: 'bg-purple-600' },
    { label: 'May', val: 90, color: 'bg-fuchsia-500' },
    { label: 'Jun', val: 60, color: 'bg-violet-500' },
    { label: 'Jul', val: 85, color: 'bg-purple-500' },
  ];

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-50 p-4 select-none">
      <div className="bg-[#16171d] border border-[#2b2d39] rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#242630] pb-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center space-x-2">
              <BarChart2 className="w-5 h-5 text-emerald-400" />
              <span>Usage Dashboard</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">View your model token usage and autonomous tasks</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Top Metric Cards */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-[#1b1c24] border border-[#282a35] space-y-1">
            <div className="text-[11px] font-medium text-zinc-400 flex items-center space-x-1.5">
              <Database className="w-3.5 h-3.5 text-violet-400" />
              <span>Total Tokens Processed</span>
            </div>
            <div className="text-2xl font-bold font-mono text-white">
              {tokensCount.toLocaleString()}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#1b1c24] border border-[#282a35] space-y-1">
            <div className="text-[11px] font-medium text-zinc-400 flex items-center space-x-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Total Autonomous Requests</span>
            </div>
            <div className="text-2xl font-bold font-mono text-white">
              {requestsCount.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Bar Chart Representation */}
        <div className="p-4 rounded-xl bg-[#1b1c24] border border-[#282a35] space-y-3">
          <div className="text-xs font-semibold text-zinc-300">Activity Breakdown</div>
          <div className="h-36 flex items-end justify-between gap-3 pt-4 px-2">
            {chartBars.map((bar, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                <div
                  className={`w-full rounded-t-md ${bar.color} opacity-80 hover:opacity-100 transition-all`}
                  style={{ height: `${bar.val}%` }}
                />
                <span className="text-[10px] text-zinc-500 font-mono">{bar.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
