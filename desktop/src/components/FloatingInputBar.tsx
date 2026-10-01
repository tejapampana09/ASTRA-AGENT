import React, { useState } from 'react';
import {
  Sparkles,
  FileCode,
  Terminal,
  Paperclip,
  Mic,
  ArrowUp,
  Square,
  ChevronDown,
} from 'lucide-react';
import { AgentState, ModelsResponse } from '../types';

interface FloatingInputBarProps {
  onSendMessage: (goal: string) => void;
  isRunning: boolean;
  onStop: () => void;
  selectedModel: string;
  onSelectModel: (m: string) => void;
  modelsData?: ModelsResponse;
  onToggleTerminal: () => void;
  onToggleDiff: () => void;
  onSelectWorkspace: () => void;
  agentState: AgentState;
}

export const FloatingInputBar: React.FC<FloatingInputBarProps> = ({
  onSendMessage,
  isRunning,
  onStop,
  selectedModel,
  onSelectModel,
  modelsData,
  onToggleTerminal,
  onToggleDiff,
  onSelectWorkspace,
  agentState,
}) => {
  const [input, setInput] = useState('');
  const [showModelDropdown, setShowModelDropdown] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isRunning) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const cleanModelName = (name: string) => {
    return name
      .replace('ollama/', '')
      .replace('gemini/', '')
      .replace('groq/', '')
      .replace('teja/', '');
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4 select-none">
      <form
        onSubmit={handleSubmit}
        className="rounded-2xl bg-white border border-slate-300 antigravity-input-shadow p-3 transition-all duration-200"
      >
        {/* Top Input Row */}
        <div className="flex items-center space-x-2.5 px-1 pt-0.5">
          <Sparkles className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isRunning}
            placeholder={
              isRunning
                ? `ASTRA is executing: ${agentState}...`
                : 'Ask ASTRA anything, plan an architecture, or execute tasks...'
            }
            className="w-full bg-transparent text-sm text-slate-900 placeholder-slate-400 outline-none disabled:opacity-50"
          />
        </div>

        {/* Bottom Toolbar Row */}
        <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-slate-100 text-xs">
          {/* Left Action Buttons */}
          <div className="flex items-center space-x-1.5">
            <button
              type="button"
              onClick={onToggleTerminal}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
              title="Toggle Terminal Execution panel"
            >
              <Terminal className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={onToggleDiff}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
              title="Toggle Git Diff viewer"
            >
              <FileCode className="w-4 h-4" />
            </button>
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center space-x-2 relative">
            {/* Model Pill Dropdown Trigger */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowModelDropdown(!showModelDropdown)}
                className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200/80 border border-slate-200 text-slate-700 font-mono text-[11px] transition-colors"
              >
                <span className="w-2 h-2 rounded-full bg-slate-900" />
                <span className="truncate max-w-[120px]">{cleanModelName(selectedModel)}</span>
                <ChevronDown className="w-3 h-3 text-slate-400" />
              </button>

              {/* Model Dropdown Menu */}
              {showModelDropdown && (
                <div className="absolute bottom-9 right-0 w-64 bg-white border border-slate-200 rounded-xl shadow-xl p-2 z-50 text-xs space-y-2 max-h-80 overflow-y-auto">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase px-2 py-0.5">
                    Select Active Model Brain
                  </div>

                  {/* Groq Cloud */}
                  <div>
                    <div className="flex items-center justify-between text-[10px] text-slate-700 font-semibold px-2 pt-1">
                      <span>⚡ Groq Cloud (27B - 120B)</span>
                      <span className="text-[9px] text-slate-400">Fast & Free</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        onSelectModel('groq/qwen/qwen3.8-27b');
                        setShowModelDropdown(false);
                      }}
                      className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-100 text-slate-700 text-[11px] flex items-center justify-between transition-colors"
                    >
                      <span className="font-mono font-medium">qwen3.8-27b</span>
                      <span className="text-[9px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">27B Coder</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        onSelectModel('groq/openai/gpt-oss-120b');
                        setShowModelDropdown(false);
                      }}
                      className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-100 text-slate-700 text-[11px] flex items-center justify-between transition-colors"
                    >
                      <span className="font-mono font-medium">gpt-oss-120b</span>
                      <span className="text-[9px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">120B Brain</span>
                    </button>
                  </div>

                  {/* Google Gemini */}
                  <div className="border-t border-slate-100 pt-1">
                    <div className="flex items-center justify-between text-[10px] text-slate-700 font-semibold px-2">
                      <span>✦ Google Gemini</span>
                      <span className="text-[9px] text-slate-400">1M Context</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        onSelectModel('gemini/gemini-3.8-flash');
                        setShowModelDropdown(false);
                      }}
                      className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-100 text-slate-700 text-[11px] flex items-center justify-between transition-colors"
                    >
                      <span className="font-mono font-medium">gemini-3.8-flash</span>
                      <span className="text-[9px] text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">Frontier</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        onSelectModel('gemini/gemini-2.5-pro');
                        setShowModelDropdown(false);
                      }}
                      className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-100 text-slate-700 text-[11px] flex items-center justify-between transition-colors"
                    >
                      <span className="font-mono font-medium">gemini-2.5-pro</span>
                      <span className="text-[9px] text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">Deep Reasoning</span>
                    </button>
                  </div>

                  {/* Ollama Local Models */}
                  {modelsData?.models.ollama && modelsData.models.ollama.length > 0 && (
                    <div className="border-t border-slate-100 pt-1">
                      <div className="flex items-center justify-between text-[10px] text-slate-700 font-semibold px-2">
                        <span>🦙 Ollama Local</span>
                        <span className="text-[9px] text-slate-400">Offline</span>
                      </div>
                      {modelsData.models.ollama.map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            onSelectModel(`ollama/${m.id}`);
                            setShowModelDropdown(false);
                          }}
                          className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-100 text-slate-700 font-mono text-[11px] truncate flex items-center justify-between transition-colors"
                        >
                          <span className="truncate">{m.name}</span>
                          <span className="text-[9px] text-slate-400 ml-1">{m.size || 'local'}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Folder / Attachment icon */}
            <button
              type="button"
              onClick={onSelectWorkspace}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
              title="Select project workspace folder"
            >
              <Paperclip className="w-4 h-4" />
            </button>

            {/* Voice / Mic */}
            <button
              type="button"
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
              title="Voice input"
            >
              <Mic className="w-4 h-4" />
            </button>

            {/* Submit / Stop Action Button */}
            {isRunning ? (
              <button
                type="button"
                onClick={onStop}
                className="w-8 h-8 rounded-xl bg-rose-600 hover:bg-rose-700 text-white flex items-center justify-center shadow-xs transition-all animate-pulse"
                title="Stop execution"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="w-8 h-8 rounded-xl bg-slate-900 hover:bg-slate-800 disabled:opacity-30 text-white flex items-center justify-center shadow-xs transition-all"
                title="Send instruction"
              >
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
};
