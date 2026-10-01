import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  Copy,
  Check,
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
  ThumbsUp,
  ThumbsDown,
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
    <div className="rounded-lg bg-white border border-slate-200 hover:border-slate-300 overflow-hidden my-1 shadow-xs text-xs transition-all">
      <div
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-3 py-2 bg-slate-50/80 hover:bg-slate-100/80 cursor-pointer transition-colors"
      >
        <div className="flex items-center space-x-2 truncate max-w-[82%]">
          {/* Badge */}
          {isCommand && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-700 font-mono text-[10px] font-semibold shrink-0">
              <Terminal className="w-3 h-3 shrink-0 text-slate-600" />
              <span>CMD</span>
            </span>
          )}
          {isFile && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-700 font-mono text-[10px] font-semibold shrink-0">
              <FileCode className="w-3 h-3 shrink-0 text-blue-600" />
              <span>FILE</span>
            </span>
          )}
          {isVerify && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 font-mono text-[10px] font-semibold shrink-0">
              <Shield className="w-3 h-3 shrink-0 text-emerald-600" />
              <span>VERIFY</span>
            </span>
          )}
          {isSearch && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-700 font-mono text-[10px] font-semibold shrink-0">
              <Search className="w-3 h-3 shrink-0 text-amber-600" />
              <span>SEARCH</span>
            </span>
          )}
          {!isCommand && !isFile && !isVerify && !isSearch && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-700 font-mono text-[10px] font-semibold shrink-0">
              <Wrench className="w-3 h-3 shrink-0 text-slate-500" />
              <span>TOOL</span>
            </span>
          )}

          <span className="font-mono font-medium text-slate-800 truncate text-[12px]">{action.title}</span>
          {action.detail && (
            <span className="text-slate-400 font-mono text-[11px] truncate">{action.detail}</span>
          )}
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1 ${
              action.status === 'running'
                ? 'bg-blue-50 text-blue-700 border border-blue-200 animate-pulse'
                : action.status === 'completed'
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-rose-50 text-rose-700 border border-rose-200'
            }`}
          >
            {action.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping" />}
            {action.status === 'completed' && <Check className="w-2.5 h-2.5" />}
            {action.status === 'failed' && <XCircle className="w-2.5 h-2.5" />}
            <span>{action.status}</span>
          </span>
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
          )}
        </div>
      </div>

      {expanded && action.output && (
        <div className="relative bg-slate-900 border-t border-slate-200">
          <div className="flex items-center justify-between px-3 py-1 bg-slate-950 border-b border-slate-800 text-[10px] text-slate-400">
            <span className="font-mono">Output</span>
            <button
              onClick={handleCopyOutput}
              className="hover:text-slate-200 flex items-center gap-1 transition-colors"
              title="Copy output"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <pre className="p-3 font-mono text-[11px] text-slate-200 overflow-x-auto max-h-64 leading-relaxed whitespace-pre-wrap select-text">
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
  const [userExpandedOverride, setUserExpandedOverride] = useState<boolean | null>(null);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // User prompt: Antigravity clean light bubble
  if (message.role === 'user') {
    return (
      <div className="flex justify-end my-4 select-text">
        <div className="max-w-[78%] rounded-2xl px-4 py-3 bg-slate-100 border border-slate-200 text-sm text-slate-900 shadow-xs space-y-1">
          <div className="whitespace-pre-wrap leading-relaxed font-normal">{message.content}</div>
          <div className="flex items-center justify-end space-x-2 pt-1 text-slate-400">
            <button
              onClick={() => handleCopy(message.content)}
              className="hover:text-slate-700 transition-colors"
              title="Copy text"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Deduplicate and sanitize actions
  const deduplicatedActions = React.useMemo(() => {
    if (!message.actions) return [];
    const list: AgentAction[] = [];

    for (const act of message.actions) {
      if (act.type === 'thought') continue;

      const rawTitle = (act.title || '').trim();
      const normKey = rawTitle
        .toLowerCase()
        .replace(/\\/g, '/')
        .replace(/^(create|created:|modify|modified:|edit|write|read|delete)\s+/, '')
        .trim();

      const existingIdx = list.findIndex((a) => {
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

  // Antigravity auto-collapse logic:
  // If any action is still running, keep open. Once completed, auto-collapse steps so UI stays clean!
  const isStillRunning = deduplicatedActions.some((a) => a.status === 'running');
  const actionsExpanded = userExpandedOverride !== null ? userExpandedOverride : isStillRunning;

  const hasVerificationInActions = deduplicatedActions.some(
    (a) => a.type === 'verification' || /verif/i.test(a.title)
  );

  return (
    <div className="flex flex-col space-y-3 my-4 max-w-[94%] select-text">
      {/* Antigravity Agent Header */}
      <div className="flex items-center justify-between text-xs pb-0.5">
        <div className="flex items-center space-x-2">
          <span className="w-5 h-5 rounded-md bg-slate-900 flex items-center justify-center text-white text-[10px] font-bold shadow-xs">
            <Sparkles className="w-3 h-3 text-white" />
          </span>
          <span className="font-semibold text-slate-900 tracking-tight text-xs">ASTRA</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 border border-slate-200 text-slate-600 font-medium">
            AUTONOMOUS
          </span>
        </div>
      </div>

      {/* Thinking Process Accordion */}
      {message.thought && (
        <div className="rounded-xl bg-slate-50 border border-slate-200 overflow-hidden text-xs">
          <button
            onClick={() => setShowThinking(!showThinking)}
            className="w-full flex items-center justify-between px-3.5 py-2 bg-slate-50 hover:bg-slate-100 text-slate-700 font-mono text-[11px] transition-colors"
          >
            <div className="flex items-center space-x-2">
              <Brain className="w-3.5 h-3.5 text-slate-500" />
              <span className="font-medium">Thinking Process</span>
              <span className="text-slate-400 text-[10px]">({message.thought.split(/\s+/).length} words)</span>
            </div>
            {showThinking ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            )}
          </button>
          {showThinking && (
            <div className="p-3.5 font-mono text-[11px] text-slate-600 leading-relaxed whitespace-pre-wrap border-t border-slate-200 bg-white">
              {message.thought}
            </div>
          )}
        </div>
      )}

      {/* Auto-Collapsing Execution Steps Group */}
      {deduplicatedActions.length > 0 && (
        <div className="rounded-xl bg-slate-50/60 border border-slate-200 p-2 space-y-1.5">
          <div
            onClick={() => setUserExpandedOverride(!actionsExpanded)}
            className="flex items-center justify-between px-1.5 py-0.5 cursor-pointer text-[11px] text-slate-600 font-mono hover:text-slate-900 select-none"
          >
            <span className="flex items-center gap-1.5 font-medium">
              <Activity className="w-3.5 h-3.5 text-blue-600" />
              <span>
                {isStillRunning ? 'Executing Steps' : 'Completed Execution'} ({deduplicatedActions.length})
              </span>
              {!actionsExpanded && (
                <span className="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded font-sans">
                  ✓ All steps verified
                </span>
              )}
            </span>
            <span className="text-[10px] text-slate-400 hover:text-slate-700 flex items-center gap-1 transition-colors">
              {actionsExpanded ? 'Collapse steps' : 'View all steps'}
              {actionsExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </span>
          </div>

          {actionsExpanded && (
            <div className="space-y-1 pt-1 border-t border-slate-200">
              {deduplicatedActions.map((act) => (
                <ActionStepCard key={act.id} action={act} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Standalone Verification Card (if not in actions) */}
      {message.verification && !hasVerificationInActions && (
        <div
          className={`rounded-xl p-3 border text-xs ${
            message.verification.passed
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <div className="flex items-center space-x-2 font-semibold mb-1">
            {message.verification.passed ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            ) : (
              <XCircle className="w-4 h-4 text-rose-600" />
            )}
            <span>{message.verification.passed ? 'Independent Verification: PASSED' : 'Verification FAILED'}</span>
          </div>
          <p className="text-[11px] text-slate-600">{message.verification.summary}</p>
          {message.verification.details && (
            <div className="mt-2 p-2 rounded bg-slate-900 font-mono text-[10px] text-slate-200 overflow-x-auto whitespace-pre-wrap">
              {message.verification.details}
            </div>
          )}
        </div>
      )}

      {/* Antigravity Final Summary & Message Body */}
      {message.content && (
        <div className="space-y-2 bg-white border border-slate-200 p-5 rounded-2xl shadow-xs text-slate-800">
          {!isStillRunning && deduplicatedActions.length > 0 && (
            <div className="flex items-center gap-1.5 pb-2 mb-2 border-b border-slate-100 text-xs font-semibold text-slate-900">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Final Task Summary</span>
            </div>
          )}

          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ children }) => (
                <h1 className="text-base font-bold text-slate-900 mt-3 mb-1.5 border-b border-slate-200 pb-1">
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-sm font-semibold text-slate-900 mt-2.5 mb-1">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-sm font-medium text-slate-800 mt-2 mb-0.5">{children}</h3>
              ),
              p: ({ children }) => (
                <p className="text-sm text-slate-700 leading-relaxed mb-2.5 font-normal">{children}</p>
              ),
              strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
              em: ({ children }) => <em className="italic text-slate-600">{children}</em>,
              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 underline underline-offset-2 hover:text-blue-700 transition-colors inline-flex items-center gap-0.5"
                >
                  <span>{children}</span>
                  <ExternalLink className="w-2.5 h-2.5 inline" />
                </a>
              ),
              ul: ({ children }) => (
                <ul className="list-disc list-inside space-y-1 my-1.5 text-sm text-slate-700 pl-1">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-inside space-y-1 my-1.5 text-sm text-slate-700 pl-1">{children}</ol>
              ),
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              pre: ({ children }: any) => <>{children}</>,
              code: ({ className, children, ...props }: any) => {
                const match = /language-(\w+)/.exec(className || '');
                const rawString = String(children);
                const isMultiline = rawString.includes('\n');

                // Inline code chip (e.g. `git_status`, `desktop`)
                if (!match && !isMultiline) {
                  return (
                    <code
                      className="bg-slate-100 text-slate-800 rounded px-1.5 py-0.5 font-mono text-[11.5px] font-medium border border-slate-200 inline align-baseline mx-0.5"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                }

                // Fenced multi-line code block
                const language = match ? match[1] : '';
                return (
                  <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden my-3 shadow-xs">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-slate-950 border-b border-slate-800/80 text-[11px] font-mono text-slate-400">
                      <span>{language || 'code'}</span>
                      <button
                        type="button"
                        onClick={() => navigator.clipboard.writeText(rawString)}
                        className="hover:text-slate-200 text-[10px] flex items-center gap-1 transition-colors"
                      >
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </button>
                    </div>
                    <pre className="p-3.5 overflow-x-auto">
                      <code className="font-mono text-xs text-slate-200 leading-relaxed" {...props}>
                        {children}
                      </code>
                    </pre>
                  </div>
                );
              },
              hr: () => <hr className="border-slate-200 my-3" />,
              table: ({ children }) => (
                <table className="text-xs text-slate-700 border-collapse w-full my-2">{children}</table>
              ),
              th: ({ children }) => (
                <th className="border border-slate-200 px-2 py-1 text-slate-900 bg-slate-50 font-semibold text-left">
                  {children}
                </th>
              ),
              td: ({ children }) => <td className="border border-slate-200 px-2 py-1">{children}</td>,
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      )}

      {/* Bottom Action Bar */}
      <div className="flex items-center justify-between pt-0.5 text-slate-400 text-xs">
        <div className="flex items-center space-x-2">
          {sourcesCount > 0 && onOpenSourcesDrawer && (
            <button
              onClick={onOpenSourcesDrawer}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 font-medium text-[11px] transition-colors"
            >
              <Layers className="w-3 h-3 text-slate-600" />
              <span>{sourcesCount} Tool Calls</span>
            </button>
          )}
        </div>

        <div className="flex items-center space-x-1">
          <button className="p-1 hover:text-slate-700 transition-colors" title="Good response">
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button className="p-1 hover:text-slate-700 transition-colors" title="Bad response">
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleCopy(message.content)}
            className="p-1 hover:text-slate-700 transition-colors"
            title="Copy message"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
    </div>
  );
};
