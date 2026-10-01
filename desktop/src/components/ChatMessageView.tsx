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
  Search,
  ExternalLink,
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

  const isCommand = action.type === 'command' || action.title.startsWith('$');
  const isFile = action.type === 'file' || /^(create|write|edit|delete|modify)/i.test(action.title);
  const isVerify = action.type === 'verification' || /verif/i.test(action.title);
  const isSearch = action.type === 'tool' && /search/i.test(action.title);

  return (
    <div className="rounded-xl bg-[#0f1017] border border-[#212332] hover:border-[#2f3248] overflow-hidden my-1 shadow-sm text-xs transition-all">
      <div
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-3.5 py-2.5 bg-[#141520] hover:bg-[#191b29] cursor-pointer transition-colors"
      >
        <div className="flex items-center space-x-2.5 truncate max-w-[82%]">
          {/* Badge */}
          {isCommand && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-700/50 text-cyan-300 font-mono text-[10px] font-semibold shrink-0">
              <Terminal className="w-3 h-3 shrink-0" />
              <span>CMD</span>
            </span>
          )}
          {isFile && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-700/50 text-emerald-300 font-mono text-[10px] font-semibold shrink-0">
              <FileCode className="w-3 h-3 shrink-0" />
              <span>FILE</span>
            </span>
          )}
          {isVerify && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-950/80 border border-purple-700/50 text-purple-300 font-mono text-[10px] font-semibold shrink-0">
              <Shield className="w-3 h-3 shrink-0" />
              <span>VERIFY</span>
            </span>
          )}
          {isSearch && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-700/50 text-amber-300 font-mono text-[10px] font-semibold shrink-0">
              <Search className="w-3 h-3 shrink-0" />
              <span>SEARCH</span>
            </span>
          )}
          {!isCommand && !isFile && !isVerify && !isSearch && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/50 text-zinc-300 font-mono text-[10px] font-semibold shrink-0">
              <Wrench className="w-3 h-3 shrink-0" />
              <span>TOOL</span>
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
            {action.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping" />}
            {action.status === 'completed' && <Check className="w-2.5 h-2.5" />}
            {action.status === 'failed' && <XCircle className="w-2.5 h-2.5" />}
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
        <div className="relative bg-[#0a0b10] border-t border-[#1d1f2c]">
          <div className="flex items-center justify-between px-3 py-1 bg-[#10111a] border-b border-[#1d1f2c] text-[10px] text-zinc-500">
            <span className="font-mono">Output</span>
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
  const [showThinking, setShowThinking] = useState(false);
  const [actionsExpanded, setActionsExpanded] = useState(true);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // User prompt
  if (message.role === 'user') {
    return (
      <div className="flex justify-end my-4 select-text">
        <div className="max-w-[78%] rounded-2xl px-4 py-3 bg-[#1d1f2b] border border-[#2d3042] text-sm text-zinc-100 shadow-md space-y-1">
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

  // Deduplicate and sanitize actions so zero duplicates appear
  const deduplicatedActions = React.useMemo(() => {
    if (!message.actions) return [];
    const list: AgentAction[] = [];

    for (const act of message.actions) {
      // 1. Never show thought/planning as a tool card (it lives in Thinking Process)
      if (act.type === 'thought') continue;

      // 2. Normalize title for stable comparison
      const rawTitle = (act.title || '').trim();
      const normKey = rawTitle
        .toLowerCase()
        .replace(/\\/g, '/')
        .replace(/^(create|created:|modify|modified:|edit|write|read|delete)\s+/, '')
        .trim();

      const existingIdx = list.findIndex((a) => {
        // Only keep 1 verification card
        if (a.type === 'verification' && act.type === 'verification') return true;
        
        const aNorm = (a.title || '')
          .toLowerCase()
          .replace(/\\/g, '/')
          .replace(/^(create|created:|modify|modified:|edit|write|read|delete)\s+/, '')
          .trim();
        return aNorm === normKey;
      });

      if (existingIdx >= 0) {
        list[existingIdx] = {
          ...list[existingIdx],
          ...act,
          output: act.output || list[existingIdx].output,
          status: act.status || list[existingIdx].status,
        };
      } else {
        list.push(act);
      }
    }
    return list;
  }, [message.actions]);

  const hasVerificationInActions = deduplicatedActions.some((a) => a.type === 'verification' || /verif/i.test(a.title));

  return (
    <div className="flex flex-col space-y-3 my-4 max-w-[92%] select-text">
      {/* Cline-Style Agent Header */}
      <div className="flex items-center justify-between text-xs pb-0.5">
        <div className="flex items-center space-x-2">
          <span className="w-5 h-5 rounded-lg bg-gradient-to-tr from-purple-600 via-indigo-500 to-cyan-400 flex items-center justify-center text-white text-[11px] font-bold shadow-md shadow-purple-950/40">
            ✦
          </span>
          <span className="font-semibold text-zinc-100 tracking-wide text-xs">ASTRA</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-950/60 border border-purple-800/40 text-purple-300 font-medium">
            AUTONOMOUS
          </span>
        </div>
      </div>

      {/* DeepSeek / Cline Style Collapsible Thinking Process */}
      {message.thought && (
        <div className="rounded-xl bg-[#0f1018] border border-purple-900/30 overflow-hidden text-xs">
          <button
            onClick={() => setShowThinking(!showThinking)}
            className="w-full flex items-center justify-between px-3.5 py-2 bg-[#131422] hover:bg-[#18192a] text-purple-300 font-mono text-[11px] transition-colors"
          >
            <div className="flex items-center space-x-2">
              <Brain className="w-3.5 h-3.5 text-purple-400" />
              <span className="font-semibold">Thinking Process</span>
              <span className="text-zinc-500 text-[10px]">({message.thought.split(/\s+/).length} words)</span>
            </div>
            {showThinking ? (
              <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
            )}
          </button>
          {showThinking && (
            <div className="p-3.5 font-mono text-[11px] text-zinc-400 leading-relaxed whitespace-pre-wrap border-t border-purple-950/40 bg-[#0c0d14]">
              {message.thought}
            </div>
          )}
        </div>
      )}

      {/* Cline-Style Execution Sequence (Unified Card Group) */}
      {deduplicatedActions.length > 0 && (
        <div className="space-y-1">
          <div className="flex items-center justify-between px-1 text-[11px] text-zinc-400 font-mono">
            <span className="flex items-center gap-1.5 font-medium">
              <Activity className="w-3.5 h-3.5 text-cyan-400" />
              <span>Execution Steps ({deduplicatedActions.length})</span>
            </span>
            <button
              onClick={() => setActionsExpanded(!actionsExpanded)}
              className="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              {actionsExpanded ? 'Collapse' : 'Expand'}
            </button>
          </div>
          {actionsExpanded && (
            <div className="space-y-1 pt-0.5">
              {deduplicatedActions.map((act) => (
                <ActionStepCard key={act.id} action={act} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Standalone Verification Card ONLY if not already shown in actions */}
      {message.verification && !hasVerificationInActions && (
        <div
          className={`rounded-xl p-3 border text-xs ${
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

      {/* Message Body & Code Blocks with ReactMarkdown */}
      {message.content && (
        <div className="space-y-2 bg-[#12131b] border border-[#212330] p-4 rounded-2xl shadow-sm">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ children }) => <h1 className="text-base font-bold text-zinc-100 mt-3 mb-1.5 border-b border-zinc-800 pb-1">{children}</h1>,
              h2: ({ children }) => <h2 className="text-sm font-semibold text-zinc-100 mt-2.5 mb-1">{children}</h2>,
              h3: ({ children }) => <h3 className="text-sm font-medium text-violet-300 mt-2 mb-0.5">{children}</h3>,
              p: ({ children }) => <p className="text-sm text-zinc-300 leading-relaxed mb-2">{children}</p>,
              strong: ({ children }) => <strong className="font-semibold text-zinc-100">{children}</strong>,
              em: ({ children }) => <em className="italic text-zinc-400">{children}</em>,
              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-violet-400 underline underline-offset-2 hover:text-violet-300 transition-colors inline-flex items-center gap-0.5"
                >
                  <span>{children}</span>
                  <ExternalLink className="w-2.5 h-2.5 inline" />
                </a>
              ),
              ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-1.5 text-sm text-zinc-300 pl-1">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-1.5 text-sm text-zinc-300 pl-1">{children}</ol>,
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              blockquote: ({ children }) => (
                <blockquote className="border-l-2 border-violet-500 pl-3 my-2 text-zinc-400 italic text-sm">{children}</blockquote>
              ),
              code: ({ inline, children }: any) =>
                inline ? (
                  <code className="bg-zinc-800/90 text-violet-300 rounded px-1 py-0.5 font-mono text-xs border border-zinc-700/40">
                    {children}
                  </code>
                ) : (
                  <div className="rounded-xl bg-[#0a0b10] border border-[#212330] overflow-hidden my-2 shadow-md">
                    <pre className="p-3.5 overflow-x-auto">
                      <code className="font-mono text-xs text-zinc-200 leading-relaxed">{children}</code>
                    </pre>
                  </div>
                ),
              hr: () => <hr className="border-zinc-800 my-3" />,
              table: ({ children }) => <table className="text-xs text-zinc-300 border-collapse w-full my-2">{children}</table>,
              th: ({ children }) => <th className="border border-zinc-700/80 px-2 py-1 text-zinc-100 bg-zinc-800/90 font-semibold text-left">{children}</th>,
              td: ({ children }) => <td className="border border-zinc-700/60 px-2 py-1">{children}</td>,
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      )}

      {/* Bottom Action Bar */}
      <div className="flex items-center justify-between pt-0.5 text-zinc-500 text-xs">
        <div className="flex items-center space-x-2">
          {sourcesCount > 0 && onOpenSourcesDrawer && (
            <button
              onClick={onOpenSourcesDrawer}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-[#181924] hover:bg-[#202230] border border-[#2b2d3d] text-cyan-300 font-medium text-[11px] transition-colors"
            >
              <Layers className="w-3 h-3 text-cyan-400" />
              <span>{sourcesCount} Tool Calls</span>
            </button>
          )}
        </div>

        <div className="flex items-center space-x-1">
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
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>
      </div>
    </div>
  );
};
