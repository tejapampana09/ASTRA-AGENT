import React, { useState } from 'react';
import {
  Sparkles,
  Search,
  PanelLeftClose,
  Plus,
  MessageSquare,
  Network,
  Grid,
  Pin,
  Circle,
  BarChart2,
  HardDrive,
  Settings as SettingsIcon,
  Trash2,
} from 'lucide-react';
import { ModelsResponse, OllamaHealth, SessionItem } from '../types';

interface SidebarProps {
  sessions: SessionItem[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  ollamaHealth?: OllamaHealth;
  modelsData?: ModelsResponse;
  activeNav: 'chat' | 'workspace' | 'models' | 'usage';
  onSelectNav: (nav: 'chat' | 'workspace' | 'models' | 'usage') => void;
  onOpenSettings: () => void;
  workspacePath: string;
  onBrowseWorkspace: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  ollamaHealth,
  modelsData,
  activeNav,
  onSelectNav,
  onOpenSettings,
  workspacePath,
  onBrowseWorkspace,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);

  const filteredSessions = sessions.filter((s) =>
    (s.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <aside className="w-64 bg-[#090d16] border-r border-[#21262d] flex flex-col h-full select-none text-[#8b949e]">
      {/* Brand Header */}
      <div className="p-3.5 flex items-center justify-between border-b border-[#21262d]">
        <div className="flex items-center space-x-2.5 cursor-pointer" onClick={() => onSelectNav('chat')}>
          <div className="w-7 h-7 rounded-lg bg-[#21262d] border border-[#30363d] flex items-center justify-center text-white shadow-xs">
            <Sparkles className="w-4 h-4 text-[#58a6ff]" />
          </div>
          <span className="font-bold text-base text-[#f0f6fc] tracking-tight">ASTRA</span>
        </div>

        <div className="flex items-center space-x-1">
          <button
            onClick={() => setShowSearch(!showSearch)}
            className="p-1.5 rounded-md hover:bg-[#161b22] text-[#8b949e] hover:text-[#f0f6fc] transition-colors"
            title="Search sessions"
          >
            <Search className="w-4 h-4" />
          </button>
          <button
            className="p-1.5 rounded-md hover:bg-[#161b22] text-[#8b949e] hover:text-[#f0f6fc] transition-colors"
            title="Collapse sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full py-2 px-3 rounded-lg bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-[#f0f6fc] text-xs font-medium flex items-center justify-center space-x-2 transition-all shadow-xs"
        >
          <Plus className="w-3.5 h-3.5 text-[#8b949e]" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Main Navigation */}
      <div className="px-3 space-y-0.5 text-xs">
        <button
          onClick={() => onSelectNav('chat')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'chat'
              ? 'bg-[#161b22] text-[#f0f6fc] border border-[#30363d] shadow-xs'
              : 'text-[#8b949e] hover:bg-[#161b22]/50 hover:text-[#f0f6fc]'
          }`}
        >
          <MessageSquare className="w-4 h-4 text-[#8b949e]" />
          <span>Chat</span>
        </button>

        <button
          onClick={() => onSelectNav('workspace')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'workspace'
              ? 'bg-[#161b22] text-[#f0f6fc] border border-[#30363d] shadow-xs'
              : 'text-[#8b949e] hover:bg-[#161b22]/50 hover:text-[#f0f6fc]'
          }`}
        >
          <Network className="w-4 h-4 text-[#8b949e]" />
          <span>Workspace</span>
        </button>

        <button
          onClick={() => onSelectNav('models')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'models'
              ? 'bg-[#161b22] text-[#f0f6fc] border border-[#30363d] shadow-xs'
              : 'text-[#8b949e] hover:bg-[#161b22]/50 hover:text-[#f0f6fc]'
          }`}
        >
          <Grid className="w-4 h-4 text-[#8b949e]" />
          <span>Models</span>
        </button>

        <button
          onClick={() => onSelectNav('usage')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'usage'
              ? 'bg-[#161b22] text-[#f0f6fc] border border-[#30363d] shadow-xs'
              : 'text-[#8b949e] hover:bg-[#161b22]/50 hover:text-[#f0f6fc]'
          }`}
        >
          <BarChart2 className="w-4 h-4 text-[#8b949e]" />
          <span>Usage</span>
        </button>
      </div>

      {/* Session Search Bar (if opened) */}
      {showSearch && (
        <div className="px-3 pt-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter sessions..."
            className="w-full bg-[#161b22] border border-[#30363d] rounded-md px-2.5 py-1 text-xs text-[#f0f6fc] outline-none placeholder-[#6e7681]"
          />
        </div>
      )}

      {/* Chat History List */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4 text-xs">
        {/* Pinned */}
        <div className="space-y-1">
          <div className="flex items-center space-x-1.5 text-[10px] font-semibold tracking-wider uppercase text-[#6e7681] px-2">
            <Pin className="w-3 h-3" />
            <span>PINNED</span>
          </div>
          <div className="py-1 px-2.5 rounded-md hover:bg-[#161b22]/50 text-[#8b949e] hover:text-[#f0f6fc] cursor-pointer flex items-center justify-between group">
            <span className="truncate">Autonomous Refactor</span>
          </div>
        </div>

        {/* Today */}
        <div className="space-y-1">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-[#6e7681] px-2">
            TODAY
          </div>
          {filteredSessions.length === 0 ? (
            <div className="text-[11px] text-[#6e7681] px-2.5 py-1 italic">No recent chats</div>
          ) : (
            filteredSessions.map((s) => {
              const isActive = s.id === activeSessionId;
              return (
                <div
                  key={s.id}
                  onClick={() => onSelectSession(s.id)}
                  className={`py-1.5 px-2.5 rounded-lg cursor-pointer flex items-center justify-between group transition-colors ${
                    isActive
                      ? 'bg-[#161b22] text-[#f0f6fc] font-medium border border-[#30363d] shadow-xs'
                      : 'text-[#8b949e] hover:bg-[#161b22]/50 hover:text-[#f0f6fc]'
                  }`}
                >
                  <div className="flex items-center space-x-2 truncate">
                    <Circle className={`w-2 h-2 ${isActive ? 'text-[#58a6ff] fill-current' : 'text-[#6e7681]'}`} />
                    <span className="truncate text-[11px]">{s.title || 'Untitled Session'}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(s.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 transition-opacity"
                    title="Delete session"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Bottom Status Card & User Badge */}
      <div className="p-3 border-t border-[#21262d] space-y-2.5">
        {/* Ollama Status Card */}
        <div className="p-2.5 rounded-xl bg-[#161b22] border border-[#30363d] text-xs shadow-xs">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center space-x-1.5">
              <HardDrive className="w-3.5 h-3.5 text-[#8b949e]" />
              <span className="font-semibold text-[#f0f6fc] text-[11px]">Ollama Local</span>
            </div>
            <span
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full ${
                ollamaHealth?.connected
                  ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800'
                  : 'bg-rose-950/60 text-rose-400 border border-rose-800'
              }`}
            >
              {ollamaHealth?.connected ? '● Connected' : '● Offline'}
            </span>
          </div>
          <p className="text-[#8b949e] text-[10px] line-clamp-1 mb-2">
            {modelsData?.models?.ollama && modelsData.models.ollama.length > 0
              ? `${modelsData.models.ollama[0].name} ready`
              : ollamaHealth?.connected
              ? 'Ollama connected'
              : 'Run: ollama serve'}
          </p>
          <button
            onClick={() => onSelectNav('models')}
            className="w-full py-1 rounded bg-[#21262d] hover:bg-[#30363d] text-[#c9d1d9] font-medium text-[10px] transition-colors flex items-center justify-center space-x-1 border border-[#30363d]"
          >
            <span>Manage Models ↗</span>
          </button>
        </div>

        {/* User / Workspace Badge */}
        <div className="flex items-center justify-between px-1">
          <div
            onClick={onBrowseWorkspace}
            className="flex items-center space-x-2 cursor-pointer hover:opacity-80 transition-opacity max-w-[170px]"
            title={`Active Workspace: ${workspacePath}`}
          >
            <div className="w-7 h-7 rounded-full bg-[#21262d] border border-[#30363d] flex items-center justify-center text-white text-xs font-bold shadow-xs">
              TP
            </div>
            <div className="truncate">
              <div className="text-xs font-semibold text-[#f0f6fc] truncate">Teja Pampana</div>
              <div className="text-[10px] text-[#8b949e] truncate font-mono">
                {workspacePath.split(/[\\/]/).pop() || 'Workspace'}
              </div>
            </div>
          </div>
          <button
            onClick={onOpenSettings}
            className="p-1.5 rounded-md hover:bg-[#161b22] text-[#8b949e] hover:text-[#f0f6fc] transition-colors"
            title="Open Settings"
          >
            <SettingsIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
