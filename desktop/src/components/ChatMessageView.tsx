import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  Copy,
  Check,
  Maximize2,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Brain,
  Layers,
  CheckCircle2,
  XCircle,
  Terminal,
  FileCode,
  Wrench,
  Shield,
  ChevronDown,
  ChevronRight,
  Activity,
} from 'lucide-react';
import { ChatMessage, AgentAction } from './ChatPanel';

interface ChatMessageViewProps {
  message: ChatMessage;
  onOpenSourcesDrawer?: () => void;
  sourcesCount?: number;
}

const ActionStepCard: React.FC<{ action: AgentAction }> = ({ action }) => {
  const [expanded, setExpanded] = useState<boolean>(action.status === 'running' || !!action.output);
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopyOutput = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (action.output) {
      navigator.clipboard.writeText(action.output);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <div className="rounded-xl bg-[#12131b] border border-[#232536] hover:border-[#2e3146] overflow-hidden my-1.5 shadow-sm text-xs transition-colors">
      <div
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-3.5 py-2 bg-[#171822] hover:bg-[#1c1e2b] cursor-pointer transition-colors"
      >
        <div className="flex items-center space-x-2.5 truncate max-w-[80%]">
          {action.type === 'command' && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-700/50 text-cyan-300 font-mono text-[10px] font-semibold">
              <Terminal className="w-3 h-3 shrink-0" />
              <span>CMD</span>
            </span>
          )}
          {action.type === 'file' && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-700/50 text-emerald-300 font-mono text-[10px] font-semibold">
              <FileCode className="w-3 h-3 shrink-0" />
              <span>FILE</span>
            </span>
          )}
          {action.type === 'tool' && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-950/80 border border-purple-700/50 text-purple-300 font-mono text-[10px] font-semibold">
              <Wrench className="w-3 h-3 shrink-0" />
              <span>TOOL</span>
            </span>
          )}
          {action.type === 'thought' && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-violet-950/80 border border-violet-700/50 text-violet-300 font-mono text-[10px] font-semibold">
              <Brain className="w-3 h-3 shrink-0" />
              <span>PLAN</span>
            </span>
          )}
          {action.type === 'verification' && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-700/50 text-amber-300 font-mono text-[10px] font-semibold">
              <Shield className="w-3 h-3 shrink-0" />
              <span>VERIFY</span>
            </span>
          )}

          <span className="font-mono font-medium text-zinc-100 truncate text-[12px]">{action.title}</span>
          {action.detail && (
            <span className="text-zinc-500 font-mono text-[11px] truncate">{action.detail}</span>
          )}
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1 ${
              action.status === 'running'
                ? 'bg-purple-950/90 text-purple-300 border border-purple-600/60 animate-pulse'
                : action.status === 'completed'
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60'
                : 'bg-rose-950/80 text-rose-300 border border-rose-700/60'
            }`}
          >
            {action.status === 'completed' && <Check className="w-2.5 h-2.5" />}
            <span>{action.status}</span>
          </span>
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
          )}
        </div>
      </div>

      {expanded && action.output && (
        <div className="relative bg-[#0d0e14] border-t border-[#202230]">
          <div className="flex items-center justify-between px-3 py-1 bg-[#13141d] border-b border-[#202230] text-[10px] text-zinc-500">
            <span>Output</span>
            <button
              onClick={handleCopyOutput}
              className="hover:text-zinc-300 flex items-center gap-1 transition-colors"
              title="Copy output"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <pre className="p-3 font-mono text-[11px] text-zinc-300 overflow-x-auto max-h-64 leading-relaxed whitespace-pre-wrap select-text">
            {action.output}
          </pre>
        </div>
      )}
    </div>
  );
};

export const ChatMessageView: React.FC<ChatMessageViewProps> = ({
  message,
  onOpenSourcesDrawer,
  sourcesCount = 0,
}) => {
  const [copied, setCopied] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Helper to extract code blocks
  const parseCodeBlocks = (content: string) => {
    if (!content) return [];
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push({ type: 'text', content: content.slice(lastIndex, match.index) });
      }
      parts.push({
        type: 'code',
        language: match[1] || 'plaintext',
        code: match[2].trim(),
      });
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < content.length) {
      parts.push({ type: 'text', content: content.slice(lastIndex) });
    }

    return parts.length > 0 ? parts : [{ type: 'text', content }];
  };

  if (message.role === 'user') {
    return (
      <div className="flex justify-end my-4 select-text">
        <div className="max-w-[75%] rounded-2xl px-4 py-3 bg-[#1d1f27] border border-[#2b2d39] text-sm text-zinc-100 shadow-md space-y-1">
          <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>
          <div className="flex items-center justify-end space-x-2 pt-1 text-zinc-500">
            <button
              onClick={() => handleCopy(message.content)}
              className="hover:text-zinc-300 transition-colors"
              title="Copy text"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const parts = parseCodeBlocks(message.content);

  // Extra safety: Deduplicate actions so identical title/target is never shown twice
  const deduplicatedActions = React.useMemo(() => {
    if (!message.actions) return [];
    const list: AgentAction[] = [];
    for (const act of message.actions) {
      const existingIdx = list.findIndex((a) => a.title === act.title);
      if (existingIdx >= 0) {
        list[existingIdx] = act; // Keep latest state
      } else {
        list.push(act);
      }
    }
    return list;
  }, [message.actions]);

  const hasVerificationAction = deduplicatedActions.some((a) => a.type === 'verification');

  return (
    <div className="flex flex-col space-y-3 my-4 max-w-[90%] select-text">
      {/* Model / Agent Header */}
      <div className="flex items-center space-x-2 text-xs">
        <span className="w-4 h-4 rounded-md bg-gradient-to-tr from-purple-600 to-violet-400 flex items-center justify-center text-white text-[10px] font-bold shadow-sm">
          ✦
        </span>
        <span className="font-semibold text-zinc-200">ASTRA Autonomous Agent</span>
      </div>

      {/* Cline-Style Execution Steps (Tool Calls, Shell Commands, Verifications) */}
      {deduplicatedActions.length > 0 && (
        <div className="space-y-1">
          {deduplicatedActions.map((act) => (
            <ActionStepCard key={act.id} action={act} />
          ))}
        </div>
      )}

      {/* Message Body & Code Blocks */}
      {message.content && (
        <div className="space-y-3 bg-[#15161c] border border-[#242631] p-4 rounded-2xl">
          {parts.map((p, i) => {
            if (p.type === 'code') {
              return (
                <div key={i} className="rounded-xl bg-[#101116] border border-[#282a35] overflow-hidden my-2 shadow-lg">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-[#181920] border-b border-[#282a35] text-xs">
                    <span className="font-mono text-zinc-400 font-medium text-[11px]">{p.language}</span>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleCopy(p.code || '')}
                        className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                        title="Copy code"
                      >
                        {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                  <pre className="p-3.5 font-mono text-xs text-zinc-300 overflow-x-auto leading-relaxed whitespace-pre">
                    <code>{p.code}</code>
                  </pre>
                </div>
              );
            }
            return (
              <ReactMarkdown
                key={i}
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => <h1 className="text-base font-bold text-zinc-100 mt-3 mb-1 border-b border-zinc-700 pb-1">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-sm font-semibold text-zinc-100 mt-3 mb-1">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-sm font-medium text-violet-300 mt-2 mb-0.5">{children}</h3>,
                  p: ({ children }) => <p className="text-sm text-zinc-300 leading-relaxed mb-2">{children}</p>,
                  strong: ({ children }) => <strong className="font-semibold text-zinc-100">{children}</strong>,
                  em: ({ children }) => <em className="italic text-zinc-400">{children}</em>,
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer"
                      className="text-violet-400 underline underline-offset-2 hover:text-violet-300 transition-colors">
                      {children}
                    </a>
                  ),
                  ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 my-1 text-sm text-zinc-300 pl-2">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside space-y-0.5 my-1 text-sm text-zinc-300 pl-2">{children}</ol>,
                  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-violet-500 pl-3 my-2 text-zinc-400 italic text-sm">{children}</blockquote>
                  ),
                  code: ({ inline, children }: any) =>
                    inline
                      ? <code className="bg-zinc-800 text-violet-300 rounded px-1 py-0.5 font-mono text-xs">{children}</code>
                      : <pre className="bg-[#101116] border border-[#282a35] rounded-lg p-3 overflow-x-auto my-2"><code className="font-mono text-xs text-zinc-300">{children}</code></pre>,
                  hr: () => <hr className="border-zinc-700 my-3" />,
                  table: ({ children }) => <table className="text-xs text-zinc-300 border-collapse w-full my-2">{children}</table>,
                  th: ({ children }) => <th className="border border-zinc-700 px-2 py-1 text-zinc-100 bg-zinc-800 font-semibold">{children}</th>,
                  td: ({ children }) => <td className="border border-zinc-700 px-2 py-1">{children}</td>,
                }}
              >
                {p.content}
              </ReactMarkdown>
            );

          })}
        </div>
      )}

      {/* Verification Outcome Card if Present and not already rendered in action steps */}
      {message.verification && !hasVerificationAction && (
        <div
          className={`rounded-xl p-3.5 border text-xs ${
            message.verification.passed
              ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-200'
              : 'bg-rose-950/30 border-rose-700/50 text-rose-200'
          }`}
        >
          <div className="flex items-center space-x-2 font-semibold mb-1">
            {message.verification.passed ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <XCircle className="w-4 h-4 text-rose-400" />
            )}
            <span>{message.verification.passed ? 'Independent Verification: PASSED' : 'Verification FAILED'}</span>
          </div>
          <p className="text-[11px] text-zinc-300">{message.verification.summary}</p>
          {message.verification.details && (
            <div className="mt-2 p-2 rounded bg-black/40 font-mono text-[10px] text-zinc-400 overflow-x-auto whitespace-pre-wrap">
              {message.verification.details}
            </div>
          )}
        </div>
      )}

      {/* Collapsible Reasoning & Sources Toolbar */}
      <div className="flex flex-wrap items-center gap-2 pt-1 select-none">
        {message.thought && (
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            className="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-[#1e202a] hover:bg-[#252834] border border-[#2f3240] text-violet-300 font-medium text-xs transition-colors"
          >
            <Brain className="w-3.5 h-3.5 text-violet-400" />
            <span>Reasoning</span>
          </button>
        )}

        {sourcesCount > 0 && onOpenSourcesDrawer && (
          <button
            onClick={onOpenSourcesDrawer}
            className="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-[#1e202a] hover:bg-[#252834] border border-[#2f3240] text-cyan-300 font-medium text-xs transition-colors"
          >
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span>{sourcesCount} Tool Calls</span>
          </button>
        )}

        <div className="flex items-center space-x-1 pl-2 text-zinc-500">
          <button className="p-1 hover:text-zinc-300 transition-colors" title="Good response">
            <ThumbsUp className="w-3 h-3" />
          </button>
          <button className="p-1 hover:text-zinc-300 transition-colors" title="Bad response">
            <ThumbsDown className="w-3 h-3" />
          </button>
          <button
            onClick={() => handleCopy(message.content)}
            className="p-1 hover:text-zinc-300 transition-colors"
            title="Copy message"
          >
            <Copy className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Expanded Reasoning Content */}
      {showReasoning && message.thought && (
        <div className="rounded-xl bg-[#14151b] border border-purple-500/30 p-3.5 text-xs text-zinc-300 font-mono space-y-1.5 shadow-inner">
          <div className="flex items-center space-x-1 text-purple-400 font-semibold text-[11px]">
            <Brain className="w-3.5 h-3.5" />
            <span>Internal Execution Logic</span>
          </div>
          <div className="whitespace-pre-wrap leading-relaxed text-[11px] text-zinc-400">
            {message.thought}
          </div>
        </div>
      )}
    </div>
  );
};
