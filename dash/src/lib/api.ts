const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API ${res.status}`);
  }
  return res.json();
}

export interface TaskData {
  id: string;
  name: string;
  description: string;
  agent_type: string;
  status: string;
  risk_level: string;
  created_at: string;
  updated_at: string;
  plan: Record<string, unknown> | null;
  error: string | null;
}

export interface PipelineResult {
  task_id: string;
  success: boolean;
  status: string;
  started_at: string;
  finished_at: string;
  evidence: Record<string, unknown>;
  error: string | null;
}

export interface StatusData {
  platform: string;
  version: string;
  status: string;
  tasks_count: number;
  audit_entries: number;
}

export interface GuardResult {
  guard: string;
  passed: boolean;
  detail: string;
}

export interface PolicyResult {
  approved: boolean;
  results: GuardResult[];
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  task_id: string;
  detail: string;
  prev_hash: string;
  hash: string;
}

export interface AuditLog {
  entries: AuditEntry[];
  chain_valid: boolean;
  total: number;
}

export const api = {
  status: () => apiFetch<StatusData>("/status"),
  listTasks: () => apiFetch<{ tasks: TaskData[]; total: number }>("/tasks"),
  createTask: (data: { name: string; description: string; agent_type: string; risk_level: string }) =>
    apiFetch<TaskData>("/tasks", { method: "POST", body: JSON.stringify(data) }),
  runPipeline: (taskId: string) =>
    apiFetch<PipelineResult>(`/pipeline/run/${taskId}`, { method: "POST" }),
  evaluatePolicy: (content: string) =>
    apiFetch<PolicyResult>("/policy/evaluate", { method: "POST", body: JSON.stringify({ content }) }),
  auditLog: () => apiFetch<AuditLog>("/audit"),
};
