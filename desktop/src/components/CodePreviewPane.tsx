import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  GitCompare,
  X,
  Copy,
  Check,
  ExternalLink,
  ChevronRight,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import { DiffResult } from '../types';
import { api } from '../api';

interface CodePreviewPaneProps {
  filePath?: string;
  lineRange?: string; // e.g. "#L1-100" or "#L50-75"
  diffResult?: DiffResult;
  filesModified?: string[];
  filesCreated?: string[];
  onClose: () => void;
  defaultTab?: 'file' | 'diff';
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

export const CodePreviewPane: React.FC<CodePreviewPaneProps> = ({
  filePath,
  lineRange,
  diffResult,
  filesModified = [],
  filesCreated = [],
  onClose,
  defaultTab = 'file',
}) => {
  const [activeTab, setActiveTab] = useState<'file' | 'diff'>(defaultTab);
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const highlightedLineRef = useRef<HTMLDivElement>(null);

  // Parse start and end line from lineRange, e.g. "#L10-25" -> start: 10, end: 25
  const parsedRange = React.useMemo(() => {
    if (!lineRange) return null;
    const match = /#L(\d+)(?:-(\d+))?/.exec(lineRange);
    if (!match) return null;
    const start = parseInt(match[1], 10);
    const end = match[2] ? parseInt(match[2], 10) : start;
    return { start, end };
  }, [lineRange]);

  // Load file content whenever filePath changes
  useEffect(() => {
    if (!filePath) {
      if (diffResult?.diff?.trim()) {
        setActiveTab('diff');
      }
      return;
    }

    let isCancelled = false;
    setLoading(true);
    setError(null);

    api
      .getWorkspaceFile(filePath)
      .then((res) => {
        if (!isCancelled) {
          setFileContent(res.content);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.message || 'Failed to load file');
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [filePath]);

  // Auto-scroll to highlighted line range after file content loads
  useEffect(() => {
    if (parsedRange && highlightedLineRef.current) {
      highlightedLineRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [fileContent, parsedRange]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = fileContent ? fileContent.split('\n') : [];
  const diffLines = diffResult?.diff ? diffResult.diff.split('\n') : [];
  const displayFileName = filePath ? filePath.split(/[\\/]/).pop() || filePath : 'Changes';

  return (
    <div
      className={`h-full flex flex-col bg-[#0d1117] border-l border-[#21262d] shadow-2xl transition-all duration-200 font-sans ${
        isExpanded ? 'w-full' : 'w-[48%] min-w-[380px] max-w-[800px]'
      }`}
    >
      {/* Pane Top Header */}
      <div className="h-11 px-4 bg-[#161b22] border-b border-[#21262d] flex items-center justify-between select-none">
        {/* Left: File Title & Icon */}
        <div className="flex items-center space-x-2 truncate">
          <span className="text-sm">{filePath ? getFileIcon(filePath) : '📄'}</span>
          <span className="font-semibold text-xs text-[#f0f6fc] font-mono truncate">
            {displayFileName}
          </span>
          {lineRange && (
            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-[#1f6feb]/20 text-[#58a6ff] border border-[#1f6feb]/40">
              {lineRange}
            </span>
          )}
        </div>

        {/* Center: Tabs Switcher */}
        <div className="flex items-center space-x-1 bg-[#0d1117] p-0.5 rounded-lg border border-[#21262d] text-xs">
          <button
            onClick={() => setActiveTab('file')}
            className={`px-2.5 py-1 rounded-md font-medium text-[11px] transition-all ${
              activeTab === 'file'
                ? 'bg-[#21262d] text-[#f0f6fc] shadow-xs'
                : 'text-[#8b949e] hover:text-[#f0f6fc]'
            }`}
          >
            File View
          </button>
          <button
            onClick={() => setActiveTab('diff')}
            className={`px-2.5 py-1 rounded-md font-medium text-[11px] transition-all flex items-center space-x-1 ${
              activeTab === 'diff'
                ? 'bg-[#21262d] text-[#f0f6fc] shadow-xs'
                : 'text-[#8b949e] hover:text-[#f0f6fc]'
            }`}
          >
            <GitCompare className="w-3 h-3 text-[#8b949e]" />
            <span>Diff {diffResult?.diff?.trim() ? '●' : ''}</span>
          </button>
        </div>

        {/* Right: Actions (Expand, Copy, Close) */}
        <div className="flex items-center space-x-1 text-[#8b949e]">
          <button
            onClick={() => handleCopy(activeTab === 'file' ? fileContent : diffResult?.diff || '')}
            className="p-1 hover:text-[#f0f6fc] rounded hover:bg-[#21262d] transition-colors"
            title="Copy contents"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 hover:text-[#f0f6fc] rounded hover:bg-[#21262d] transition-colors"
            title={isExpanded ? 'Restore width' : 'Maximize panel'}
          >
            {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={onClose}
            className="p-1 hover:text-[#f0f6fc] rounded hover:bg-[#21262d] transition-colors"
            title="Close preview"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Pane Content Body */}
      <div className="flex-1 overflow-auto bg-[#0d1117] font-mono text-xs select-text">
        {activeTab === 'file' ? (
          loading ? (
            <div className="h-full flex items-center justify-center text-[#8b949e] space-x-2">
              <span className="inline-block animate-spin text-sm text-[#58a6ff]">↻</span>
              <span className="text-xs">Loading {filePath}...</span>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-rose-400 space-y-1">
              <p className="font-semibold text-xs">Error opening file</p>
              <p className="text-[11px] text-[#8b949e]">{error}</p>
            </div>
          ) : !filePath ? (
            <div className="h-full flex flex-col items-center justify-center text-[#8b949e] p-8 text-center space-y-2">
              <FileText className="w-8 h-8 text-[#6e7681]" />
              <p className="text-xs text-[#8b949e]">Select any analyzed or edited file to inspect its code</p>
            </div>
          ) : (
            <div className="py-2">
              {lines.map((lineText, idx) => {
                const lineNum = idx + 1;
                const isHighlighted =
                  parsedRange && lineNum >= parsedRange.start && lineNum <= parsedRange.end;
                const isTargetLine = parsedRange && lineNum === parsedRange.start;

                return (
                  <div
                    key={lineNum}
                    ref={isTargetLine ? highlightedLineRef : undefined}
                    className={`flex items-start text-[11.5px] leading-relaxed group transition-colors ${
                      isHighlighted
                        ? 'bg-[#1f6feb]/15 border-l-2 border-[#58a6ff] text-[#f0f6fc] font-medium'
                        : 'hover:bg-[#161b22] text-[#c9d1d9]'
                    }`}
                  >
                    {/* Line number gutter */}
                    <span
                      className={`w-12 select-none text-right pr-3 text-[10px] shrink-0 font-mono ${
                        isHighlighted ? 'text-[#58a6ff] font-bold' : 'text-[#6e7681] group-hover:text-[#8b949e]'
                      }`}
                    >
                      {lineNum}
                    </span>
                    {/* Code text */}
                    <span className="whitespace-pre overflow-x-auto flex-1 pr-4">{lineText || ' '}</span>
                  </div>
                );
              })}
            </div>
          )
        ) : (
          /* Diff View */
          <div>
            {/* Diff Summary Strip */}
            <div className="px-3 py-1.5 bg-[#161b22] border-b border-[#21262d] flex items-center space-x-3 text-[10px] text-[#8b949e]">
              {filesModified.length > 0 && (
                <span className="text-amber-400 font-semibold">Modified: {filesModified.length}</span>
              )}
              {filesCreated.length > 0 && (
                <span className="text-emerald-400 font-semibold">Created: {filesCreated.length}</span>
              )}
              {diffResult?.branch && <span>Branch: {diffResult.branch}</span>}
            </div>

            {diffLines.length === 0 || !diffResult?.diff?.trim() ? (
              <div className="p-8 text-center text-[#8b949e] text-xs">
                No active git diff changes in workspace.
              </div>
            ) : (
              <div className="py-1">
                {diffLines.map((line, idx) => {
                  let rowStyle = 'text-[#8b949e] hover:bg-[#161b22]';
                  if (line.startsWith('+') && !line.startsWith('+++')) {
                    rowStyle = 'bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500 font-medium';
                  } else if (line.startsWith('-') && !line.startsWith('---')) {
                    rowStyle = 'bg-rose-950/40 text-rose-300 border-l-2 border-rose-500 font-medium';
                  } else if (line.startsWith('@@')) {
                    rowStyle = 'bg-[#1f6feb]/20 text-[#58a6ff] font-semibold py-0.5 my-0.5';
                  }

                  return (
                    <div
                      key={idx}
                      className={`px-3 text-[11px] leading-relaxed whitespace-pre font-mono ${rowStyle}`}
                    >
                      {line || ' '}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pane Footer */}
      <div className="h-6 px-3 bg-[#161b22] border-t border-[#21262d] flex items-center justify-between text-[10px] text-[#8b949e] select-none">
        <span>{filePath ? `${lines.length} lines` : 'Git diff mode'}</span>
        <span>ASTRA Code Inspector</span>
      </div>
    </div>
  );
};
