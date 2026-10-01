import React, { useState } from 'react';
import { X, Save, Shield, Clock, HardDrive, Cpu } from 'lucide-react';

interface SettingsModalProps {
  onClose: () => void;
  currentSettings: {
    ollamaBaseUrl: string;
    model: string;
    maxIterations: number;
    commandTimeout: number;
    permissionMode: string;
  };
  onSave: (newSettings: any) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  onClose,
  currentSettings,
  onSave,
}) => {
  const [form, setForm] = useState({ ...currentSettings });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 select-none">
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl max-w-lg w-full p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-[#30363d] pb-3">
          <h3 className="font-semibold text-white text-sm flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>ASTRA Configuration</span>
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Ollama URL */}
          <div className="space-y-1">
            <label className="text-zinc-300 font-medium flex items-center space-x-1.5">
              <HardDrive className="w-3.5 h-3.5 text-zinc-400" />
              <span>Ollama Daemon URL</span>
            </label>
            <input
              type="text"
              value={form.ollamaBaseUrl}
              onChange={(e) => setForm({ ...form, ollamaBaseUrl: e.target.value })}
              className="w-full bg-[#0d1117] border border-[#30363d] focus:border-cyan-500 rounded-lg p-2 text-zinc-200 outline-none font-mono"
            />
          </div>

          {/* Model */}
          <div className="space-y-1">
            <label className="text-zinc-300 font-medium">Default Model</label>
            <input
              type="text"
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              className="w-full bg-[#0d1117] border border-[#30363d] focus:border-cyan-500 rounded-lg p-2 text-zinc-200 outline-none font-mono"
            />
          </div>

          {/* Max Iterations & Timeout */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-zinc-300 font-medium flex items-center space-x-1">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                <span>Max Iterations</span>
              </label>
              <input
                type="number"
                min="5"
                max="100"
                value={form.maxIterations}
                onChange={(e) => setForm({ ...form, maxIterations: parseInt(e.target.value) || 30 })}
                className="w-full bg-[#0d1117] border border-[#30363d] focus:border-cyan-500 rounded-lg p-2 text-zinc-200 outline-none font-mono"
              />
            </div>

            <div className="space-y-1">
              <label className="text-zinc-300 font-medium flex items-center space-x-1">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                <span>Command Timeout (s)</span>
              </label>
              <input
                type="number"
                min="10"
                max="600"
                value={form.commandTimeout}
                onChange={(e) => setForm({ ...form, commandTimeout: parseInt(e.target.value) || 120 })}
                className="w-full bg-[#0d1117] border border-[#30363d] focus:border-cyan-500 rounded-lg p-2 text-zinc-200 outline-none font-mono"
              />
            </div>
          </div>

          {/* Permission Mode */}
          <div className="space-y-1">
            <label className="text-zinc-300 font-medium flex items-center space-x-1.5">
              <Shield className="w-3.5 h-3.5 text-zinc-400" />
              <span>Filesystem & Command Security Mode</span>
            </label>
            <select
              value={form.permissionMode}
              onChange={(e) => setForm({ ...form, permissionMode: e.target.value })}
              className="w-full bg-[#0d1117] border border-[#30363d] focus:border-cyan-500 rounded-lg p-2 text-zinc-200 outline-none font-mono"
            >
              <option value="balanced">Balanced (Auto-run safe commands; prompt on dangerous)</option>
              <option value="strict">Strict (Prompt for any terminal command or file deletion)</option>
              <option value="safe">Safe (Block all dangerous destructive operations completely)</option>
            </select>
          </div>

          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-[#30363d]">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium flex items-center space-x-1.5 shadow-md transition-colors"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save Settings</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
