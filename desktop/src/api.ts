import {
  DiffResult,
  FileNode,
  ModelsResponse,
  ProjectMetadata,
  SessionItem,
  SystemHealth,
} from './types';

const API_BASE = 'http://127.0.0.1:8765';
const WS_BASE = 'ws://127.0.0.1:8765';

export const api = {
  async getHealth(): Promise<SystemHealth> {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  },

  async getModels(): Promise<ModelsResponse> {
    const res = await fetch(`${API_BASE}/api/models`);
    if (!res.ok) throw new Error('Failed to fetch models');
    return res.json();
  },

  async getWorkspace(): Promise<ProjectMetadata> {
    const res = await fetch(`${API_BASE}/api/workspace`);
    if (!res.ok) throw new Error('Failed to fetch workspace metadata');
    return res.json();
  },

  async setWorkspace(path: string): Promise<{ success: boolean; workspace_path: string; metadata: ProjectMetadata }> {
    const res = await fetch(`${API_BASE}/api/workspace/set`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_path: path }),
    });
    if (!res.ok) throw new Error('Failed to set workspace');
    return res.json();
  },

  async getWorkspaceFiles(): Promise<FileNode[]> {
    const res = await fetch(`${API_BASE}/api/workspace/files`);
    if (!res.ok) throw new Error('Failed to fetch workspace files');
    return res.json();
  },

  async getWorkspaceFile(path: string): Promise<{ path: string; content: string }> {
    const res = await fetch(`${API_BASE}/api/workspace/file?path=${encodeURIComponent(path)}`);
    if (!res.ok) throw new Error('Failed to read file');
    return res.json();
  },

  async getWorkspaceDiff(): Promise<DiffResult> {
    const res = await fetch(`${API_BASE}/api/workspace/diff`);
    if (!res.ok) throw new Error('Failed to fetch git diff');
    return res.json();
  },

  async listSessions(): Promise<SessionItem[]> {
    const res = await fetch(`${API_BASE}/api/sessions`);
    if (!res.ok) throw new Error('Failed to list sessions');
    return res.json();
  },

  async getSession(id: string): Promise<SessionItem> {
    const res = await fetch(`${API_BASE}/api/sessions/${id}`);
    if (!res.ok) throw new Error('Failed to get session');
    return res.json();
  },

  async createSession(workspace_path?: string, model?: string, title?: string): Promise<{ session_id: string }> {
    const res = await fetch(`${API_BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_path, model, title }),
    });
    if (!res.ok) throw new Error('Failed to create session');
    return res.json();
  },

  async deleteSession(id: string): Promise<{ deleted: boolean }> {
    const res = await fetch(`${API_BASE}/api/sessions/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete session');
    return res.json();
  },

  async startTask(goal: string, workspace_path?: string, model?: string, session_id?: string): Promise<{ status: string; session_id: string }> {
    const res = await fetch(`${API_BASE}/api/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, workspace_path, model, session_id }),
    });
    if (!res.ok) throw new Error('Failed to start task');
    return res.json();
  },

  async stopTask(session_id: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/api/tasks/${session_id}/stop`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to stop task');
    return res.json();
  },

  async submitApproval(approval_id: string, approved: boolean): Promise<{ approval_id: string; approved: boolean }> {
    const res = await fetch(`${API_BASE}/api/approvals/${approval_id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved }),
    });
    if (!res.ok) throw new Error('Failed to submit approval');
    return res.json();
  },

  connectWebSocket(onEvent: (event: any) => void, onStatusChange?: (status: boolean) => void): WebSocket {
    const ws = new WebSocket(`${WS_BASE}/ws/events`);

    ws.onopen = () => {
      onStatusChange?.(true);
    };

    ws.onmessage = (msgEvent) => {
      try {
        const parsed = JSON.parse(msgEvent.data);
        onEvent(parsed);
      } catch (err) {
        console.error('Failed to parse WS message:', err);
      }
    };

    ws.onclose = () => {
      onStatusChange?.(false);
    };

    ws.onerror = () => {
      onStatusChange?.(false);
    };

    return ws;
  },
};
