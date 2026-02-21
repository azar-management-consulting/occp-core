/**
 * @occp/sdk – TypeScript client for the OpenCloud Control Plane API.
 *
 * Uses native `fetch` (Node 18+) – zero runtime dependencies.
 *
 * @example
 * ```ts
 * import { OCCPClient } from "@occp/sdk";
 *
 * const client = new OCCPClient({ baseUrl: "http://localhost:3000", apiKey: "..." });
 * const status = await client.getStatus();
 * ```
 */

export { OCCPClient } from "./client.js";
export type {
  OCCPClientOptions,
  TaskStatus,
  Task,
  Agent,
  WorkflowInput,
  WorkflowResult,
  AuditEntry,
  PlatformStatus,
} from "./types.js";
export { OCCPAPIError, AuthenticationError, NotFoundError } from "./errors.js";
