import React, { useState } from 'react';
import {
  FolderOpen,
  Square,
  Settings as SettingsIcon,
  RefreshCw,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Activity,
  Layers,
} from 'lucide-react';
import { AgentState, ModelsResponse, OllamaHealth, ProjectMetadata } from '../types';

interface HeaderProps {
  ollamaHealth?: OllamaHealth;
  modelsData?: ModelsResponse;
  selectedModel: string;
  onSelectModel: (m: string) => void;
  metadata?: ProjectMetadata;
  agentState: AgentState;
  onSelectWorkspace: () => void;
  onStopTask: () => void;
  onOpenSettings: () => void;
  onRefreshHealth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  ollamaHealth,
  modelsData,
  selectedModel,
  onSelectModel,
  metadata,
  agentState,
  onSelectWorkspace,
  onStopTask,
  onOpenSettings,
  onRefreshHealth,
}) => {
  const [showOllamaTooltip, setShowOllamaTooltip] = useState(false);
  const isRunning = agentState !== 'IDLE' && agentState !== 'COMPLETED' && agentState !== 'FAILED' && agentState !== 'CANCELLED';

  const getStateColor = (state: AgentState) => {
    switch (state) {
      case 'PLANNING':
      case 'EXPLORING':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/40';
      case 'EXECUTING':
      case 'OBSERVING':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40 animate-pulse';
      case 'VERIFYING':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/40 animate-pulse';
      case 'FIXING':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/40 animate-pulse';
      case 'COMPLETED':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
      case 'FAILED':
        return 'bg-red-500/20 text-red-400 border-red-500/40';
      case 'CANCELLED':
        return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40';
      default:
        return 'bg-zinc-800 text-zinc-400 border-zinc-700';
    }
  };

  return (
    <header className="h-14 bg-[#161b22] border-b border-[#30363d] px-4 flex items-center justify-between select-none">
      {/* Left: Branding & Workspace Picker */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-cyan-500/20 tracking-wider text-sm">
            A4
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-white text-sm tracking-wide">ASTRA</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/50">
                v4.0
              </span>
            </div>
            <div className="text-[10px] text-zinc-400">Autonomous SE Agent</div>
          </div>
        </div>

        {/* Workspace Directory */}
        <div className="h-5 w-px bg-zinc-700 mx-2" />
        <button
          onClick={onSelectWorkspace}
          className="flex items-center space-x-2 px-2.5 py-1.5 rounded-md bg-[#0d1117] hover:bg-zinc-800 border border-[#30363d] text-xs text-zinc-300 transition-colors group max-w-[280px]"
          title="Click to switch workspace folder"
        >
          <FolderOpen className="w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition-transform flex-shrink-0" />
          <span className="truncate font-mono">
            {metadata?.workspace_path ? metadata.workspace_path.split(/[\\/]/).pop() : 'Select Workspace'}
          </span>
          {metadata?.project_type && metadata.project_type !== 'unknown' && (
            <span className="text-[10px] px-1 rounded bg-zinc-800 text-zinc-400 border border-zinc-700 uppercase">
              {metadata.project_type}
            </span>
          )}
        </button>
      </div>

      {/* Center: Model Selector & Ollama Status */}
      <div className="flex items-center space-x-3">
        {/* Ollama Status Badge */}
        <div className="relative">
          <button
            onClick={() => setShowOllamaTooltip(!showOllamaTooltip)}
            onMouseEnter={() => setShowOllamaTooltip(true)}
            onMouseLeave={() => setShowOllamaTooltip(false)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono border transition-all ${
              ollamaHealth?.connected
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                : 'bg-rose-950/60 text-rose-300 border-rose-700/60'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                ollamaHealth?.connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
              }`}
            />
            <span>{ollamaHealth?.connected ? 'Ollama ● Connected' : 'Ollama ● Disconnected'}</span>
          </button>

          {/* Tooltip / Details on hover/click */}
          {showOllamaTooltip && (
            <div className="absolute top-9 left-0 w-72 p-3 bg-[#1c2128] border border-zinc-700 rounded-lg shadow-xl text-xs z-50">
              <div className="font-semibold text-white mb-1 flex items-center justify-between">
                <span>Ollama Daemon</span>
                <span className="text-[10px] text-zinc-400 font-mono">{ollamaHealth?.endpoint || 'localhost:11434'}</span>
              </div>
              <p className="text-zinc-300 text-[11px] mb-2">{ollamaHealth?.message}</p>
              {!ollamaHealth?.connected && (
                <div className="p-2 rounded bg-zinc-900 border border-zinc-800 text-[10px] text-zinc-400 space-y-1">
                  <div>1. Run <code className="text-cyan-400">ollama serve</code> in terminal</div>
                  <div>2. Or open Ollama desktop application</div>
                  <div>3. Pull model: <code className="text-cyan-400">ollama pull qwen2.5-coder:7b</code></div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Model Selection Dropdown */}
        <div className="flex items-center space-x-1.5 bg-[#0d1117] border border-[#30363d] rounded-md px-2 py-1 text-xs">
          <Cpu className="w-3.5 h-3.5 text-zinc-400" />
          <select
            value={selectedModel}
            onChange={(e) => onSelectModel(e.target.value)}
            className="bg-transparent text-zinc-200 outline-none cursor-pointer pr-1 text-xs font-mono"
          >
            {/* Ollama Models Group */}
            <optgroup label="Local Ollama">
              {modelsData?.models.ollama && modelsData.models.ollama.length > 0 ? (
                modelsData.models.ollama.map((m) => (
                  <option key={m.id} value={`ollama/${m.id}`}>
                    {m.name} {m.size ? `(${m.size})` : ''}
                  </option>
                ))
              ) : (
                <option value="ollama/qwen2.5-coder:7b">qwen2.5-coder:7b (Local)</option>
              )}
            </optgroup>

            {/* Cloud Models Group */}
            <optgroup label="Google Gemini">
              <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
              <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
              <option value="gemini-3.5-flash-lite">Gemini 3.5 Flash-Lite</option>
            </optgroup>

            <optgroup label="Groq (High-Speed)">
              <option value="groq">Llama 3.3 70B (Versatile)</option>
              <option value="qwen-2.5-coder-32b">Qwen 2.5 Coder 32B</option>
            </optgroup>

            <optgroup label="TejaAI Fine-Tuned">
              <option value="teja-gemma">TejaAI Gemma-4 2B (GPU)</option>
            </optgroup>
          </select>
        </div>
      </div>

      {/* Right: State Badge, Stop Button & Settings */}
      <div className="flex items-center space-x-3">
        {/* Agent State Badge */}
        <div className={`px-2.5 py-1 rounded-md text-xs font-mono font-medium border flex items-center space-x-1.5 ${getStateColor(agentState)}`}>
          <Activity className="w-3.5 h-3.5" />
          <span>{agentState}</span>
        </div>

        {/* Stop Button */}
        {isRunning && (
          <button
            onClick={onStopTask}
            className="flex items-center space-x-1.5 px-3 py-1 rounded-md bg-rose-600 hover:bg-rose-700 text-white font-medium text-xs shadow-md transition-all animate-pulse"
            title="Stop autonomous execution"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            <span>STOP</span>
          </button>
        )}

        {/* Refresh button */}
        <button
          onClick={onRefreshHealth}
          className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
          title="Refresh Ollama & models status"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>

        {/* Settings button */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
          title="Open Settings"
        >
          <SettingsIcon className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
