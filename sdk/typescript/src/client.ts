/**
 * OCCP TypeScript SDK client – uses native fetch (Node 18+).
 */

import type {
  OCCPClientOptions,
  Task,
  Agent,
  WorkflowInput,
  WorkflowResult,
  AuditEntry,
  PlatformStatus,
} from "./types.js";
import {
  OCCPAPIError,
  AuthenticationError,
  NotFoundError,
  RateLimitError,
} from "./errors.js";

const DEFAULT_BASE_URL = "http://localhost:3000";
const DEFAULT_TIMEOUT = 30_000; // ms

export class OCCPClient {
  private readonly baseUrl: string;
  private apiKey: string;
  private readonly timeout: number;

  constructor(options: OCCPClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.apiKey = options.apiKey ?? "";
    this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
  }

  // ----- Public API -----

  /** POST /api/v1/auth/login — stores token internally. */
  async login(username: string, password: string): Promise<string> {
    const data = await this.request<{ access_token: string }>(
      "POST",
      "/api/v1/auth/login",
      { username, password },
    );
    this.apiKey = data.access_token;
    return data.access_token;
  }

  async getStatus(): Promise<PlatformStatus> {
    return this.request<PlatformStatus>("GET", "/api/v1/status");
  }

  async listAgents(): Promise<{ agents: Agent[]; total: number }> {
    return this.request<{ agents: Agent[]; total: number }>("GET", "/api/v1/agents");
  }

  /** POST /api/v1/tasks — requires auth. */
  async createTask(input: {
    name: string;
    description: string;
    agentType: string;
    riskLevel?: string;
    metadata?: Record<string, unknown>;
  }): Promise<Task> {
    return this.request<Task>("POST", "/api/v1/tasks", {
      name: input.name,
      description: input.description,
      agent_type: input.agentType,
      risk_level: input.riskLevel ?? "low",
      metadata: input.metadata,
    });
  }

  /** POST /api/v1/pipeline/run/{taskId} — requires auth. */
  async runPipeline(taskId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("POST", `/api/v1/pipeline/run/${taskId}`);
  }

  async runWorkflow(input: WorkflowInput): Promise<WorkflowResult> {
    return this.request<WorkflowResult>("POST", "/api/v1/workflows/run", input);
  }

  async getTask(taskId: string): Promise<Task> {
    return this.request<Task>("GET", `/api/v1/tasks/${taskId}`);
  }

  async listTasks(status?: string): Promise<{ tasks: Task[]; total: number }> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<{ tasks: Task[]; total: number }>("GET", `/api/v1/tasks${qs}`);
  }

  async getAuditLog(limit = 100, offset = 0): Promise<{ entries: AuditEntry[]; total: number }> {
    return this.request<{ entries: AuditEntry[]; total: number }>(
      "GET",
      `/api/v1/audit?limit=${limit}&offset=${offset}`,
    );
  }

  // ----- Internal -----

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const res = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        let detail: unknown;
        try {
          detail = JSON.parse(text);
        } catch {
          detail = text;
        }

        if (res.status === 401 || res.status === 403) {
          throw new AuthenticationError(
            typeof detail === "object" && detail !== null && "message" in detail
              ? String((detail as Record<string, unknown>).message)
              : "Authentication failed",
          );
        }
        if (res.status === 404) {
          throw new NotFoundError(path);
        }
        if (res.status === 429) {
          const retry = parseInt(res.headers.get("Retry-After") ?? "60", 10);
          throw new RateLimitError(retry);
        }
        throw new OCCPAPIError(res.status, res.statusText, detail);
      }

      return (await res.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }
}
