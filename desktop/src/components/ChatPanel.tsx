import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Wrench,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileCode,
  Terminal,
  Brain,
  Sparkles,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { AgentState } from '../types';

export interface AgentAction {
  id: string;
  type: 'thought' | 'tool' | 'command' | 'file' | 'verification';
  title: string;
  detail?: string;
  output?: string;
  status: 'running' | 'completed' | 'failed';
  timestamp?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  tool_calls?: any[];
  verification?: {
    passed: boolean;
    summary: string;
    details: string;
  };
  thought?: string;
  files_modified?: string[];
  actions?: AgentAction[];
  timestamp: number;
}

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (msg: string) => void;
  isRunning: boolean;
  agentState: AgentState;
  activeThought?: string;
  currentAction?: string;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  onSendMessage,
  isRunning,
  agentState,
  activeThought,
  currentAction,
}) => {
  const [input, setInput] = useState('');
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, activeThought, currentAction]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isRunning) return;
    onSendMessage(trimmed);
    setInput('');
  };

  const toggleTool = (id: string) => {
    setExpandedTools((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0d1117] overflow-hidden">
      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8 text-zinc-500">
            <div className="w-14 h-14 rounded-2xl bg-cyan-950/40 border border-cyan-800/40 flex items-center justify-center text-cyan-400 mb-4 shadow-lg shadow-cyan-950/50">
              <Sparkles className="w-7 h-7" />
            </div>
            <h2 className="text-base font-semibold text-zinc-200 mb-1">ASTRA Autonomous Agent</h2>
            <p className="text-xs text-zinc-400 max-w-md mb-6">
              Give ASTRA any software-engineering goal. It will autonomously explore your repository, plan the work, edit code surgically, run tests, diagnose errors, and verify the solution.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-lg w-full text-left">
              {[
                'Fix the failing test in test_algorithms.py and run pytest',
                'Implement JWT token authentication with bcrypt password hashing',
                'Refactor database connection pool with automatic retry',
                'Find syntax or type errors in the repository and fix them',
              ].map((example, i) => (
                <button
                  key={i}
                  onClick={() => setInput(example)}
                  className="p-2.5 rounded-lg bg-[#161b22] hover:bg-zinc-800 border border-[#30363d] text-xs text-zinc-300 hover:text-white transition-colors"
                >
                  "{example}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className="space-y-2">
              {/* User Message */}
              {m.role === 'user' && (
                <div className="flex justify-end">
                  <div className="max-w-[80%] rounded-xl px-4 py-2.5 bg-cyan-600 text-white text-sm shadow-md">
                    {m.content}
                  </div>
                </div>
              )}

              {/* Assistant Message */}
              {m.role === 'assistant' && (
                <div className="flex flex-col space-y-2 max-w-[90%]">
                  {/* Thought bubble if present */}
                  {m.thought && (
                    <div className="rounded-lg bg-zinc-900/80 border border-cyan-950/60 p-3 text-xs text-zinc-300 space-y-1.5 shadow-sm">
                      <div className="flex items-center space-x-1.5 text-cyan-400 font-medium">
                        <Brain className="w-3.5 h-3.5" />
                        <span>Reasoning & Plan</span>
                      </div>
                      <div className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-zinc-300">
                        {m.thought}
                      </div>
                    </div>
                  )}

                  {/* Main text content */}
                  {m.content && (
                    <div className="rounded-xl px-4 py-3 bg-[#161b22] border border-[#30363d] text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed">
                      {m.content}
                    </div>
                  )}

                  {/* Verification Banner */}
                  {m.verification && (
                    <div
                      className={`rounded-lg p-3 text-xs border ${
                        m.verification.passed
                          ? 'bg-emerald-950/40 border-emerald-700/60 text-emerald-200'
                          : 'bg-rose-950/40 border-rose-700/60 text-rose-200'
                      }`}
                    >
                      <div className="flex items-center space-x-2 font-semibold mb-1">
                        {m.verification.passed ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <XCircle className="w-4 h-4 text-rose-400" />
                        )}
                        <span>{m.verification.passed ? 'Independent Verification Passed' : 'Independent Verification Failed'}</span>
                      </div>
                      <div className="text-[11px] text-zinc-300">{m.verification.summary}</div>
                      {m.verification.details && (
                        <div className="mt-2 p-2 rounded bg-black/40 font-mono text-[10px] text-zinc-400 overflow-x-auto whitespace-pre-wrap">
                          {m.verification.details}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Modified Files Badge */}
                  {m.files_modified && m.files_modified.length > 0 && (
                    <div className="rounded-lg bg-zinc-900 border border-zinc-800 p-2 text-xs">
                      <div className="text-zinc-400 font-medium mb-1 flex items-center space-x-1">
                        <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Files Changed ({m.files_modified.length}):</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {m.files_modified.map((f, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded bg-zinc-800 text-cyan-300 font-mono text-[11px]">
                            {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tool Execution Record */}
              {m.role === 'tool' && (
                <div className="rounded-lg bg-[#11161d] border border-zinc-800 text-xs overflow-hidden">
                  <button
                    onClick={() => toggleTool(m.id)}
                    className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-zinc-800/50 transition-colors"
                  >
                    <div className="flex items-center space-x-2">
                      <Wrench className="w-3.5 h-3.5 text-amber-400" />
                      <span className="font-mono text-zinc-300 font-medium">{m.content.split('\n')[0] || 'Tool Output'}</span>
                    </div>
                    {expandedTools[m.id] ? <ChevronDown className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />}
                  </button>
                  {expandedTools[m.id] && (
                    <div className="p-3 bg-black/40 border-t border-zinc-800 font-mono text-[11px] text-zinc-400 max-h-48 overflow-y-auto whitespace-pre-wrap">
                      {m.content}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {/* Live Working Indicator */}
        {isRunning && (
          <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-800/40 text-xs space-y-2 animate-pulse">
            <div className="flex items-center space-x-2 text-cyan-400 font-medium">
              <Sparkles className="w-4 h-4 animate-spin" />
              <span>ASTRA is working: {agentState}...</span>
            </div>
            {currentAction && <div className="text-zinc-300 text-[11px] font-mono pl-6">{currentAction}</div>}
            {activeThought && (
              <div className="text-zinc-400 text-[11px] pl-6 font-mono whitespace-pre-wrap max-h-24 overflow-hidden">
                {activeThought}
              </div>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-3 bg-[#161b22] border-t border-[#30363d]">
        <form onSubmit={handleSubmit} className="flex items-center space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isRunning}
            placeholder={
              isRunning
                ? 'ASTRA is executing autonomously...'
                : 'Enter your objective (e.g. "Fix broken auth test and run pytest")...'
            }
            className="flex-1 bg-[#0d1117] border border-[#30363d] focus:border-cyan-500 rounded-lg px-3.5 py-2.5 text-sm text-zinc-200 outline-none placeholder-zinc-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isRunning}
            className="px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white rounded-lg font-medium text-sm transition-colors flex items-center space-x-1.5 shadow-md flex-shrink-0"
          >
            <Send className="w-4 h-4" />
            <span>Run</span>
          </button>
        </form>
      </div>
    </div>
  );
};
