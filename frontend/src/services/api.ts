import { Task, ApprovalTicket, AgentEvent } from '../types';

export const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8080/api';

export async function createTask(
  goal: string,
  repository_path?: string,
  model?: string,
  mode?: string
): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, repository_path, model, mode }),
  });
  if (!res.ok) throw new Error(`Failed to create task: ${res.statusText}`);
  return res.json();
}

export async function getTask(taskId: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}`);
  if (!res.ok) throw new Error(`Failed to fetch task: ${res.statusText}`);
  return res.json();
}

export async function listTasks(): Promise<Task[]> {
  const res = await fetch(`${API_BASE}/tasks`);
  if (!res.ok) throw new Error(`Failed to list tasks: ${res.statusText}`);
  return res.json();
}

export async function cancelTask(taskId: string): Promise<void> {
  await fetch(`${API_BASE}/tasks/${taskId}/cancel`, { method: 'POST' });
}

export async function getEventHistory(taskId: string, limit: number = 200): Promise<AgentEvent[]> {
  const res = await fetch(`${API_BASE}/events/history/${taskId}?limit=${limit}`);
  if (!res.ok) {
    if (res.status === 404) return [];
    throw new Error(`Failed to fetch event history: ${res.statusText}`);
  }
  return res.json();
}

export async function listApprovals(): Promise<ApprovalTicket[]> {
  const res = await fetch(`${API_BASE}/approvals`);
  if (!res.ok) return [];
  return res.json();
}

export async function approveTicket(ticketId: string, comment?: string): Promise<void> {
  await fetch(`${API_BASE}/approvals/${ticketId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comment }),
  });
}

export async function rejectTicket(ticketId: string, comment?: string): Promise<void> {
  await fetch(`${API_BASE}/approvals/${ticketId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comment }),
  });
}

export async function recoverTask(taskId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/recover`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to recover task: ${res.statusText}`);
  return res.json();
}

export async function getTaskHealth(taskId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/health`);
  if (!res.ok) throw new Error(`Failed to fetch health: ${res.statusText}`);
  return res.json();
}

export async function getTaskAudit(taskId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/audit`);
  if (!res.ok) throw new Error(`Failed to fetch audit: ${res.statusText}`);
  return res.json();
}
