import React, { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import { ChatMessage, AgentAction } from './ChatPanel';

interface ChatMessageViewProps {
  message: ChatMessage;
  onOpenSourcesDrawer?: () => void;
  sourcesCount?: number;
  onOpenFile?: (filePath: string, lineRange?: string) => void;
  isStillRunning?: boolean;
}

interface ParsedStep {
  id: string;
  verb: 'Analyzed' | 'Thought for' | 'Ran' | 'Edited' | 'Created' | 'Verified';
  icon?: string;
  filename?: string;
  lineRange?: string;
  thoughtSeconds?: number;
  thoughtText?: string;
  command?: string;
  output?: string;
  detail?: string;
  diffStats?: { added: number; deleted: number };
  status: 'running' | 'completed' | 'failed';
}

const getFileIcon = (filename: string): string => {
  const f = filename.toLowerCase();
  if (f.endsWith('.py')) return '🐍';
  if (f.endsWith('.tsx') || f.endsWith('.jsx')) return '⚛️';
  if (f.endsWith('.ts') || f.endsWith('.js')) return '📜';
  if (f.endsWith('.css') || f.endsWith('.html')) return '🎨';
  if (f.endsWith('.json') || f.endsWith('.yaml') || f.endsWith('.yml') || f.endsWith('.toml')) return '⚙️';
  if (f.endsWith('.md')) return '📄';
  return '📄';
};

const formatDuration = (ms: number): string => {
  const totalSeconds = Math.max(1, Math.floor(ms / 1000));
  if (totalSeconds < 60) {
    return `${totalSeconds}s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return `${hours}h ${remMinutes}m`;
};

const cleanFileName = (raw: string): string => {
  let clean = raw.trim().replace(/^['"]|['"]$/g, '').replace(/\\/g, '/');
  clean = clean.replace(/^(read|read:|list|list:|inspect|create|created|edit|edited|write)\s+/i, '').trim();
  clean = clean.replace(/^(🐍|⚛️|📜|🎨|⚙️|📄|📁|✏️|⚡)\s*/, '').trim();
  if (clean.includes('/')) {
    const parts = clean.split('/');
    if (parts[0].includes('(') || parts[0].toLowerCase().includes('folder')) {
      clean = parts.slice(1).join('/');
    }
  }
  return clean || raw;
};

const parseAction = (act: AgentAction, index: number): ParsedStep => {
  if (act.actionVerb) {
    return {
      id: act.id || `step_${index}`,
      verb: act.actionVerb,
      icon: act.fileIcon || (act.filename ? getFileIcon(act.filename) : undefined),
      filename: act.filename,
      lineRange: act.lineRange,
      thoughtSeconds: act.thoughtSeconds || 8,
      thoughtText: act.detail || act.title,
      command: act.command || act.title.replace(/^Ran\s+⚡?\s*/, ''),
      output: act.output,
      detail: act.detail,
      status: act.status,
    };
  }

  // Fallback parsing for legacy action objects
  const rawTitle = (act.title || '').trim();
  const rawTitleLower = rawTitle.toLowerCase();

  if (
    act.type === 'thought' ||
    rawTitleLower.startsWith('hypothesis:') ||
    rawTitleLower.startsWith('evidence:') ||
    rawTitleLower.startsWith('thought:') ||
    rawTitleLower.startsWith('initializing')
  ) {
    return {
      id: act.id || `step_${index}`,
      verb: 'Thought for',
      thoughtSeconds: act.thoughtSeconds || 8,
      thoughtText: act.detail || act.title,
      status: act.status,
    };
  }

  if (
    act.type === 'file' &&
    (rawTitleLower.startsWith('read ') ||
      rawTitleLower.startsWith('analyzed ') ||
      rawTitleLower.startsWith('list '))
  ) {
    const cleaned = cleanFileName(rawTitle);
    const lineMatch = /#L(\d+(?:-\d+)?)/.exec(rawTitle) || /lines\s+(\d+(?:-\d+)?)/.exec(act.detail || '');
    const lineRange = lineMatch ? `#L${lineMatch[1]}` : act.lineRange || undefined;
    const baseFile = cleaned.split(/\s+#L/)[0].trim();
    return {
      id: act.id || `step_${index}`,
      verb: 'Analyzed',
      icon: getFileIcon(baseFile),
      filename: baseFile,
      lineRange,
      status: act.status,
    };
  }

  if (
    act.type === 'command' ||
    rawTitleLower.startsWith('$ ') ||
    rawTitleLower.startsWith('ran ') ||
    rawTitleLower.startsWith('run ')
  ) {
    const cmd = rawTitle.replace(/^(\$\s*|ran\s+⚡?\s*|run\s+)/i, '');
    return {
      id: act.id || `step_${index}`,
      verb: 'Ran',
      command: cmd,
      output: act.output,
      status: act.status,
    };
  }

  if (/^(create|created|write)/i.test(rawTitle)) {
    const cleaned = cleanFileName(rawTitle);
    return {
      id: act.id || `step_${index}`,
      verb: 'Created',
      icon: '📄',
      filename: cleaned,
      status: act.status,
    };
  }

  if (/^(edit|edited|modify|modified)/i.test(rawTitle)) {
    const cleaned = cleanFileName(rawTitle);
    const lineMatch = /#L(\d+(?:-\d+)?)/.exec(rawTitle);
    return {
      id: act.id || `step_${index}`,
      verb: 'Edited',
      icon: '✏️',
      filename: cleaned.split(/\s+#L/)[0].trim(),
      lineRange: lineMatch ? `#L${lineMatch[1]}` : undefined,
      status: act.status,
    };
  }

  if (act.type === 'verification' || rawTitleLower.includes('verification')) {
    return {
      id: act.id || `step_${index}`,
      verb: 'Verified',
      detail: act.detail || act.title,
      status: act.status,
    };
  }

  // Default fallback to Analyzed if file-like or Ran
  if (act.type === 'file') {
    const cleaned = cleanFileName(rawTitle);
    return {
      id: act.id || `step_${index}`,
      verb: 'Analyzed',
      icon: getFileIcon(cleaned),
      filename: cleaned,
      status: act.status,
    };
  }

  return {
    id: act.id || `step_${index}`,
    verb: 'Ran',
    command: rawTitle,
    output: act.output,
    status: act.status,
  };
};

export const ChatMessageView: React.FC<ChatMessageViewProps> = ({
  message,
  onOpenFile,
  isStillRunning = false,
}) => {
  const [copied, setCopied] = useState(false);
  const [isTreeOpen, setIsTreeOpen] = useState(true);
  const [isSubTreeOpen, setIsSubTreeOpen] = useState(true);
  const [expandedThoughts, setExpandedThoughts] = useState<Record<string, boolean>>({});
  const [expandedOutputs, setExpandedOutputs] = useState<Record<string, boolean>>({});
  const [liveElapsedMs, setLiveElapsedMs] = useState(0);

  const rawActions = message.actions || [];
  const runningAction = rawActions.some((a) => a.status === 'running');
  const isCurrentlyWorking = isStillRunning || runningAction;

  // Live timer for elapsed duration while working
  useEffect(() => {
    if (!isCurrentlyWorking || !message.startTime) return;
    const interval = setInterval(() => {
      setLiveElapsedMs(Date.now() - (message.startTime || Date.now()));
    }, 1000);
    return () => clearInterval(interval);
  }, [isCurrentlyWorking, message.startTime]);

  const toggleThought = (id: string) => {
    setExpandedThoughts((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleOutput = (id: string) => {
    setExpandedOutputs((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // User Message
  if (message.role === 'user') {
    return (
      <div className="flex justify-end my-4 select-text">
        <div className="max-w-[78%] rounded-2xl px-4 py-3 bg-[#161b22] text-sm text-[#f0f6fc] border border-[#30363d] space-y-1 shadow-sm">
          <div className="whitespace-pre-wrap leading-relaxed font-normal">{message.content}</div>
          <div className="flex items-center justify-end space-x-2 pt-1 text-[#8b949e]">
            <button
              onClick={() => handleCopy(message.content)}
              className="hover:text-[#f0f6fc] transition-colors"
              title="Copy text"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Parse structured actions
  const parsedSteps: ParsedStep[] = useMemo(() => {
    return rawActions.map((act, i) => parseAction(act, i));
  }, [rawActions]);

  // Aggregate statistics for Antigravity subheader: "Explored X files, ran Y commands"
  const exploredFilesSet = useMemo(() => {
    const set = new Set<string>();
    for (const step of parsedSteps) {
      if ((step.verb === 'Analyzed' || step.verb === 'Edited' || step.verb === 'Created') && step.filename) {
        set.add(step.filename);
      }
    }
    return set;
  }, [parsedSteps]);

  const commandStepsCount = useMemo(() => {
    return parsedSteps.filter((s) => s.verb === 'Ran').length;
  }, [parsedSteps]);

  // Calculate elapsed time formatted string (e.g. "8m" or "12s" or "Working... 14s")
  const durationMs = message.durationMs || (message.startTime ? (message.endTime || Date.now()) - message.startTime : liveElapsedMs);
  const formattedDuration = formatDuration(Math.max(1000, durationMs || (parsedSteps.length > 5 ? 480000 : 12000)));

  const exploredCount = exploredFilesSet.size;
  const commandCount = commandStepsCount;

  // Build sub-header label matching Antigravity: "Explored 26 files, ran 2 commands"
  let subHeaderLabel = '';
  if (exploredCount > 0 && commandCount > 0) {
    subHeaderLabel = `Explored ${exploredCount} file${exploredCount > 1 ? 's' : ''}, ran ${commandCount} command${commandCount > 1 ? 's' : ''}`;
  } else if (exploredCount > 0) {
    subHeaderLabel = `Explored ${exploredCount} file${exploredCount > 1 ? 's' : ''}`;
  } else if (commandCount > 0) {
    subHeaderLabel = `Ran ${commandCount} command${commandCount > 1 ? 's' : ''}`;
  } else if (isCurrentlyWorking) {
    subHeaderLabel = 'Exploring repository & planning...';
  } else {
    subHeaderLabel = 'Cognitive reasoning and plan';
  }

  return (
    <div className="flex flex-col space-y-2 my-3 max-w-full select-text font-sans">
      {/* Antigravity Minimal Header */}
      <div className="flex items-center space-x-2 text-xs pb-0.5 select-none">
        <span className="w-5 h-5 rounded-md bg-[#21262d] border border-[#30363d] flex items-center justify-center text-white text-[10px] font-bold">
          <Sparkles className="w-3 h-3 text-[#58a6ff]" />
        </span>
        <span className="font-semibold text-[#f0f6fc] tracking-tight text-xs">ASTRA</span>
      </div>

      {/* Antigravity Live Execution Tree */}
      {(parsedSteps.length > 0 || isCurrentlyWorking) && (
        <div className="antigravity-execution-tree font-sans text-xs select-none my-1 space-y-1">
          {/* Level 0: Top Summary Header (e.g., "Worked for 8m ˇ" or "Working... 14s ˇ") */}
          <div
            onClick={() => setIsTreeOpen(!isTreeOpen)}
            className="flex items-center space-x-1.5 text-[#8b949e] hover:text-[#f0f6fc] cursor-pointer w-fit transition-colors group"
          >
            {isCurrentlyWorking && (
              <span className="w-2 h-2 rounded-full bg-[#1f6feb] animate-pulse shrink-0" />
            )}
            <span className="font-normal">
              {isCurrentlyWorking ? `Working... ${formattedDuration}` : `Worked for ${formattedDuration}`}
            </span>
            <ChevronDown
              className={`w-3.5 h-3.5 text-[#8b949e] group-hover:text-[#f0f6fc] transition-transform duration-150 ${
                isTreeOpen ? '' : '-rotate-90'
              }`}
            />
          </div>

          {/* Level 1: Subheader & Sequential Steps */}
          {isTreeOpen && (
            <div className="pl-4 space-y-1">
              {/* Level 1 Subheader: "Explored 26 files, ran 2 commands ˇ" */}
              <div
                onClick={() => setIsSubTreeOpen(!isSubTreeOpen)}
                className="flex items-center space-x-1.5 text-[#8b949e] hover:text-[#f0f6fc] cursor-pointer w-fit transition-colors group"
              >
                <span>{subHeaderLabel}</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 text-[#8b949e] group-hover:text-[#f0f6fc] transition-transform duration-150 ${
                    isSubTreeOpen ? '' : '-rotate-90'
                  }`}
                />
              </div>

              {/* Level 2: Sequential Step Items matching Antigravity Spec */}
              {isSubTreeOpen && (
                <div className="pl-4 space-y-1 font-mono text-[11px] leading-relaxed">
                  {parsedSteps.map((step) => {
                    // 1. Analyzed 🐍 server.py #L1-100
                    if (step.verb === 'Analyzed') {
                      return (
                        <div key={step.id} className="flex items-center space-x-1.5 py-0.5 text-[#8b949e]">
                          <span className="font-sans text-xs">Analyzed</span>
                          <span className="text-xs">{step.icon || getFileIcon(step.filename || '')}</span>
                          <span
                            onClick={() => step.filename && onOpenFile?.(step.filename, step.lineRange)}
                            className="font-medium text-[#f0f6fc] hover:text-[#58a6ff] hover:underline cursor-pointer"
                            title={`Inspect ${step.filename}`}
                          >
                            {step.filename}
                          </span>
                          {step.lineRange && (
                            <span className="text-[#6e7681] text-[11px]">{step.lineRange}</span>
                          )}
                          {step.status === 'running' && (
                            <span className="inline-block animate-spin text-[10px] text-[#58a6ff] ml-1">↻</span>
                          )}
                        </div>
                      );
                    }

                    // 2. Thought for 8s >
                    if (step.verb === 'Thought for') {
                      const isExpanded = Boolean(expandedThoughts[step.id]);
                      return (
                        <div key={step.id} className="py-0.5">
                          <div
                            onClick={() => toggleThought(step.id)}
                            className="flex items-center space-x-1 text-[#8b949e] hover:text-[#f0f6fc] cursor-pointer select-none w-fit transition-colors group"
                          >
                            <span className="font-sans text-xs">Thought for {step.thoughtSeconds || 8}s</span>
                            <ChevronRight
                              className={`w-3 h-3 text-[#8b949e] group-hover:text-[#f0f6fc] transition-transform duration-150 ${
                                isExpanded ? 'rotate-90' : ''
                              }`}
                            />
                          </div>
                          {isExpanded && (
                            <div className="pl-3 py-1 my-1 border-l-2 border-[#30363d] bg-[#161b22]/60 rounded-r font-sans text-[11px] text-[#8b949e] whitespace-pre-wrap leading-relaxed">
                              {step.thoughtText || 'Analyzing cognitive state and hypotheses...'}
                            </div>
                          )}
                        </div>
                      );
                    }

                    // 3. Ran ⚡ command >
                    if (step.verb === 'Ran') {
                      const hasOutput = Boolean(step.output);
                      const isExpanded = Boolean(expandedOutputs[step.id]);
                      return (
                        <div key={step.id} className="py-0.5">
                          <div
                            onClick={() => hasOutput && toggleOutput(step.id)}
                            className={`flex items-center space-x-1.5 text-[#8b949e] ${
                              hasOutput ? 'cursor-pointer hover:text-[#f0f6fc] group' : ''
                            }`}
                          >
                            <span className="font-sans text-xs">Ran</span>
                            <span className="text-[#e3b341]">⚡</span>
                            <span className="text-[#f0f6fc] truncate max-w-md">{step.command}</span>
                            {step.status === 'running' && (
                              <span className="inline-block animate-spin text-[10px] text-[#58a6ff] ml-1">↻</span>
                            )}
                            {hasOutput && (
                              <ChevronRight
                                className={`w-3 h-3 text-[#8b949e] group-hover:text-[#f0f6fc] transition-transform duration-150 ${
                                  isExpanded ? 'rotate-90' : ''
                                }`}
                              />
                            )}
                          </div>
                          {isExpanded && step.output && (
                            <div className="my-1.5 p-3 rounded-lg bg-[#010409] text-[#c9d1d9] font-mono text-[11px] overflow-x-auto max-h-56 whitespace-pre-wrap select-text border border-[#30363d]">
                              {step.output}
                            </div>
                          )}
                        </div>
                      );
                    }

                    // 4. Edited ✏️ filename #L1-50
                    if (step.verb === 'Edited') {
                      return (
                        <div
                          key={step.id}
                          onClick={() => step.filename && onOpenFile?.(step.filename, step.lineRange)}
                          className="flex items-center space-x-1.5 py-0.5 text-[#8b949e] cursor-pointer hover:text-[#f0f6fc] group"
                        >
                          <span className="font-sans text-xs">Edited</span>
                          <span className="text-xs">✏️</span>
                          <span className="font-medium text-[#f0f6fc] group-hover:text-[#58a6ff] group-hover:underline">
                            {step.filename}
                          </span>
                          {step.lineRange && (
                            <span className="text-[#6e7681] text-[11px]">{step.lineRange}</span>
                          )}
                          {step.diffStats && (
                            <span className="text-[11px] font-mono ml-1">
                              <span className="text-emerald-400">+{step.diffStats.added}</span>{' '}
                              <span className="text-rose-400">-{step.diffStats.deleted}</span>
                            </span>
                          )}
                        </div>
                      );
                    }

                    // 5. Created 📄 filename
                    if (step.verb === 'Created') {
                      return (
                        <div
                          key={step.id}
                          onClick={() => step.filename && onOpenFile?.(step.filename)}
                          className="flex items-center space-x-1.5 py-0.5 text-[#8b949e] cursor-pointer hover:text-[#f0f6fc] group"
                        >
                          <span className="font-sans text-xs">Created</span>
                          <span className="text-xs">📄</span>
                          <span className="font-medium text-[#f0f6fc] group-hover:text-[#58a6ff] group-hover:underline">
                            {step.filename}
                          </span>
                        </div>
                      );
                    }

                    // 6. Verified 🛡️ summary
                    if (step.verb === 'Verified') {
                      return (
                        <div key={step.id} className="flex items-center space-x-1.5 py-0.5 text-emerald-400">
                          <span className="font-sans text-xs text-[#8b949e]">Verified</span>
                          <span className="text-xs">🛡️</span>
                          <span className="font-medium font-sans text-xs">{step.detail || 'Passed all verification tests'}</span>
                        </div>
                      );
                    }

                    return null;
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Clean Markdown Response Text */}
      {message.content && (
        <div className="text-[#c9d1d9] text-sm leading-relaxed space-y-2 pt-1 font-normal select-text">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ children }) => (
                <h1 className="text-base font-bold text-[#f0f6fc] mt-3 mb-1.5 pb-1 border-b border-[#21262d]">
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-sm font-semibold text-[#f0f6fc] mt-2.5 mb-1">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-sm font-medium text-[#f0f6fc] mt-2 mb-0.5">{children}</h3>
              ),
              p: ({ children }) => (
                <p className="text-sm text-[#c9d1d9] leading-relaxed mb-2.5 font-normal">{children}</p>
              ),
              strong: ({ children }) => <strong className="font-semibold text-[#f0f6fc]">{children}</strong>,
              em: ({ children }) => <em className="italic text-[#8b949e]">{children}</em>,
              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#58a6ff] underline underline-offset-2 hover:text-[#79c0ff] transition-colors inline-flex items-center gap-0.5"
                >
                  <span>{children}</span>
                  <ExternalLink className="w-2.5 h-2.5 inline" />
                </a>
              ),
              ul: ({ children }) => (
                <ul className="list-disc list-inside space-y-1 my-1.5 text-sm text-[#c9d1d9] pl-1">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-inside space-y-1 my-1.5 text-sm text-[#c9d1d9] pl-1">{children}</ol>
              ),
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              blockquote: ({ children }) => (
                <blockquote className="border-l-2 border-[#30363d] pl-3 my-2 text-[#8b949e] italic text-sm">
                  {children}
                </blockquote>
              ),
              pre: ({ children }: any) => <>{children}</>,
              code: ({ className, children, ...props }: any) => {
                const match = /language-(\w+)/.exec(className || '');
                const rawString = String(children);
                const isMultiline = rawString.includes('\n');

                if (!match && !isMultiline) {
                  return (
                    <code
                      className="bg-[#161b22] text-[#f0f6fc] rounded px-1.5 py-0.5 font-mono text-[11.5px] font-medium border border-[#30363d] inline align-baseline mx-0.5"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                }

                const language = match ? match[1] : '';
                return (
                  <div className="rounded-xl bg-[#161b22] border border-[#30363d] overflow-hidden my-3 shadow-md">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-[#0d1117] border-b border-[#30363d] text-[11px] font-mono text-[#8b949e]">
                      <span>{language || 'code'}</span>
                      <button
                        type="button"
                        onClick={() => navigator.clipboard.writeText(rawString)}
                        className="hover:text-[#f0f6fc] text-[10px] flex items-center gap-1 transition-colors"
                      >
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </button>
                    </div>
                    <pre className="p-3.5 overflow-x-auto bg-[#0d1117]">
                      <code className="font-mono text-xs text-[#c9d1d9] leading-relaxed" {...props}>
                        {children}
                      </code>
                    </pre>
                  </div>
                );
              },
              hr: () => <hr className="border-[#21262d] my-3" />,
              table: ({ children }) => (
                <table className="text-xs text-[#c9d1d9] border-collapse w-full my-2">{children}</table>
              ),
              th: ({ children }) => (
                <th className="border border-[#30363d] px-2 py-1 text-[#f0f6fc] bg-[#161b22] font-semibold text-left">
                  {children}
                </th>
              ),
              td: ({ children }) => <td className="border border-[#30363d] px-2 py-1">{children}</td>,
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      )}

      {/* Bottom Minimal Action Bar */}
      <div className="flex items-center space-x-2 pt-1 text-[#8b949e] text-xs">
        <button className="p-1 hover:text-[#f0f6fc] transition-colors" title="Good response">
          <ThumbsUp className="w-3.5 h-3.5" />
        </button>
        <button className="p-1 hover:text-[#f0f6fc] transition-colors" title="Bad response">
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => handleCopy(message.content)}
          className="p-1 hover:text-[#f0f6fc] transition-colors"
          title="Copy message"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  );
};
