import React, { useState } from 'react';
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
  onOpenFile?: (filePath: string) => void;
}

interface AntigravityGroup {
  id: string;
  type: 'explore' | 'edit' | 'commands';
  label: string;
  files?: string[];
  filename?: string;
  fileIcon?: string;
  diffStats?: { added: number; deleted: number };
  actions: AgentAction[];
}

const formatCommandLabel = (title: string, status?: string): string => {
  let clean = title.trim();
  if (clean.startsWith('$ ')) clean = clean.slice(2);
  if (/^run\s+/i.test(clean)) clean = clean.slice(4);

  if (title.toLowerCase().includes('checked task') || title.toLowerCase().includes('checking task')) {
    return clean;
  }
  if (title.toLowerCase().includes('killed task') || title.toLowerCase().includes('canceling') || title.toLowerCase().includes('canceled')) {
    return clean;
  }
  if (title.toLowerCase().startsWith('search code:') || title.toLowerCase().startsWith('web search:')) {
    return clean;
  }

  if (status === 'running') {
    return `Run ${clean}`;
  }
  return `Ran ${clean}`;
};

const getFileIcon = (filename: string): string => {
  const f = filename.toLowerCase();
  if (f.endsWith('.py')) return '🐍';
  if (f.endsWith('.tsx') || f.endsWith('.jsx')) return '⚛️';
  if (f.endsWith('.ts') || f.endsWith('.js')) return '📜';
  if (f.endsWith('.css') || f.endsWith('.html')) return '🎨';
  if (f.endsWith('.json') || f.endsWith('.yaml') || f.endsWith('.yml')) return '⚙️';
  if (f.endsWith('.md')) return '📄';
  return '📄';
};

const cleanFileNameDisplay = (raw: string): string => {
  let clean = raw.trim().replace(/^['"]|['"]$/g, '').replace(/\\/g, '/');
  clean = clean.replace(/^(read|read:|list|list:|inspect)\s+/i, '').trim();
  if (clean.includes('/')) {
    const parts = clean.split('/');
    if (parts[0].includes('(') || parts[0].toLowerCase().includes('folder')) {
      clean = parts.slice(1).join('/');
    }
  }
  return clean || raw;
};

const groupActionsChronologically = (actions: AgentAction[]): AntigravityGroup[] => {
  const groups: AntigravityGroup[] = [];

  for (const act of actions) {
    if (act.type === 'thought') continue;

    const titleLower = (act.title || '').toLowerCase();
    // STRICT: Only actual file reads and directory listings belong in Explored files
    const isFileRead =
      act.type === 'file' &&
      (titleLower.startsWith('read ') ||
        titleLower.startsWith('read:') ||
        titleLower.startsWith('list ') ||
        titleLower.startsWith('list:'));

    const isEditOrCreate =
      !isFileRead &&
      (act.type === 'file' ||
        /^(create|created|write|edit|modify|modified|delete)/i.test(act.title));

    if (isFileRead) {
      const fileName = cleanFileNameDisplay(act.title);
      const lastGroup = groups[groups.length - 1];
      if (lastGroup && lastGroup.type === 'explore') {
        if (fileName && !lastGroup.files?.includes(fileName)) {
          lastGroup.files?.push(fileName);
        }
        lastGroup.actions.push(act);
      } else {
        groups.push({
          id: `grp_${act.id}`,
          type: 'explore',
          label: 'Explored',
          files: [fileName],
          actions: [act],
        });
      }
    } else if (isEditOrCreate) {
      let rawName = act.title
        .replace(/^(create|created:|write|edit|modify|modified:|delete)\s+/i, '')
        .trim();
      if (!rawName && act.detail) rawName = act.detail;
      const basename = cleanFileNameDisplay(rawName.split(/[\\/]/).pop() || rawName);

      let diffStats: { added: number; deleted: number } | undefined;
      const match = /\+(\d+)\s+-(\d+)/.exec(act.detail || '');
      if (match) {
        diffStats = { added: parseInt(match[1]), deleted: parseInt(match[2]) };
      } else if (act.detail && act.detail.includes('lines')) {
        const num = parseInt(act.detail) || 1;
        diffStats = { added: num, deleted: 0 };
      }

      groups.push({
        id: `grp_${act.id}`,
        type: 'edit',
        label: /create/i.test(act.title) ? 'Created' : 'Edited',
        filename: basename,
        fileIcon: getFileIcon(basename),
        diffStats,
        actions: [act],
      });
    } else {
      // Command, status, search, or task step
      const lastGroup = groups[groups.length - 1];
      if (lastGroup && lastGroup.type === 'commands') {
        lastGroup.actions.push(act);
      } else {
        groups.push({
          id: `grp_${act.id}`,
          type: 'commands',
          label: 'Commands',
          actions: [act],
        });
      }
    }
  }

  return groups;
};

export const ChatMessageView: React.FC<ChatMessageViewProps> = ({
  message,
  onOpenFile,
  onOpenSourcesDrawer,
  sourcesCount,
}) => {
  const [copied, setCopied] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [selectedOutput, setSelectedOutput] = useState<string | null>(null);

  const toggleGroup = (id: string, defaultOpen = false) => {
    setExpandedGroups((prev) => ({
      ...prev,
      [id]: prev[id] !== undefined ? !prev[id] : !defaultOpen,
    }));
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // User prompt
  if (message.role === 'user') {
    return (
      <div className="flex justify-end my-4 select-text">
        <div className="max-w-[78%] rounded-2xl px-4 py-3 bg-slate-100 text-sm text-slate-900 space-y-1">
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

  // Deduplicate raw actions
  const rawActions = message.actions || [];
  const groups = groupActionsChronologically(rawActions);
  const isStillRunning = rawActions.some((a) => a.status === 'running');

  return (
    <div className="flex flex-col space-y-2 my-4 max-w-full select-text font-sans">
      {/* Antigravity Minimal Header */}
      <div className="flex items-center space-x-2 text-xs pb-0.5 select-none">
        <span className="w-5 h-5 rounded-md bg-slate-900 flex items-center justify-center text-white text-[10px] font-bold">
          <Sparkles className="w-3 h-3 text-white" />
        </span>
        <span className="font-semibold text-slate-900 tracking-tight text-xs">ASTRA</span>
      </div>

      {/* Antigravity Sequential Activity Stream (Exact Match to Image 1) */}
      {groups.length > 0 && (
        <div className="space-y-1 py-1 text-xs select-none">
          {groups.map((group) => {
            if (group.type === 'explore') {
              const count = group.files?.length || group.actions.length || 1;
              const isExpanded = expandedGroups[group.id] || false;
              return (
                <div key={group.id} className="py-0.5">
                  <div
                    onClick={() => toggleGroup(group.id, false)}
                    className="flex items-center space-x-1.5 text-slate-600 hover:text-slate-900 cursor-pointer w-fit transition-colors"
                  >
                    <span>Explored {count} file{count > 1 ? 's' : ''}</span>
                    <ChevronRight className={`w-3 h-3 text-slate-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                  </div>
                  {isExpanded && (
                    <div className="pl-4 py-0.5 space-y-0.5 mt-0.5 font-mono text-[11px] text-slate-500">
                      {(group.files || []).map((f, i) => (
                        <div
                          key={i}
                          onClick={() => onOpenFile?.(f)}
                          className="flex items-center space-x-1.5 py-0.5 px-1.5 rounded hover:bg-slate-100 hover:text-slate-900 cursor-pointer w-fit transition-colors group"
                          title={`Click to inspect ${f}`}
                        >
                          <span className="text-xs">{getFileIcon(f)}</span>
                          <span className="group-hover:underline text-slate-700">{f}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            }

            if (group.type === 'edit') {
              return (
                <div
                  key={group.id}
                  onClick={() => onOpenFile?.(group.filename || '')}
                  className="flex items-center space-x-1.5 text-slate-800 py-0.5 px-1 rounded hover:bg-slate-50 cursor-pointer font-mono text-xs w-fit transition-colors group"
                  title={`Click to view diff for ${group.filename}`}
                >
                  <span className="text-slate-500 font-sans font-medium">{group.label}</span>
                  <span className="text-sm">{group.fileIcon}</span>
                  <span className="font-semibold text-slate-900 group-hover:underline">{group.filename}</span>
                  {group.diffStats && (
                    <div className="flex items-center space-x-1 text-[11px] font-medium ml-1">
                      <span className="text-emerald-600">+{group.diffStats.added}</span>
                      <span className="text-rose-600">-{group.diffStats.deleted}</span>
                    </div>
                  )}
                </div>
              );
            }

            if (group.type === 'commands') {
              const cmdCount = group.actions.length;
              const hasRunning = group.actions.some((a) => a.status === 'running');
              const isExpanded = expandedGroups[group.id] !== undefined ? expandedGroups[group.id] : hasRunning;

              return (
                <div key={group.id} className="py-0.5">
                  <div
                    onClick={() => toggleGroup(group.id, hasRunning)}
                    className="flex items-center space-x-1.5 text-slate-700 hover:text-slate-950 cursor-pointer w-fit font-medium transition-colors"
                  >
                    <span>
                      {hasRunning
                        ? `Exploring ${Math.max(1, cmdCount)} task${cmdCount > 1 ? 's' : ''}, running ${cmdCount} command${cmdCount > 1 ? 's' : ''}`
                        : `Ran ${cmdCount} command${cmdCount > 1 ? 's' : ''}`}
                    </span>
                    <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isExpanded ? '' : '-rotate-90'}`} />
                  </div>

                  {isExpanded && (
                    <div className="pl-4 py-0.5 space-y-1 mt-0.5">
                      {group.actions.map((act) => {
                        const lbl = formatCommandLabel(act.title, act.status);
                        const hasOut = Boolean(act.output);
                        const isRunningThis = act.status === 'running';

                        return (
                          <div key={act.id}>
                            <div
                              onClick={() => hasOut && setSelectedOutput(selectedOutput === act.id ? null : act.id)}
                              className={`flex items-center space-x-1.5 text-slate-600 hover:text-slate-900 ${
                                hasOut ? 'cursor-pointer' : ''
                              }`}
                            >
                              <span className="truncate">{lbl}</span>
                              {isRunningThis ? (
                                <span className="inline-block animate-spin text-[12px] text-blue-600 shrink-0">↻</span>
                              ) : null}
                              {hasOut ? (
                                <ChevronRight className={`w-3 h-3 text-slate-400 shrink-0 transition-transform ${selectedOutput === act.id ? 'rotate-90' : ''}`} />
                              ) : null}
                            </div>

                            {selectedOutput === act.id && act.output && (
                              <div className="my-1.5 p-3 rounded-lg bg-slate-950 text-slate-200 font-mono text-[11px] overflow-x-auto max-h-56 whitespace-pre-wrap select-text">
                                {act.output}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            }

            return null;
          })}

          {/* Antigravity Working Status Line (Image 1 Style) */}
          {isStillRunning && (
            <div className="text-xs text-slate-600 font-medium py-1 select-none flex items-center space-x-1.5">
              <span>Working.</span>
            </div>
          )}
        </div>
      )}

      {/* Natural Markdown Response Text (NO BORDER BOX, Clean Antigravity Flow) */}
      {message.content && (
        <div className="text-slate-800 text-sm leading-relaxed space-y-2 pt-1 font-normal">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ children }) => (
                <h1 className="text-base font-bold text-slate-900 mt-3 mb-1.5 pb-1 border-b border-slate-100">
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
                <p className="text-sm text-slate-800 leading-relaxed mb-2.5 font-normal">{children}</p>
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
                <ul className="list-disc list-inside space-y-1 my-1.5 text-sm text-slate-800 pl-1">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-inside space-y-1 my-1.5 text-sm text-slate-800 pl-1">{children}</ol>
              ),
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              blockquote: ({ children }) => (
                <blockquote className="border-l-2 border-slate-300 pl-3 my-2 text-slate-500 italic text-sm">
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
                      className="bg-slate-100 text-slate-800 rounded px-1.5 py-0.5 font-mono text-[11.5px] font-medium border border-slate-200 inline align-baseline mx-0.5"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                }

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

      {/* Bottom Minimal Action Bar */}
      <div className="flex items-center space-x-2 pt-1 text-slate-400 text-xs">
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
  );
};
