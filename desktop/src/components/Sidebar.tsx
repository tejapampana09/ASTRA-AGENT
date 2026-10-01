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
  MoreHorizontal,
  ChevronDown,
  BarChart2,
  HardDrive,
  Settings as SettingsIcon,
  Trash2,
  FolderOpen,
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
    <aside className="w-64 bg-[#141519] border-r border-[#22242a] flex flex-col h-full select-none text-zinc-300">
      {/* Brand Header */}
      <div className="p-3.5 flex items-center justify-between border-b border-[#202228]">
        <div className="flex items-center space-x-2.5 cursor-pointer" onClick={() => onSelectNav('chat')}>
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-purple-600 to-violet-400 flex items-center justify-center text-white shadow-md shadow-purple-500/30">
            <Sparkles className="w-4 h-4" />
          </div>
          <span className="font-bold text-base text-white tracking-wide">ASTRA</span>
        </div>

        <div className="flex items-center space-x-1">
          <button
            onClick={() => setShowSearch(!showSearch)}
            className="p-1.5 rounded-md hover:bg-zinc-800/60 text-zinc-400 hover:text-white transition-colors"
            title="Search sessions"
          >
            <Search className="w-4 h-4" />
          </button>
          <button
            className="p-1.5 rounded-md hover:bg-zinc-800/60 text-zinc-400 hover:text-white transition-colors"
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
          className="w-full py-2 px-3 rounded-lg bg-[#1c1d23] hover:bg-[#25272e] border border-[#2d2f38] text-white text-xs font-medium flex items-center justify-center space-x-2 transition-all shadow-sm"
        >
          <Plus className="w-3.5 h-3.5 text-zinc-400" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Main Navigation */}
      <div className="px-3 space-y-0.5 text-xs">
        <button
          onClick={() => onSelectNav('chat')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'chat'
              ? 'bg-[#22242c] text-white'
              : 'text-zinc-400 hover:bg-[#1a1b21] hover:text-zinc-200'
          }`}
        >
          <MessageSquare className="w-4 h-4 text-violet-400" />
          <span>Chat</span>
        </button>

        <button
          onClick={() => onSelectNav('workspace')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'workspace'
              ? 'bg-[#22242c] text-white'
              : 'text-zinc-400 hover:bg-[#1a1b21] hover:text-zinc-200'
          }`}
        >
          <Network className="w-4 h-4 text-cyan-400" />
          <span>Workspace</span>
        </button>

        <button
          onClick={() => onSelectNav('models')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'models'
              ? 'bg-[#22242c] text-white'
              : 'text-zinc-400 hover:bg-[#1a1b21] hover:text-zinc-200'
          }`}
        >
          <Grid className="w-4 h-4 text-purple-400" />
          <span>Models</span>
        </button>

        <button
          onClick={() => onSelectNav('usage')}
          className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg transition-colors font-medium ${
            activeNav === 'usage'
              ? 'bg-[#22242c] text-white'
              : 'text-zinc-400 hover:bg-[#1a1b21] hover:text-zinc-200'
          }`}
        >
          <BarChart2 className="w-4 h-4 text-emerald-400" />
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
            className="w-full bg-[#1c1d23] border border-[#2d2f38] rounded-md px-2.5 py-1 text-xs text-zinc-200 outline-none placeholder-zinc-500"
          />
        </div>
      )}

      {/* Chat History List */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4 text-xs">
        {/* Pinned */}
        <div className="space-y-1">
          <div className="flex items-center space-x-1.5 text-[10px] font-semibold tracking-wider uppercase text-zinc-500 px-2">
            <Pin className="w-3 h-3" />
            <span>PINNED</span>
          </div>
          <div className="py-1 px-2.5 rounded-md hover:bg-[#1b1c22] text-zinc-400 cursor-pointer flex items-center justify-between group">
            <span className="truncate">Autonomous Refactor</span>
          </div>
        </div>

        {/* Today */}
        <div className="space-y-1">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-zinc-500 px-2">
            TODAY
          </div>
          {filteredSessions.length === 0 ? (
            <div className="text-[11px] text-zinc-600 px-2.5 py-1 italic">No recent chats</div>
          ) : (
            filteredSessions.map((s) => {
              const isActive = s.id === activeSessionId;
              return (
                <div
                  key={s.id}
                  onClick={() => onSelectSession(s.id)}
                  className={`py-1.5 px-2.5 rounded-lg cursor-pointer flex items-center justify-between group transition-colors ${
                    isActive ? 'bg-[#22242c] text-white font-medium' : 'text-zinc-400 hover:bg-[#1a1b21] hover:text-zinc-200'
                  }`}
                >
                  <div className="flex items-center space-x-2 truncate">
                    <Circle className={`w-2 h-2 ${isActive ? 'text-violet-400 fill-current' : 'text-zinc-600'}`} />
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
      <div className="p-3 border-t border-[#202228] space-y-2.5">
        {/* Ollama Status Card */}
        <div className="p-2.5 rounded-xl bg-[#191a21] border border-[#2b2d37] text-xs">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center space-x-1.5">
              <HardDrive className="w-3.5 h-3.5 text-violet-400" />
              <span className="font-semibold text-white text-[11px]">Ollama Local</span>
            </div>
            <span
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full ${
                ollamaHealth?.connected
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/60'
                  : 'bg-rose-950 text-rose-400 border border-rose-800/60'
              }`}
            >
              {ollamaHealth?.connected ? '● Connected' : '● Offline'}
            </span>
          </div>
          <p className="text-zinc-400 text-[10px] line-clamp-1 mb-2">
            {modelsData?.models?.ollama && modelsData.models.ollama.length > 0
              ? `${modelsData.models.ollama[0].name} ready`
              : ollamaHealth?.connected
              ? 'Ollama connected'
              : 'Run: ollama serve'}
          </p>
          <button
            onClick={() => onSelectNav('models')}
            className="w-full py-1 rounded bg-[#242631] hover:bg-[#2d303d] text-violet-300 font-medium text-[10px] transition-colors flex items-center justify-center space-x-1"
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
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center text-white text-xs font-bold shadow-sm">
              TP
            </div>
            <div className="truncate">
              <div className="text-xs font-medium text-white truncate">Teja Pampana</div>
              <div className="text-[10px] text-zinc-500 truncate font-mono">
                {workspacePath.split(/[\\/]/).pop() || 'Workspace'}
              </div>
            </div>
          </div>
          <button
            onClick={onOpenSettings}
            className="p-1.5 rounded-md hover:bg-zinc-800/70 text-zinc-400 hover:text-white transition-colors"
            title="Open Settings"
          >
            <SettingsIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
