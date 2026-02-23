import { getStoredToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (res.status === 401 && path !== "/auth/login") {
    if (typeof window !== "undefined") {
      localStorage.removeItem("occp_token");
      localStorage.removeItem("occp_user");
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }

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

export interface AgentData {
  agent_type: string;
  display_name: string;
  capabilities: string[];
  max_concurrent: number;
  timeout_seconds: number;
  metadata: Record<string, unknown>;
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

export interface LLMProviderHealth {
  healthy: boolean;
  total_calls: number;
  failures: number;
  success_rate: number;
  avg_latency_ms: number;
  consecutive_failures: number;
}

export interface LLMHealthData {
  status: string;
  providers: Record<string, LLMProviderHealth>;
}

export const api = {
  status: () => apiFetch<StatusData>("/status"),
  llmHealth: () => apiFetch<LLMHealthData>("/llm/health"),
  listTasks: () => apiFetch<{ tasks: TaskData[]; total: number }>("/tasks"),
  createTask: (data: { name: string; description: string; agent_type: string; risk_level: string }) =>
    apiFetch<TaskData>("/tasks", { method: "POST", body: JSON.stringify(data) }),
  runPipeline: (taskId: string) =>
    apiFetch<PipelineResult>(`/pipeline/run/${taskId}`, { method: "POST" }),
  evaluatePolicy: (content: string) =>
    apiFetch<PolicyResult>("/policy/evaluate", { method: "POST", body: JSON.stringify({ content }) }),
  auditLog: () => apiFetch<AuditLog>("/audit"),
  listAgents: () => apiFetch<{ agents: AgentData[]; total: number }>("/agents"),
  registerAgent: (data: {
    agent_type: string;
    display_name: string;
    capabilities: string[];
    max_concurrent: number;
    timeout_seconds: number;
    metadata?: Record<string, unknown>;
  }) => apiFetch<AgentData>("/agents", { method: "POST", body: JSON.stringify(data) }),
  deleteAgent: (agentType: string) =>
    apiFetch<void>(`/agents/${agentType}`, { method: "DELETE" }),
};
