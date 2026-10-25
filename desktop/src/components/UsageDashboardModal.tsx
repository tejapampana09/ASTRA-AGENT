import React, { useEffect, useState } from 'react';
import { X, BarChart2 } from 'lucide-react';
import { api, UsageSummary } from '../api';

export const UsageDashboardModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let disposed = false;
    api.getUsage().then((data) => { if (!disposed) setUsage(data); })
      .catch((err: Error) => { if (!disposed) setError(err.message); });
    return () => { disposed = true; };
  }, []);
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-[#161b22] border border-[#30363d] rounded-2xl max-w-2xl w-full p-6 space-y-5 text-[#c9d1d9]">
        <div className="flex justify-between items-center">
          <h2 className="font-bold flex gap-2"><BarChart2 className="w-5 h-5" />Recorded usage</h2>
          <button onClick={onClose} aria-label="Close usage"><X className="w-5 h-5" /></button>
        </div>
        {error && <p role="alert" className="text-red-300">{error}</p>}
        {!usage && !error && <p>Loading usage…</p>}
        {usage && <>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-[#0d1117] rounded-xl"><p>Request attempts</p><strong className="text-2xl">{usage.requests.toLocaleString()}</strong></div>
            <div className="p-4 bg-[#0d1117] rounded-xl"><p>Reported tokens</p><strong className="text-2xl">{usage.tokens.toLocaleString()}</strong></div>
          </div>
          <p className="text-sm">{usage.requests_today} attempts today. Token metadata available for {usage.requests_with_token_usage} requests.</p>
          <table className="w-full text-sm text-left"><thead><tr><th>Provider</th><th>Recorded attempts</th></tr></thead>
            <tbody>{Object.entries(usage.providers).map(([provider, count]) => <tr key={provider}><td>{provider}</td><td>{count}</td></tr>)}</tbody>
          </table>
          {usage.requests === 0 && <p>No requests recorded yet.</p>}
          <p className="text-sm">Local caps: {usage.local_limits.requests_per_session} requests/session; Gemini {usage.local_limits.gemini_rpm_per_model}/minute and {usage.local_limits.gemini_rpd_per_model}/day per model. A cap of 0 means disabled.</p>
          <p className="text-xs text-[#8b949e]">{usage.scope} Check Google AI Studio for authoritative project limits and remaining quota.</p>
        </>}
      </div>
    </div>
  );
};
