/** Client configuration options. */
export interface OCCPClientOptions {
  baseUrl?: string;
  apiKey?: string;
  timeout?: number;
}

/** Possible task lifecycle states. */
export type TaskStatus =
  | "pending"
  | "planning"
  | "gated"
  | "executing"
  | "validating"
  | "shipping"
  | "completed"
  | "failed"
  | "rejected";

/** A pipeline task. */
export interface Task {
  id: string;
  name: string;
  description: string;
  agentType: string;
  status: TaskStatus;
  riskLevel: "low" | "medium" | "high" | "critical";
  createdAt: string;
  updatedAt: string;
  plan?: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
}

/** A registered agent adapter. */
export interface Agent {
  agentType: string;
  displayName: string;
  capabilities: string[];
  maxConcurrent: number;
}

/** Input for running a workflow. */
export interface WorkflowInput {
  name: string;
  tasks: Array<{
    name: string;
    description: string;
    agentType: string;
    riskLevel?: "low" | "medium" | "high" | "critical";
    metadata?: Record<string, unknown>;
  }>;
  metadata?: Record<string, unknown>;
}

/** Result of a workflow execution. */
export interface WorkflowResult {
  workflowId: string;
  status: "running" | "completed" | "failed";
  tasks: Task[];
}

/** A single audit log entry. */
export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  taskId: string;
  detail: Record<string, unknown>;
  prevHash: string;
  hash: string;
}

/** Platform status summary. */
export interface PlatformStatus {
  platform: string;
  version: string;
  status: "running" | "stopped" | "error";
  agents: Agent[];
  pipelinesActive: number;
}
