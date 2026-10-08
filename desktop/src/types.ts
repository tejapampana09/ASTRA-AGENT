export type AgentState =
  | 'IDLE'
  | 'PLANNING'
  | 'EXPLORING'
  | 'EXECUTING'
  | 'OBSERVING'
  | 'VERIFYING'
  | 'FIXING'
  | 'WAITING_FOR_APPROVAL'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'CONVERSATION'
  | 'UNDERSTAND'
  | 'INVESTIGATE'
  | 'DIAGNOSE'
  | 'PLAN'
  | 'EXECUTE'
  | 'OBSERVE'
  | 'VERIFY'
  | 'REPLAN'
  | 'RECOVER'
  | 'DONE'
  | 'BLOCKED';

export interface AgentEvent {
  event_type: string;
  state: AgentState;
  data: Record<string, any>;
  session_id: string;
  timestamp: number;
}

export interface OllamaHealth {
  connected: boolean;
  status: string;
  version?: string;
  endpoint: string;
  message: string;
}

export interface SystemHealth {
  status: string;
  version: string;
  ollama: OllamaHealth;
  active_workspace: string;
  project_type: string;
  default_model: string;
  active_tasks_count: number;
}

export interface ModelItem {
  id: string;
  name: string;
  provider: 'ollama' | 'gemini' | 'groq' | 'teja';
  size?: string;
}

export interface ModelsResponse {
  providers: {
    ollama: OllamaHealth;
    gemini: { connected: boolean; status: string; message: string };
    groq: { connected: boolean; status: string; message: string };
    teja: { connected: boolean; status: string; message: string };
  };
  models: {
    ollama: ModelItem[];
    gemini: ModelItem[];
    groq: ModelItem[];
    teja: ModelItem[];
  };
}

export interface ProjectMetadata {
  workspace_path: string;
  project_type: string;
  project_types: string[];
  package_manager: string;
  test_command?: string;
  build_command?: string;
  lint_command?: string;
  has_git: boolean;
  git_branch: string;
  total_files: number;
  key_manifests: string[];
}

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileNode[];
}

export interface SessionItem {
  id: string;
  title: string;
  workspace_path: string;
  model: string;
  state: AgentState;
  summary: string;
  created_at: number;
  updated_at: number;
  messages?: any[];
  files_modified?: string[];
}

export interface DiffResult {
  diff: string;
  status: string;
  branch: string;
}

declare global {
  interface Window {
    electronAPI?: {
      selectDirectory: () => Promise<string | null>;
      openPath: (path: string) => Promise<string>;
      platform: string;
    };
  }
}
