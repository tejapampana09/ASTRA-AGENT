import React, { useState } from 'react';
import {
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  Search,
  RefreshCw,
  ChevronRight,
  ChevronDown,
} from 'lucide-react';
import { FileNode } from '../types';

interface FileExplorerProps {
  files: FileNode[];
  onSelectFile: (path: string) => void;
  onRefresh: () => void;
  selectedFile?: string;
}

const FileItem: React.FC<{
  node: FileNode;
  onSelect: (path: string) => void;
  selectedFile?: string;
  depth?: number;
}> = ({ node, onSelect, selectedFile, depth = 0 }) => {
  const [isOpen, setIsOpen] = useState(depth === 0);

  if (node.type === 'directory') {
    return (
      <div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center space-x-1.5 py-1 px-2 rounded hover:bg-zinc-800 text-xs text-zinc-300 text-left transition-colors"
          style={{ paddingLeft: `${depth * 14 + 8}px` }}
        >
          {isOpen ? <ChevronDown className="w-3 h-3 text-zinc-500" /> : <ChevronRight className="w-3 h-3 text-zinc-500" />}
          {isOpen ? <FolderOpen className="w-3.5 h-3.5 text-cyan-400" /> : <Folder className="w-3.5 h-3.5 text-cyan-500" />}
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen && node.children && (
          <div>
            {node.children.map((child, i) => (
              <FileItem key={i} node={child} onSelect={onSelect} selectedFile={selectedFile} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  }

  const isSelected = selectedFile === node.path;
  const isCode = node.name.endsWith('.py') || node.name.endsWith('.ts') || node.name.endsWith('.js') || node.name.endsWith('.tsx');

  return (
    <button
      onClick={() => onSelect(node.path)}
      className={`w-full flex items-center space-x-1.5 py-1 px-2 rounded text-xs text-left transition-colors ${
        isSelected ? 'bg-cyan-950/80 text-cyan-300 font-medium' : 'hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200'
      }`}
      style={{ paddingLeft: `${depth * 14 + 20}px` }}
    >
      {isCode ? <FileCode className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" /> : <FileText className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />}
      <span className="truncate">{node.name}</span>
    </button>
  );
};

export const FileExplorer: React.FC<FileExplorerProps> = ({
  files,
  onSelectFile,
  onRefresh,
  selectedFile,
}) => {
  const [filter, setFilter] = useState('');

  const filterFiles = (nodes: FileNode[], query: string): FileNode[] => {
    if (!query) return nodes;
    const lower = query.toLowerCase();

    return nodes.reduce<FileNode[]>((acc, node) => {
      if (node.type === 'directory') {
        const matchingChildren = filterFiles(node.children || [], query);
        if (matchingChildren.length > 0 || node.name.toLowerCase().includes(lower)) {
          acc.push({ ...node, children: matchingChildren });
        }
      } else if (node.name.toLowerCase().includes(lower) || node.path.toLowerCase().includes(lower)) {
        acc.push(node);
      }
      return acc;
    }, []);
  };

  const displayedFiles = filterFiles(files, filter);

  return (
    <div className="w-64 bg-[#161b22] border-r border-[#30363d] flex flex-col h-full select-none">
      {/* Header */}
      <div className="p-2.5 border-b border-[#30363d] flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Explorer</span>
        <button
          onClick={onRefresh}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
          title="Refresh tree"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>

      {/* Filter search */}
      <div className="p-2 border-b border-[#30363d]">
        <div className="flex items-center space-x-1.5 px-2 py-1 rounded bg-[#0d1117] border border-[#30363d]">
          <Search className="w-3 h-3 text-zinc-500" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search files..."
            className="w-full bg-transparent text-xs text-zinc-300 outline-none placeholder-zinc-600"
          />
        </div>
      </div>

      {/* File Tree List */}
      <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
        {displayedFiles.length === 0 ? (
          <div className="p-4 text-center text-xs text-zinc-500">No files found</div>
        ) : (
          displayedFiles.map((n, i) => (
            <FileItem key={i} node={n} onSelect={onSelectFile} selectedFile={selectedFile} />
          ))
        )}
      </div>
    </div>
  );
};
