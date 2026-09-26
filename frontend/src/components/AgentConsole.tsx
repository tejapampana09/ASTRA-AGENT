import React, { useState, useEffect, useRef } from 'react';
import {
  Terminal,
  FileCode,
  CheckCircle,
  XCircle,
  Bug,
  GitBranch,
  ShieldCheck,
  Info,
  ChevronDown,
  ChevronRight,
  ArrowDownCircle,
  Play,
  RotateCcw,
} from 'lucide-react';
import { TranslatedActivity } from '../types';

interface Props {
  activities: TranslatedActivity[];
  isRunning: boolean;
}

export const AgentConsole: React.FC<Props> = ({ activities, isRunning }) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const [expandedIndices, setExpandedIndices] = useState<Set<number>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const isUserScrollingRef = useRef(false);

  // Auto-scroll when new activities arrive, unless user scrolled up
  useEffect(() => {
    if (autoScroll && containerRef.current && !isUserScrollingRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [activities, autoScroll]);

  // Handle user scroll detection
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;
    if (atBottom) {
      setAutoScroll(true);
      isUserScrollingRef.current = false;
    } else {
      setAutoScroll(false);
      isUserScrollingRef.current = true;
    }
  };

  const resumeScroll = () => {
    setAutoScroll(true);
    isUserScrollingRef.current = false;
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  };

  const toggleExpand = (idx: number) => {
    setExpandedIndices((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  };

  const renderIcon = (type: TranslatedActivity['iconType']) => {
    switch (type) {
      case 'terminal':
        return <Terminal className="w-3.5 h-3.5 text-amber-400" />;
      case 'file':
        return <FileCode className="w-3.5 h-3.5 text-sky-400" />;
      case 'test_pass':
        return <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />;
      case 'test_fail':
        return <XCircle className="w-3.5 h-3.5 text-rose-400" />;
      case 'debug':
        return <Bug className="w-3.5 h-3.5 text-purple-400" />;
      case 'git':
      case 'pr':
        return <GitBranch className="w-3.5 h-3.5 text-indigo-400" />;
      case 'approval':
        return <ShieldCheck className="w-3.5 h-3.5 text-orange-400" />;
      default:
        return <Info className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col h-[480px] relative">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
            Autonomous Codex Console
          </h3>
        </div>

        <div className="flex items-center gap-3">
          {!autoScroll && (
            <button
              onClick={resumeScroll}
              className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 hover:bg-indigo-900 transition cursor-pointer"
            >
              <ArrowDownCircle className="w-3 h-3" />
              Resume Scroll
            </button>
          )}

          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
            {activities.length} events
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-2 pr-1 font-mono text-xs select-text"
      >
        {activities.length === 0 ? (
          <div className="py-20 text-center flex flex-col items-center justify-center gap-2 text-slate-500">
            <Play className="w-6 h-6 text-slate-600 animate-pulse" />
            <p>Awaiting task dispatch...</p>
            <p className="text-[11px] text-slate-600">Launch an engineering task to observe live execution stream.</p>
          </div>
        ) : (
          activities.map((act, idx) => {
            const isNewest = idx === activities.length - 1;
            const isExpanded = expandedIndices.has(idx);
            const hasPayload = act.rawEvent.payload && Object.keys(act.rawEvent.payload).length > 0;

            return (
              <div
                key={idx}
                className={`p-2.5 rounded-lg border transition-all ${
                  isNewest && isRunning
                    ? 'bg-slate-950 border-indigo-500/50 shadow-sm shadow-indigo-500/10'
                    : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700/80'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 shrink-0">{renderIcon(act.iconType)}</span>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-slate-200 font-medium text-xs truncate">
                        {act.title}
                      </p>
                      <span className="text-[10px] text-slate-500 shrink-0">
                        {formatTime(act.timestamp)}
                      </span>
                    </div>

                    {act.subtitle && (
                      <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                        {act.subtitle}
                      </p>
                    )}

                    {hasPayload && (
                      <div className="mt-1.5">
                        <button
                          onClick={() => toggleExpand(idx)}
                          className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition cursor-pointer"
                        >
                          {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                          {isExpanded ? 'Hide Details' : 'View Payload'}
                        </button>

                        {isExpanded && (
                          <pre className="mt-1.5 p-2 bg-slate-900 border border-slate-800 rounded text-[10px] text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-40">
                            {JSON.stringify(act.rawEvent.payload, null, 2)}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
