# OPENCLAW-GAP-ANALYSIS.md — OCCP v1.0 Integration Plan

**Version:** 2.0.0 | **Date:** 2026-02-27
**Research basis:** OpenClaw (formerly Clawdbot/Moltbot) — ~236K GitHub stars, MIT license, TypeScript
**OpenClaw audit:** CrowdStrike Jan 2026 — 512 vulnerabilities, 8 critical

---

## B1: Gap List

| GAP-ID | Short Name | Strategy | What OpenClaw Has | What OCCP Lacks | Impact |
|--------|-----------|:--------:|-------------------|-----------------|--------|
| GAP-01 | Messaging Adapters | ✅ | 12+ channel adapters (WhatsApp/Baileys, Telegram/grammY, Discord/discord.js, Slack/Bolt, Signal, iMessage, Teams, Matrix, LINE, WeChat, custom WebSocket) | Zero messaging adapters. API-only interaction model. | **Critical** — Cannot reach users where they are. Primary adoption blocker. |
| GAP-02 | Memory System | ✅ | Hybrid vector + BM25 + SQLite structured. Daily compaction. Cross-session persistence. | No memory beyond session-scoped context. No vector search. No compaction. | **High** — Agents cannot learn or recall across sessions. Limits utility. |
| GAP-03 | Skill Marketplace | ⚠ | ClawHub: 5,705+ community skills. Install via `openclaw install`. Reviews, ratings, version management. | No marketplace. Skills are code-level integrations only. | **High** — No ecosystem growth. Every integration requires engineering. |
| GAP-04 | Config-First Agents | ✅ | AGENTS.md, SOUL.md, TOOLS.md — Markdown-based agent definition. Hot-reload. No-code agent creation. | Agent definition requires Python code in `orchestrator/`. No config-first approach. | **Medium** — Higher barrier to agent creation. Limits non-developer adoption. |
| GAP-05 | Cron & Scheduling | ✅ | Built-in cron with timezone, retry, webhook triggers. | No scheduling capability. All execution is request-driven. | **High** — Cannot run autonomous tasks. Major enterprise feature gap. |
| GAP-06 | Browser Automation | ✅ | Playwright integration with screenshot, navigation, interaction. | No browser adapter. | **Medium** — Cannot perform web-based tasks. Common agent use case. |
| GAP-07 | Agent Canvas (A2UI) | ✅ | Interactive HTML workspace. Agent-generated UI via WebSocket. Charts, forms, rich content. | Dashboard is read-only monitoring. No agent-generated interactive content. | **Medium** — Limits agent output to plain text. |
| GAP-08 | Plugin System | ⚠ | TypeScript plugin host. Hot-loading. Crash isolation. 50+ built-in integrations. | No plugin system. Extensions require core code changes. | **High** — Cannot extend without core development. Limits ecosystem. |
| GAP-09 | SSE/Streaming | ✅ | Real-time streaming responses via Server-Sent Events. | SDKs return complete responses only. No streaming. | **Medium** — Poor UX for long-running tasks. |
| GAP-10 | Native MCP Client | ✅ | Full MCP client via @modelcontextprotocol/sdk@1.25.3. Auto-discovery, tool execution. | MCP configurator only. No native MCP protocol client. | **High** — Cannot leverage MCP ecosystem of tools natively. |
| GAP-11 | Security Audit CLI | ⚠ | `openclaw security audit` — checks config, secrets, TLS, permissions. | No security audit command. Manual verification only. | **Medium** — No automated security posture validation. |
| GAP-12 | Multi-Platform Discord Bot | ✅ | Discord role mapping, slash commands, DM isolation. Production-grade. | No Discord integration. | **Medium** — Missing developer community channel. |
| GAP-13 | Webhook Receiver | ✅ | Inbound webhooks with validation, routing, retry. | No webhook endpoint. | **High** — Cannot receive external events. Limits automation. |
| GAP-14 | Event Triggers | ⚠ | Configurable triggers on audit events, thresholds, external signals. | No event-driven execution. | **Medium** — Cannot react to system state changes. |
| GAP-15 | Local Model Support | ⚠ | Ollama integration with auto-detection, fallback chain. | OllamaPlanner stub exists but not functional. | **Low** — Nice-to-have for development. Not enterprise priority. |
| GAP-16 | Session Management | ✅ | Main/DM/group session types with isolated contexts, tools, permissions. | Single session type. No context isolation by channel/thread. | **Medium** — Cannot scope tools per conversation type. |

### OCCP Advantages (Where OpenClaw Lacks)

| ADV-ID | Feature | Strategy | OCCP Has | OpenClaw Lacks |
|--------|---------|:--------:|----------|----------------|
| ADV-01 | Tamper-Evident Audit | 🔁 | SHA-256 hash chain, per-entry linked | No cryptographic audit trail |
| ADV-02 | Non-Bypassable VAP | 🔁 | 5-stage pipeline, no skip paths | Tool policy has precedence overrides |
| ADV-03 | RBAC (Casbin) | 🔁 | 4-role hierarchy with enforcement | Single-user trust model |
| ADV-04 | AES-256-GCM Encryption | 🔁 | Per-token DEK with HKDF | No at-rest encryption |
| ADV-05 | Sandbox Execution | 🔁 | nsjail → bwrap → process → mock | Process-level isolation only |
| ADV-06 | Supply Chain Scanner | 🔁 | Typosquatting + homoglyph detection | No supply chain verification |
| ADV-07 | Policy Guards | 🔁 | PII, injection, resource, output, human oversight | Basic content filter only |
| ADV-08 | Multi-LLM Failover | 🔁 | Anthropic → OpenAI → Echo with circuit breaker | OpenAI-primary, Anthropic fallback |
| ADV-09 | Docker Security | 🔁 | no-new-privileges, read_only, capability drops | Standard Docker compose |
| ADV-10 | CI Pipeline | 🔁 | 6 checks: multi-Python, node, SDK, secrets | Basic CI |

### Strategy Legend

| Symbol | Meaning | Count |
|:------:|---------|:-----:|
| ✅ | **Full equivalent** — OpenClaw has mature implementation. Study architecture, adapt with OCCP governance wrappers. | 11 |
| ⚠ | **Partial equivalent** — OpenClaw has basic implementation but lacks security model. Adapt architecture, build governance from scratch. | 5 |
| ❌ | **No equivalent** — Build entirely from scratch. OpenClaw provides no reference. | 0 |
| 🔁 | **Reverse gap** — OCCP advantage. OpenClaw lacks this capability entirely. Protect and extend. | 10 |

**Summary:** 11/16 gaps have full OpenClaw equivalents to study (69%). 5/16 require significant OCCP-original governance work (31%). 0 gaps require pure greenfield. 10 OCCP advantages represent durable competitive moat.

---

## B2: Integration Plan

### GAP-01: Messaging Adapters → REQ-CHAN-01 through REQ-CHAN-05

**Proposed Module:** `adapters/channels/` (new package)

**Architecture:**
```
InboundMessage (from any adapter)
    │
    ├── adapters/channels/base.py      ← ChannelAdapter Protocol
    ├── adapters/channels/whatsapp.py  ← Baileys (Node.js sidecar)
    ├── adapters/channels/telegram.py  ← grammY (Node.js sidecar)
    ├── adapters/channels/slack.py     ← Bolt (Python native)
    ├── adapters/channels/discord.py   ← discord.js (Node.js sidecar)
    │
    ▼
orchestrator/message_pipeline.py → normalize → VAP pipeline
```

**Security/Governance Integration:**
- Every inbound message normalized to `InboundMessage` dataclass before entering VAP
- Channel identity mapped to OCCP user via `api/rbac.py` (existing)
- Message content passes through all policy guards (injection, PII, resource)
- Outbound messages pass through output sanitization guard
- All adapter events (connect, disconnect, error, message) in SHA-256 audit chain

**Dependencies:** Node.js sidecar for WhatsApp/Telegram/Discord (Baileys, grammY, discord.js are JS libraries). Communication via internal HTTP/WebSocket. Slack Bolt has Python SDK — native integration.

**Testable Acceptance Criteria:**
1. New adapter implementable in <200 LOC using ChannelAdapter Protocol
2. WhatsApp QR pairing completes within 30s
3. Messages from all 4 channels produce identical `InboundMessage` fields
4. All inbound messages traverse full VAP (fuzz: 1000 messages, 0 bypass)
5. Adapter failure triggers automatic reconnect within 10s
6. All adapter lifecycle events in audit trail

---

### GAP-02: Memory System → REQ-MEM-01 through REQ-MEM-03

**Proposed Module:** `store/memory/` (new package)

**Architecture:**
```
store/memory/
    ├── hybrid.py       ← Fusion retriever (vector + BM25 + SQL)
    ├── compactor.py    ← Daily summarization + archival
    ├── knowledge.py    ← Cross-session shared knowledge base
    ├── embeddings.py   ← Embedding provider abstraction
    └── index.py        ← BM25 index management
```

**Security/Governance Integration:**
- Memory writes create audit trail entries (who wrote what, when)
- Memory reads filtered through RBAC — no cross-org memory access
- Memory compaction summaries inherit classification of source data
- PII guard applied to memory content before storage
- Knowledge base entries versioned; deletes are soft-deletes with audit
- Vector DB (ChromaDB/Qdrant) deployed in same Docker network, no external exposure

**Dependencies:** ChromaDB or Qdrant for vector storage. rank-bm25 for keyword search. Embedding model: OpenAI ada-002 or local sentence-transformers.

**Testable Acceptance Criteria:**
1. Semantic query ("meetings about budget") returns relevant results from vector index
2. Exact keyword query ("REQ-GOV-01") returns exact matches from BM25 index
3. Fusion ranking p95 <200ms on 100K document corpus
4. Memory compaction reduces storage ≥60% for 30-day conversation history
5. Agent A writes fact in Session 1 → Agent B retrieves in Session 2
6. Org A memory invisible to Org B user (even via direct DB query)

---

### GAP-03: Skill Marketplace → REQ-MARKET-01, REQ-TSF-01 through REQ-TSF-05

**Proposed Module:** `api/routes/hub.py`, `cli/skills.py` (new)

**Architecture:**
```
OCCPHub Registry (hosted service)
    │
    ├── Submission: occp skill publish → scan pipeline → registry
    ├── Install: occp skill install name@version → verify → sandbox
    ├── Search: occp skill search query → ranked results
    └── Private: org-scoped registry (self-hosted option)

Scan Pipeline:
    Semgrep (SAST) → Snyk (SCA) → GitGuardian (secrets) → Capability validation → Sign (cosign)
```

**Security/Governance Integration:**
- Every skill must pass 4-stage scan pipeline before publishing
- Skills signed with cosign; runtime verification on every load (REQ-CPC-02, REQ-CPC-03)
- Capability declaration schema mandatory (REQ-TSF-02) — skill declares network/file/command scope
- SBOM generated per version (REQ-TSF-03)
- Version pinning enforced in production via `skills.lock` (REQ-TSF-04)
- Private-first: default registry is org-scoped, OCCPHub opt-in (REQ-TSF-01)
- Revocation framework for zero-day response (REQ-CPC-04)

**Dependencies:** Sigstore/cosign for signing. Semgrep, Snyk, GitGuardian MCPs for scanning. CycloneDX for SBOM. Hosted registry backend (S3-compatible storage + PostgreSQL metadata).

**Testable Acceptance Criteria:**
1. `occp skill publish my-skill` triggers full scan pipeline
2. Skill with hardcoded API key → rejected at scan stage
3. Skill without capability manifest → rejected at validation
4. Unsigned skill → rejected at runtime load
5. `occp skill search "web scraping"` returns ranked results
6. `skills.lock` enforced in production mode (no floating versions)
7. Revoked skill blocked within 5-minute polling cycle

---

### GAP-04: Config-First Agents → REQ-CORE-03

**Proposed Module:** `orchestrator/config_loader.py` (new)

**Architecture:**
```
agents/
    ├── my-agent/
    │   ├── AGENT.md      ← Name, description, model, temperature
    │   ├── SOUL.md       ← System prompt, personality, constraints
    │   └── TOOLS.md      ← Allowed tools, skill references
    └── another-agent/
        └── ...

config_loader.py watches directory → validates schema → registers agent → hot-reload on change
```

**Security/Governance Integration:**
- AGENT.md validated against JSON schema (embedded in Markdown frontmatter)
- TOOLS.md references must exist in registered skill/tool inventory
- New agent registration triggers policy gate evaluation (does this role have permission?)
- Agent config changes create audit entry with before/after diff
- Hot-reload limited to non-production environments by default

**Dependencies:** Watchdog library for file system monitoring. Markdown parser (python-markdown or mdformat).

**Testable Acceptance Criteria:**
1. Placing valid `AGENT.md` in `agents/` directory auto-registers agent within 5s
2. Invalid AGENT.md (missing required fields) → validation error logged, not registered
3. TOOLS.md referencing non-existent skill → validation error
4. Config change triggers audit entry with SHA-256 of old and new config
5. Hot-reload disabled when `OCCP_ENV=production` (explicit `--allow-reload` flag required)

---

### GAP-05: Cron & Scheduling → REQ-VSTA-01 through REQ-VSTA-04, REQ-AUTO-01

**Proposed Module:** `orchestrator/cron.py`, `orchestrator/scheduler.py` (new)

**Architecture:**
```
cron.py:
    APScheduler backend → job definition → VAP pipeline trigger
    │
    ├── Job creates Task with source=cron
    ├── Task enters full VAP (Plan → Gate → Execute → Validate → Ship)
    ├── Policy profile applied per-job (strict/standard/permissive)
    └── Budget guard tracks token/cost per execution

scheduler.py:
    Timeout manager → SIGTERM → grace period → SIGKILL → cleanup
```

**Security/Governance Integration:**
- Every cron execution enters full VAP pipeline (REQ-VSTA-01) — no shortcut
- Policy template profiles determine guard activation level (REQ-VSTA-02)
- Per-job token budget enforced; 80% warning, 100% hard kill (REQ-VSTA-03)
- Time-bound execution: SIGTERM → 10s grace → SIGKILL (REQ-VSTA-04)
- All scheduled executions produce full audit trail entries
- Cron definitions stored in version-controlled YAML

**Dependencies:** APScheduler for cron scheduling. Existing VAP pipeline. Existing policy guards.

**Testable Acceptance Criteria:**
1. `occp cron add "*/5 * * * *" --agent=reporter --profile=strict` registers job
2. Job fires at scheduled time and enters full 5-stage VAP
3. Gate rejection stops job, creates alert, does NOT retry
4. Budget limit exceeded → job terminated, remaining budget logged
5. Job stuck beyond timeout → graceful kill → forced kill → sandbox cleanup
6. All cron executions visible in audit trail with `source=cron` tag

---

### GAP-06: Browser Automation → REQ-CBDB-01 through REQ-CBDB-05

**Proposed Module:** `adapters/browser_adapter.py`, `policy_engine/browser_policy.py` (new)

**Architecture:**
```
browser_adapter.py:
    Playwright → BrowserContext (isolated per session)
    │
    ├── Navigation → policy_engine/browser_policy.py → domain check
    ├── Form submit → approval flag check
    ├── Download → type/size/domain check → sandbox storage
    └── All interactions → SHA-256 audit chain + screenshots

browser_policy.py:
    ├── Domain allow/deny list (default-deny)
    ├── Form submission approval flags
    └── Download restrictions (type, size, domain)
```

**Security/Governance Integration:**
- Each session gets isolated Playwright BrowserContext (separate cookies, storage)
- BrowserContext destroyed on session end (no persistent browser state)
- Domain navigation policy-gated: default-deny with explicit allowlist
- Form submission requires explicit approval flag in policy (default: blocked)
- Downloads stored in sandbox, not host filesystem; scanned before access
- All browser interactions (nav, click, form, download) hash-chained in audit
- Screenshots at key actions (form submit, navigation) stored in audit
- No access to host filesystem, clipboard, or other browser profiles

**Dependencies:** Playwright Python SDK. Existing sandbox infrastructure (nsjail/bwrap).

**Testable Acceptance Criteria:**
1. Session A cookies/storage invisible to Session B
2. Navigation to non-allowlisted domain → blocked + audit entry
3. Form submit without approval flag → blocked + audit entry
4. Download of .exe → blocked by default
5. Download >50MB → blocked by default
6. Browser profile destroyed within 10s of session end
7. Audit chain for browser session independently verifiable

---

### GAP-07: Agent Canvas → REQ-A2UI-01

**Proposed Module:** `dash/src/app/canvas/`, `api/routes/canvas.py` (new)

**Architecture:**
```
Agent → api/routes/canvas.py → WebSocket push → dash/src/app/canvas/
    │
    ├── HTML content sanitized (DOMPurify)
    ├── Rendered in sandboxed iframe (sandbox="allow-scripts")
    ├── No parent DOM access (same-origin policy via srcdoc)
    └── Canvas disabled by default (policy-gated)
```

**Security/Governance Integration:**
- Canvas disabled by default; requires explicit policy enablement
- HTML content sanitized with DOMPurify before rendering
- iframe sandbox attribute restricts: no form submission, no top navigation, no same-origin access
- Canvas content in audit trail (hash of rendered content)
- WebSocket connection authenticated via existing session token

**Dependencies:** Next.js 14 (existing dash). DOMPurify for sanitization. WebSocket (existing infrastructure).

**Testable Acceptance Criteria:**
1. Agent pushes HTML → renders in dashboard canvas area
2. iframe sandbox prevents parent DOM access (CSP violation → blocked)
3. Canvas disabled by default; enabling requires `canvas: enabled` in policy
4. WebSocket reconnects on drop within 5s

---

### GAP-08: Plugin System → REQ-MARKET-02

**Proposed Module:** `orchestrator/plugins.py` (new)

**Architecture:**
```
extensions/
    ├── my-plugin/
    │   ├── manifest.json   ← Name, version, API version, capabilities
    │   ├── index.py        ← Python plugin entry
    │   └── index.ts        ← TypeScript plugin entry (Node.js sidecar)
    └── ...

plugins.py:
    ├── Discovery: scan extensions/ directory
    ├── Validation: manifest schema + capability check
    ├── Loading: subprocess isolation (crash boundary)
    ├── API: versioned plugin API (v1, v2, ...)
    └── Hot-reload: watch + reload in dev mode
```

**Security/Governance Integration:**
- Plugin manifest validated against schema (name, version, capabilities, API version)
- Plugin runs in subprocess — crash does not crash host process
- Plugin API versioned; deprecated versions logged
- Plugin tool calls routed through policy gate (same as built-in tools)
- Plugin capability declaration enforced (same as skill capabilities)
- Plugin load/unload events in audit trail

**Dependencies:** Python subprocess/multiprocessing for isolation. Node.js child_process for TS plugins.

**Testable Acceptance Criteria:**
1. Plugin placed in `extensions/` auto-discovered and loaded
2. Plugin crash → error logged, host process continues
3. Plugin calling tool outside declared capabilities → blocked
4. Plugin API version mismatch → load rejected with clear error
5. Plugin load/unload events visible in audit trail

---

### GAP-09: SSE Streaming → REQ-SDK-01

**Proposed Module:** `sdk/python/client.py`, `sdk/typescript/src/client.ts` (existing, extended)

**Architecture:**
```
API → SSE endpoint (/api/v1/pipeline/stream) → typed events
    │
    ├── PipelineStarted { task_id, agent, timestamp }
    ├── StageEntered { stage: plan|gate|execute|validate|ship }
    ├── TokenDelta { content: string, role: string }
    ├── ToolCall { name, args, status }
    ├── PipelineCompleted { result, audit_hash }
    └── PipelineError { error, stage }
```

**Security/Governance Integration:**
- SSE connection authenticated via existing JWT/API key
- Token deltas respect output sanitization guard (PII redacted in real-time)
- SSE events include audit hash for stream integrity verification
- Connection drops trigger auto-reconnect with resume token

**Dependencies:** FastAPI StreamingResponse (existing). httpx-sse for Python client. EventSource for TypeScript client.

**Testable Acceptance Criteria:**
1. Python `client.stream_pipeline()` yields typed event objects
2. TypeScript `client.streamPipeline()` returns AsyncIterator
3. Auto-reconnect on connection drop within 3s
4. PII content redacted in TokenDelta events
5. Stream integrity verifiable via audit hash chain

---

### GAP-10: Native MCP Client → REQ-MCP-01 through REQ-MCP-04

**Proposed Module:** `adapters/mcp_client.py`, `config/mcp_registry.py`, `api/routes/mcp.py` (new)

**Architecture:**
```
mcp_client.py:
    @modelcontextprotocol/sdk → tool discovery → scope check → policy gate → execute
    │
    ├── Registry: config/mcp_registry.py (private-first, mirror capability)
    ├── Consent: api/routes/mcp.py (scope-based, per-org)
    ├── Governance: security/supply_chain.py (scan, version pin, health monitor)
    └── Enforcement: adapters/mcp_client.py (runtime scope check)
```

**Security/Governance Integration:**
- MCP servers treated as governed dependencies (same as skills)
- Supply-chain scanned at install; version pinned in `mcp.lock`
- Scope-based consent: each MCP server connection requires explicit scope approval
- Runtime scope enforcement: tool call outside declared scope → blocked
- Health monitoring: 60s interval; unhealthy server marked, failover triggered
- All MCP tool calls pass through VAP policy gate
- All MCP interactions in SHA-256 audit chain

**Dependencies:** @modelcontextprotocol/sdk (Node.js — sidecar or Python port). Existing policy engine. Existing supply chain scanner.

**Testable Acceptance Criteria:**
1. MCP server connects and tools auto-discovered
2. Connection without scope consent → blocked
3. Tool call outside declared scope → blocked + audit entry
4. MCP server health check every 60s; unhealthy → marked
5. All MCP tool calls visible in audit trail
6. `mcp.lock` enforces version pinning
7. MCP server install triggers supply-chain scan

---

### GAP-11: Security Audit CLI → REQ-SEC-02

**Proposed Module:** `cli/security_audit.py` (new)

**Architecture:**
```
occp security audit [--deep] [--fix]
    │
    ├── Config checks: JWT secret strength, CORS origins, admin passwords
    ├── TLS checks: cert validity, protocol version, cipher suites
    ├── Sandbox checks: nsjail available, capabilities dropped
    ├── Policy checks: default-deny, guard activation, break-glass config
    ├── Dependency checks: known CVEs, outdated packages
    ├── --deep: endpoint probing, injection testing
    └── --fix: auto-remediate safe issues (weak JWT → regenerate)
```

**Security/Governance Integration:**
- Audit results in structured JSON (machine-parseable)
- Critical findings → exit code 1 (CI integration)
- `--fix` actions create audit trail entries
- Deep mode requires `system_admin` role

**Dependencies:** Existing security modules. requests for endpoint probing. cryptography for cert validation.

**Testable Acceptance Criteria:**
1. `occp security audit` checks ≥15 items
2. Weak JWT secret → CRITICAL finding
3. `--deep` probes API endpoints for injection
4. `--fix` regenerates weak JWT secret automatically
5. Exit code 1 if any CRITICAL finding
6. JSON output parseable by SIEM

---

### GAP-13: Webhook Receiver → REQ-AUTO-02

**Proposed Module:** `api/routes/webhooks.py` (new)

**Architecture:**
```
POST /api/v1/webhooks/{hook_id}
    │
    ├── HMAC-SHA256 signature verification
    ├── Schema validation (per-hook configurable)
    ├── Routing to target agent/workflow
    └── Retry on processing failure (3x, exponential backoff)
```

**Security/Governance Integration:**
- HMAC-SHA256 verification mandatory; invalid signature → 403
- Webhook secrets stored in credential vault (REQ-SEC-03)
- Webhook payload passes through VAP pipeline as inbound task
- Replay attack prevention via nonce/timestamp check
- All webhook receipts in audit trail

**Dependencies:** Existing FastAPI. HMAC (stdlib). Existing VAP pipeline.

**Testable Acceptance Criteria:**
1. Valid HMAC-SHA256 signature → accepted, routed to agent
2. Invalid signature → 403, audit entry
3. Missing/expired timestamp → rejected (replay prevention)
4. Processing failure → retry 3x with exponential backoff
5. Webhook receipt visible in audit trail

---

### GAP-14: Event Triggers → REQ-AUTO-03

**Proposed Module:** `orchestrator/triggers.py` (new)

**Architecture:**
```
triggers.yaml:
    - name: high-error-rate
      on: audit.event
      condition: "error_count > 10 AND window = 5m"
      action: run_agent(alerter)

triggers.py:
    Event bus subscription → condition evaluation → agent trigger
```

**Security/Governance Integration:**
- Trigger definitions in version-controlled YAML
- Trigger evaluation is non-blocking (async event bus)
- Triggered agent execution enters full VAP pipeline
- Trigger fire events in audit trail
- Condition evaluation uses safe expression parser (no eval())

**Dependencies:** Existing audit event stream. Safe expression parser (simpleeval or similar).

**Testable Acceptance Criteria:**
1. Trigger fires within 500ms of matching event
2. Definitions loaded from version-controlled YAML
3. Triggered agent enters full VAP pipeline
4. Trigger fire event in audit trail
5. Malicious expression (code injection via trigger condition) → rejected by safe parser

---

### GAP-16: Session Management → REQ-CORE-02

**Proposed Module:** `orchestrator/sessions.py` (new)

**Architecture:**
```
Session types:
    ├── main    ← Full tool access, admin operations
    ├── dm      ← Scoped tools, personal context
    └── group   ← Shared context, restricted tools

sessions.py:
    Session factory → type detection → tool scoping → context isolation
```

**Security/Governance Integration:**
- Session type determines available tools (policy-enforced)
- Group sessions: shared context, but tool access per-user RBAC
- DM sessions: isolated state, invisible to other DMs
- Session creation/destruction in audit trail
- Session type cannot be escalated mid-session

**Dependencies:** Existing RBAC. Existing session infrastructure.

**Testable Acceptance Criteria:**
1. Group session cannot invoke main-only tools (e.g., `shell_exec`)
2. DM state invisible to other DM sessions
3. Session type determined at creation, immutable
4. Tool access filtered per session type + user RBAC
5. All session lifecycle events in audit trail

---

### GAP-12 & GAP-15: Integration Plan Skip Reasons

| GAP-ID | Short Name | Skip Reason |
|--------|-----------|-------------|
| GAP-12 | Discord Adapter | Subsumed by GAP-01 (Messaging Adapters). Discord is one of 4 channel adapters (REQ-CHAN-05) built under the same `adapters/channels/` architecture. All GAP-01 governance requirements (policy gate, VAP, crypto audit, SBOM, sandbox, kill-switch) apply identically. No separate integration plan needed. |
| GAP-15 | Local Model Support (Ollama) | Maps to REQ-CORE-04. Implementation is a single adapter module (`adapters/ollama_planner.py`) extending existing `BasePlanner` Protocol. OllamaPlanner already exists as stub in v0.8.2. Governance: inherits all planner governance (VAP, policy gate, audit trail) from existing `orchestrator/pipeline.py`. Low complexity, low security impact, no new attack surface. No dedicated integration plan warranted. |

---

## B3: Priority Matrix

| GAP-ID | Short Name | Priority | Complexity | Security Impact | Phase | Rationale |
|--------|-----------|----------|-----------|-----------------|-------|-----------|
| GAP-01 | Messaging Adapters | **P0** | High | Medium | 4 | Primary adoption blocker. Users expect messaging integration. |
| GAP-05 | Cron & Scheduling | **P0** | Medium | High | 5 | Enterprise #1 request. Unattended execution is highest-risk. |
| GAP-10 | Native MCP Client | **P0** | High | High | 7 | MCP is the industry standard for tool integration. Without it, OCCP is isolated. |
| GAP-02 | Memory System | **P0** | High | Medium | 3 | Agents without memory have limited utility. Core capability. |
| GAP-03 | Skill Marketplace | **P1** | High | High | 2, 8 | Ecosystem growth driver. Supply-chain security critical. |
| GAP-08 | Plugin System | **P1** | High | High | 8 | Extensibility without core changes. Crash isolation essential. |
| GAP-13 | Webhook Receiver | **P1** | Medium | Medium | 5 | Event-driven architecture. Enables external integrations. |
| GAP-06 | Browser Automation | **P1** | Medium | High | 7 | Common agent use case. Sandbox escape risk demands careful implementation. |
| GAP-11 | Security Audit CLI | **P1** | Low | High | 1 | Low effort, high security value. Should ship early. |
| GAP-04 | Config-First Agents | **P1** | Medium | Low | 1 | Lowers barrier to agent creation. Enables non-developer adoption. |
| GAP-09 | SSE Streaming | **P1** | Medium | Low | 8 | UX improvement for long-running tasks. Both SDKs. |
| GAP-16 | Session Management | **P2** | Medium | Medium | 1 | Scoped tools per session type. Important for multi-channel. |
| GAP-07 | Agent Canvas | **P2** | Low | Low | 4 | Nice-to-have. Rich output beyond text. |
| GAP-14 | Event Triggers | **P2** | Medium | Low | 5 | Reactive automation. Lower priority than cron. |
| GAP-12 | Discord Adapter | **P2** | Low | Low | 4 | Community channel. Lower priority than WhatsApp/Slack/Telegram. |
| GAP-15 | Local Model Support | **P2** | Low | Low | 1 | Development convenience. Not production requirement. |

### Priority Legend

| Priority | Definition | Timeline |
|----------|-----------|----------|
| **P0** | Must-have for v1.0 viability. Without these, OCCP cannot compete. | Phases 1-7 |
| **P1** | Should-have for v1.0 completeness. Significant value-add. | Phases 1-8 |
| **P2** | Nice-to-have. Can defer to v1.1 if schedule pressure. | Phases 1-8 (deprioritize if needed) |

### Complexity Legend

| Complexity | Effort | New Modules | Risk |
|-----------|--------|-------------|------|
| **High** | 2-3 weeks | 3+ new modules | New infrastructure, external dependencies |
| **Medium** | 1-2 weeks | 1-2 new modules | Extends existing patterns |
| **Low** | <1 week | 1 module or extension | Well-understood patterns |

### Security Impact Legend

| Impact | Meaning |
|--------|---------|
| **High** | Introduces new attack surface or handles untrusted input. Requires dedicated security review. |
| **Medium** | Extends existing security boundaries. Standard policy gate integration sufficient. |
| **Low** | Minimal new attack surface. Read-only or config-only changes. |

---

## Integration Dependency Graph

```
Phase 1: Governance Core ─────────────────────────────────────────────┐
    ├── REQ-GOV-01..04, GOV-06 (VAP hardening, trust levels)         │
    ├── REQ-POL-01..03 (ABAC, audit, testing)                        │
    ├── REQ-SEC-01..04 (ML classifier, audit CLI, vault, throttle)   │
    └── REQ-CORE-01..04 (pipeline, sessions, config-first, Ollama)   │
                                                                      │
Phase 2: Provenance ──────────────────────────────────────────────────┤
    ├── REQ-CPC-01..04 (SLSA, signing, verification, revocation)     │
    ├── REQ-TSF-01..05 (registry, capabilities, SBOM, pinning, scan) │
    └── REQ-SEC-06 (Merkle root audit verification)                   │
                                                                      │
Phase 3: Memory (depends on store/) ──────────────────────────────────┤
    └── REQ-MEM-01..03 (hybrid, compaction, knowledge)               │
                                                                      │
Phase 4: Channels (depends on Phase 1 pipeline) ─────────────────────┤
    ├── REQ-CHAN-01..05 (protocol, WA, TG, Slack, Discord)           │
    └── REQ-A2UI-01 (canvas)                                         │
                                                                      │
Phase 5: Scheduler (depends on Phase 1 VAP) ─────────────────────────┤
    ├── REQ-VSTA-01..04 (VAP-enforced, profiles, budget, timeout)    │
    ├── REQ-AUTO-01..03 (cron, webhooks, triggers)                    │
    └── REQ-SEC-05 (cost anomaly detection)                           │
                                                                      │
Phase 6: Multi-Agent (depends on Phase 1 sandbox) ───────────────────┤
    └── REQ-MAO-01..05 (isolation, recursion, cascade, merge, proof) │
                                                                      │
Phase 7: Browser+MCP (depends on Phase 2 signing) ───────────────────┤
    ├── REQ-CBDB-01..05 (browser isolation, policy, audit)           │
    └── REQ-MCP-01..04 (registry, consent, governance, enforcement)  │
                                                                      │
Phase 8: Marketplace (depends on Phase 2 supply-chain) ──────────────┤
    ├── REQ-MARKET-01..02 (OCCPHub, plugins)                         │
    ├── REQ-SDK-01..02 (SSE, MCP server)                             │
    └── REQ-COMP-02 (SIEM)                                           │
                                                                      │
Phase 9: Multi-Tenant (depends on Phase 1 RBAC) ─────────────────────┤
    ├── REQ-MULTI-01..02 (isolation, residency)                      │
    └── REQ-COMP-01 (compliance dashboard)                           │
                                                                      │
Phase 10: Red-Team (validates all phases) ────────────────────────────┘
    └── REQ-RT-01..05 (injection, poisoning, exfil, agency, scoreboard)
```

---

## Supply Chain Risk Assessment

| Component | Source | License | Risk | Mitigation |
|-----------|--------|---------|------|------------|
| Baileys (WhatsApp) | github.com/WhiskeySockets/Baileys | MIT | **High** — Unofficial API, Meta may block | Abstract behind ChannelAdapter; swap-ready |
| grammY (Telegram) | github.com/grammyjs/grammY | MIT | **Low** — Official Bot API | Stable, well-maintained |
| discord.js | github.com/discordjs/discord.js | Apache-2.0 | **Low** — Official SDK | Stable, active maintenance |
| Slack Bolt | github.com/slackapi/bolt-python | MIT | **Low** — Official SDK | Python native, no sidecar |
| Playwright | github.com/microsoft/playwright | Apache-2.0 | **Low** — Microsoft maintained | Well-tested, sandboxable |
| ChromaDB | github.com/chroma-core/chroma | Apache-2.0 | **Medium** — Rapidly evolving API | Pin version; abstraction layer |
| APScheduler | github.com/agronholm/apscheduler | MIT | **Low** — Mature, stable | Well-understood patterns |
| Sigstore/cosign | github.com/sigstore/cosign | Apache-2.0 | **Low** — Linux Foundation project | Industry standard |
| MCP SDK | github.com/modelcontextprotocol/sdk | MIT | **Medium** — Protocol evolving | Pin version; adapter layer |
| OpenClaw skills (if imported) | ClawHub | Various | **High** — No capability declaration, no signing | Require wrapper + scan + capability generation |

---

## Key Insight: Competitive Positioning

```
                    ┌──────────────────────────────────┐
                    │        Enterprise Grade           │
                    │                                   │
                    │   OCCP v1.0 TARGET ★              │
                    │   (Control Plane + Runtime)       │
                    │                                   │
    Governance ◄────┤───────────────────────────────────┤───► Runtime
    (Security,      │                                   │     (Features,
     Audit,         │   OCCP v0.8.2                     │      Integrations,
     Compliance)    │   (Control Plane only)            │      Ecosystem)
                    │                                   │
                    │                    OpenClaw        │
                    │                    (Runtime only)  │
                    │                                   │
                    └──────────────────────────────────┘
                                Consumer Grade
```

OCCP v1.0 occupies the **upper-right quadrant**: enterprise-grade governance WITH full runtime capabilities. No competitor currently occupies this space.

---

## Capability Matrix: OCCP vs OpenClaw

Head-to-head feature comparison across 50 capabilities in 10 categories.

**Legend:** ✅ Production-ready | ⚠ Partial/Stub | ❌ Missing | N/A Not applicable

### 1. Governance & Policy (10 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 1 | Non-bypassable execution pipeline | ✅ VAP 5-stage | ❌ | ✅ Hardened VAP |
| 2 | Role-based access control | ✅ Casbin 4-role | ❌ Single-user | ✅ ABAC+RBAC hybrid |
| 3 | Policy-as-code engine | ❌ | ❌ | ✅ REQ-GOV-02 |
| 4 | Break-glass protocol | ❌ | ❌ | ✅ REQ-GOV-04 |
| 5 | Trust level enforcement | ❌ | ❌ | ✅ REQ-GOV-06 L0-L5 |
| 6 | Policy testing framework | ❌ | ❌ | ✅ REQ-POL-03 |
| 7 | Policy decision audit | ⚠ Implicit via audit | ❌ | ✅ REQ-POL-02 |
| 8 | Agent boundary enforcement | ❌ | ❌ | ✅ REQ-GOV-05 |
| 9 | Human oversight controls | ✅ Guard-based | ❌ | ✅ Enhanced |
| 10 | Testable policy definitions | ❌ | ❌ | ✅ REQ-POL-03 |

**Score: OCCP v0.8.2 = 3/10 | OpenClaw = 0/10 | OCCP v1.0 = 10/10**

### 2. Security (8 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 11 | Tamper-evident audit trail | ✅ SHA-256 chain | ❌ | ✅ + Merkle root |
| 12 | At-rest encryption | ✅ AES-256-GCM | ❌ | ✅ |
| 13 | Sandbox execution | ✅ nsjail/bwrap | ⚠ Process only | ✅ Enhanced |
| 14 | ML injection detection | ❌ | ❌ | ✅ REQ-SEC-01 |
| 15 | Security audit CLI | ❌ | ⚠ Basic | ✅ REQ-SEC-02 |
| 16 | Credential vault | ❌ | ❌ | ✅ REQ-SEC-03 |
| 17 | Adaptive rate throttling | ❌ | ❌ | ✅ REQ-SEC-04 |
| 18 | Supply chain scanner | ✅ Typosquatting | ❌ | ✅ + SLSA |

**Score: OCCP v0.8.2 = 4/8 | OpenClaw = 1/8 | OCCP v1.0 = 8/8**

### 3. Runtime & Pipeline (5 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 19 | Message pipeline | ⚠ API-only | ✅ Multi-channel | ✅ REQ-CORE-01 |
| 20 | Session management | ⚠ Single type | ✅ Main/DM/group | ✅ REQ-CORE-02 |
| 21 | Config-first agent definition | ❌ | ✅ AGENTS.md | ✅ REQ-CORE-03 |
| 22 | Local model support (Ollama) | ⚠ Stub | ✅ Full | ✅ REQ-CORE-04 |
| 23 | Multi-LLM failover | ✅ Circuit breaker | ⚠ Simple fallback | ✅ Enhanced |

**Score: OCCP v0.8.2 = 2/5 | OpenClaw = 4/5 | OCCP v1.0 = 5/5**

### 4. Channels & Messaging (6 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 24 | Channel adapter protocol | ❌ | ✅ 12+ adapters | ✅ REQ-CHAN-01 |
| 25 | WhatsApp adapter | ❌ | ✅ Baileys | ✅ REQ-CHAN-02 |
| 26 | Telegram adapter | ❌ | ✅ grammY | ✅ REQ-CHAN-03 |
| 27 | Slack adapter | ❌ | ✅ Bolt | ✅ REQ-CHAN-04 |
| 28 | Discord adapter | ❌ | ✅ discord.js | ✅ REQ-CHAN-05 |
| 29 | Agent Canvas (A2UI) | ❌ | ✅ Interactive | ✅ REQ-A2UI-01 |

**Score: OCCP v0.8.2 = 0/6 | OpenClaw = 6/6 | OCCP v1.0 = 6/6**

### 5. Memory & Knowledge (3 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 30 | Hybrid memory retrieval | ❌ | ✅ Vector+BM25 | ✅ REQ-MEM-01 |
| 31 | Memory compaction | ❌ | ✅ Daily | ✅ REQ-MEM-02 |
| 32 | Cross-session knowledge | ❌ | ✅ Persistent | ✅ REQ-MEM-03 |

**Score: OCCP v0.8.2 = 0/3 | OpenClaw = 3/3 | OCCP v1.0 = 3/3**

### 6. Automation & Scheduling (5 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 33 | Cron scheduler | ❌ | ✅ Built-in | ✅ REQ-AUTO-01 |
| 34 | Webhook receiver | ❌ | ✅ HMAC-verified | ✅ REQ-AUTO-02 |
| 35 | Event triggers | ❌ | ⚠ Basic | ✅ REQ-AUTO-03 |
| 36 | Budget guard | ❌ | ❌ | ✅ REQ-VSTA-03 |
| 37 | Cost anomaly detection | ❌ | ❌ | ✅ REQ-SEC-05 |

**Score: OCCP v0.8.2 = 0/5 | OpenClaw = 2/5 | OCCP v1.0 = 5/5**

### 7. Multi-Agent (5 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 38 | Worker sandbox isolation | ❌ | ❌ | ✅ REQ-MAO-01 |
| 39 | Recursion depth control | ❌ | ❌ | ✅ REQ-MAO-02 |
| 40 | Cascade stop | ❌ | ❌ | ✅ REQ-MAO-03 |
| 41 | Deterministic merge contract | ❌ | ❌ | ✅ REQ-MAO-04 |
| 42 | Proof-carrying outputs | ❌ | ❌ | ✅ REQ-MAO-05 |

**Score: OCCP v0.8.2 = 0/5 | OpenClaw = 0/5 | OCCP v1.0 = 5/5**

### 8. Browser & MCP (5 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 43 | Browser automation | ❌ | ✅ Playwright | ✅ REQ-CBDB-01..05 |
| 44 | Native MCP client | ❌ | ✅ SDK v1.25 | ✅ REQ-MCP-01..04 |
| 45 | Domain allow/deny policy | ❌ | ❌ | ✅ REQ-CBDB-02 |
| 46 | Form submission approval | ❌ | ❌ | ✅ REQ-CBDB-03 |
| 47 | MCP scope enforcement | ❌ | ❌ | ✅ REQ-MCP-04 |

**Score: OCCP v0.8.2 = 0/5 | OpenClaw = 2/5 | OCCP v1.0 = 5/5**

### 9. Marketplace & Ecosystem (4 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 48 | Skill/plugin marketplace | ❌ | ✅ ClawHub 5705+ | ✅ REQ-MARKET-01 |
| 49 | Plugin system | ❌ | ✅ Hot-loading | ✅ REQ-MARKET-02 |
| 50 | SSE streaming | ❌ | ✅ Standard SSE | ✅ REQ-SDK-01 |
| 51 | OCCP as MCP server | ❌ | ❌ | ✅ REQ-SDK-02 |

**Score: OCCP v0.8.2 = 0/4 | OpenClaw = 3/4 | OCCP v1.0 = 4/4**

### 10. Enterprise & Compliance (4 features)

| # | Capability | OCCP v0.8.2 | OpenClaw | OCCP v1.0 Target |
|---|-----------|:-----------:|:--------:|:-----------------:|
| 52 | Org-scoped data isolation | ❌ | ❌ | ✅ REQ-MULTI-01 |
| 53 | Data residency controls | ❌ | ❌ | ✅ REQ-MULTI-02 |
| 54 | Compliance dashboard | ❌ | ❌ | ✅ REQ-COMP-01 |
| 55 | SIEM/SOAR integration | ❌ | ❌ | ✅ REQ-COMP-02 |

**Score: OCCP v0.8.2 = 0/4 | OpenClaw = 0/4 | OCCP v1.0 = 4/4**

### Capability Score Summary

| Category | OCCP v0.8.2 | OpenClaw | OCCP v1.0 | Gap to Close |
|----------|:-----------:|:--------:|:---------:|:------------:|
| 1. Governance & Policy | 3/10 (30%) | 0/10 (0%) | 10/10 | +7 |
| 2. Security | 4/8 (50%) | 1/8 (13%) | 8/8 | +4 |
| 3. Runtime & Pipeline | 2/5 (40%) | 4/5 (80%) | 5/5 | +3 |
| 4. Channels & Messaging | 0/6 (0%) | 6/6 (100%) | 6/6 | +6 |
| 5. Memory & Knowledge | 0/3 (0%) | 3/3 (100%) | 3/3 | +3 |
| 6. Automation & Scheduling | 0/5 (0%) | 2/5 (40%) | 5/5 | +5 |
| 7. Multi-Agent | 0/5 (0%) | 0/5 (0%) | 5/5 | +5 |
| 8. Browser & MCP | 0/5 (0%) | 2/5 (40%) | 5/5 | +5 |
| 9. Marketplace & Ecosystem | 0/4 (0%) | 3/4 (75%) | 4/4 | +4 |
| 10. Enterprise & Compliance | 0/4 (0%) | 0/4 (0%) | 4/4 | +4 |
| **TOTAL** | **9/55 (16%)** | **21/55 (38%)** | **55/55 (100%)** | **+46** |

### Strategic Interpretation

| Quadrant | OCCP v0.8.2 Leads | OpenClaw Leads | Neither Has |
|----------|:-----------------:|:--------------:|:-----------:|
| Governance (Cat 1, 7, 10) | **3** features | 0 features | **16** features |
| Runtime (Cat 3, 4, 5) | **2** features | **13** features | 0 features |
| Security (Cat 2) | **4** features | **1** feature | 3 features |
| Automation (Cat 6, 8, 9) | 0 features | **7** features | 7 features |

**Key takeaways:**
1. **OCCP owns Governance** — 3/10 features already, OpenClaw has 0. This is the durable moat.
2. **OpenClaw owns Runtime** — 13 features vs OCCP's 2. Channels, Memory, Config-first are the biggest gaps.
3. **Neither owns Multi-Agent or Enterprise** — Both at 0. First-mover advantage for OCCP v1.0.
4. **OCCP v1.0 achieves 100%** — All 55 capabilities addressed across 10 phases.

---

## B4: Mandatory Governance Compliance Matrix

Every module integration MUST satisfy all 6 governance requirements. This matrix audits each integration plan.

### Compliance Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Explicitly addressed in integration plan |
| ⚠️ | Implicitly covered but needs explicit statement |
| ❌ | Not addressed — governance gap |

### Matrix

| GAP-ID | Module | Policy Gate | VAP Lifecycle | Crypto Audit | SBOM+Sign | Sandbox | Kill-Switch |
|--------|--------|:-----------:|:-------------:|:------------:|:---------:|:-------:|:-----------:|
| GAP-01 | Messaging Adapters | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| GAP-02 | Memory System | ✅ | ⚠️ | ✅ | ❌ | ✅ | ❌ |
| GAP-03 | Skill Marketplace | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| GAP-04 | Config-First Agents | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| GAP-05 | Cron & Scheduling | ✅ | ✅ | ✅ | ❌ | ⚠️ | ✅ |
| GAP-06 | Browser Automation | ✅ | ⚠️ | ✅ | ❌ | ✅ | ✅ |
| GAP-07 | Agent Canvas | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| GAP-08 | Plugin System | ✅ | ⚠️ | ✅ | ❌ | ✅ | ❌ |
| GAP-09 | SSE Streaming | ✅ | ✅ | ✅ | ❌ | N/A | ❌ |
| GAP-10 | MCP Client | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| GAP-11 | Security Audit CLI | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| GAP-13 | Webhook Receiver | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| GAP-14 | Event Triggers | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| GAP-16 | Session Management | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |

### Coverage Summary

| Requirement | Covered | Implicit | Missing | Coverage |
|------------|---------|----------|---------|----------|
| Policy Gate | 13 | 0 | 0 | **100%** |
| VAP Lifecycle | 6 | 4 | 3 | **46%** |
| Crypto Audit Trail | 13 | 0 | 0 | **100%** |
| SBOM + Signing | 2 | 0 | 11 | **15%** |
| Sandbox Isolation | 7 | 2 | 4 | **54%** |
| Kill-Switch | 4 | 0 | 9 | **31%** |

### Governance Remediation Per Module

The following specifies the exact governance additions required for each integration plan to achieve 6/6 compliance.

---

#### GAP-01 Remediation (Messaging Adapters)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| SBOM+Sign | ❌ | Node.js sidecar dependencies (Baileys, grammY, discord.js) tracked in CycloneDX SBOM. Sidecar binaries signed with cosign. Runtime signature verification on sidecar startup. |
| Sandbox | ❌ | Node.js sidecars run in dedicated containers with `no-new-privileges`, `read_only` rootfs, network restricted to internal bridge only. No host filesystem mount. |
| Kill-Switch | ❌ | Admin API endpoint `POST /api/v1/adapters/{channel}/kill` force-disconnects adapter. Emergency halt flag in policy config disables all adapters. Adapter crash triggers circuit breaker (3 failures in 60s → auto-disable). |

---

#### GAP-02 Remediation (Memory System)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ⚠️ | Memory write operations that modify shared knowledge base enter VAP gate (prevents unauthorized knowledge injection). Read operations exempt (performance). |
| SBOM+Sign | ❌ | ChromaDB/Qdrant version pinned in `requirements.txt` and tracked in project SBOM. Embedding model checksums verified at load time. |
| Kill-Switch | ❌ | Memory service pause endpoint `POST /api/v1/memory/pause` halts all writes (reads continue from cache). Emergency purge for compromised memory segments with audit trail. |

---

#### GAP-03 Remediation (Skill Marketplace)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ⚠️ | Skill execution enters VAP pipeline explicitly — skill tool calls processed as `Execute` stage with full gate evaluation. Skill publish enters VAP with `source=skill_publish`. |

---

#### GAP-04 Remediation (Config-First Agents)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ❌ | Agent registration triggers VAP gate: config validated → policy gate evaluates permissions → register → audit entry. Config hot-reload triggers re-evaluation through gate. |
| SBOM+Sign | ❌ | Agent config files (AGENT.md, TOOLS.md) signed with cosign. Config loader verifies signatures before loading. Unsigned configs rejected in production. |
| Sandbox | ❌ | Config loader runs with read-only filesystem access to `agents/` directory. Watchdog process isolated from main API process. |
| Kill-Switch | ❌ | `POST /api/v1/agents/{id}/disable` immediately deregisters agent and blocks all pending tasks. Admin emergency flag disables all config-loaded agents. |

---

#### GAP-05 Remediation (Cron & Scheduling)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| SBOM+Sign | ❌ | APScheduler version pinned in project SBOM. Cron job definitions signed — runtime verifies definition hash before execution. Tampered definitions rejected. |
| Sandbox | ⚠️ | Each cron job execution runs in sandbox (inherits sandbox from VAP Execute stage). Job process isolated from scheduler process (crash boundary). |

---

#### GAP-06 Remediation (Browser Automation)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ⚠️ | Each browser action (navigate, click, form submit, download) enters VAP micro-gate: action → policy check → execute → audit. Batch actions processed sequentially through gate. |
| SBOM+Sign | ❌ | Playwright version pinned in project SBOM. Browser binary checksums verified at download. Playwright update triggers SBOM regeneration. |

---

#### GAP-07 Remediation (Agent Canvas)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ❌ | Canvas content push enters VAP gate: content sanitized (DOMPurify) → policy gate evaluates content classification → render → audit entry with content hash. |
| SBOM+Sign | ❌ | DOMPurify version pinned in `package.json` and tracked in dashboard SBOM. Canvas HTML templates (if any) signed. |
| Kill-Switch | ❌ | `POST /api/v1/canvas/disable` immediately disables all canvas rendering. Canvas content cleared from active sessions. Policy flag `canvas: disabled` enforced globally. |

---

#### GAP-08 Remediation (Plugin System)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ⚠️ | Plugin tool calls enter full VAP pipeline (not just policy gate). Plugin-initiated actions processed as `Execute` stage with gate evaluation per tool call. |
| SBOM+Sign | ❌ | Plugin `manifest.json` signed with cosign. Runtime verifies manifest signature before loading. Plugin dependencies tracked in per-plugin SBOM (CycloneDX). Unsigned plugins rejected in production. |
| Kill-Switch | ❌ | `POST /api/v1/plugins/{id}/kill` sends SIGTERM to plugin subprocess → 5s grace → SIGKILL. Admin emergency flag kills all plugin subprocesses. Plugin restart requires explicit re-enable. |

---

#### GAP-09 Remediation (SSE Streaming)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| SBOM+Sign | ❌ | httpx-sse (Python) and EventSource polyfill (TypeScript) version pinned in respective SBOM. SSE event schema signed (stream integrity already uses audit hash — extend to schema signature). |
| Kill-Switch | ❌ | Server-side stream abort: `POST /api/v1/pipeline/{task_id}/abort` terminates stream and sends `PipelineAborted` event. Client receives abort signal and closes connection. Admin can abort all active streams. |

---

#### GAP-10 Remediation (MCP Client)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| Sandbox | ⚠️ | MCP server processes run in dedicated containers (same isolation as adapter sidecars). MCP tool execution inherits VAP sandbox context. No direct host filesystem access from MCP servers. |

---

#### GAP-11 Remediation (Security Audit CLI)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ❌ | `--fix` remediation actions enter VAP pipeline (config change is a privileged action). `--deep` endpoint probing enters VAP gate with `source=security_audit`. Read-only audit exempt from VAP. |
| SBOM+Sign | ❌ | Audit CLI dependencies tracked in project SBOM. Audit report signed with cosign for integrity verification. Signed reports required for compliance evidence. |
| Sandbox | ❌ | `--deep` endpoint probing runs in sandboxed network namespace (prevents audit tool from accessing unintended services). Probe targets restricted to configured endpoints only. |
| Kill-Switch | ❌ | `--deep` probing has configurable timeout (default 30s). Admin can terminate running audit via `occp security audit --abort`. Abort creates audit entry. |

---

#### GAP-13 Remediation (Webhook Receiver)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| SBOM+Sign | ❌ | Webhook endpoint dependencies tracked in project SBOM. Webhook configuration files signed — prevents unauthorized webhook registration. |
| Sandbox | ❌ | Webhook payload processing runs in sandbox context (inherits from VAP Execute stage). Payload size limit enforced (default 1MB). Binary payloads rejected by default. |
| Kill-Switch | ❌ | `POST /api/v1/webhooks/{hook_id}/disable` disables specific webhook. Admin emergency flag `webhooks: disabled` halts all webhook processing. Queued payloads preserved but not processed until re-enabled. |

---

#### GAP-14 Remediation (Event Triggers)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| SBOM+Sign | ❌ | Trigger definition files (`triggers.yaml`) signed with cosign. Runtime verifies signature before loading trigger rules. simpleeval dependency version pinned in SBOM. |
| Kill-Switch | ❌ | `POST /api/v1/triggers/{name}/disable` disables specific trigger. Admin emergency flag `triggers: disabled` halts all trigger evaluation. Trigger disable event in audit trail. |

---

#### GAP-16 Remediation (Session Management)

| Requirement | Current | Required Addition |
|------------|---------|-------------------|
| VAP Lifecycle | ❌ | Session creation enters VAP gate: session type + user identity → policy evaluation → session created with scoped permissions. Session type escalation attempt enters gate and is rejected. |
| SBOM+Sign | ❌ | Session management dependencies tracked in project SBOM. Session tokens signed with HMAC-SHA256 (existing JWT infrastructure). |
| Kill-Switch | ❌ | `POST /api/v1/sessions/{id}/terminate` force-terminates session and cleans up all associated state. Admin emergency flag terminates all active sessions. Terminated sessions cannot be resumed. |

---

### Post-Remediation Compliance

After applying all remediations above, the compliance matrix becomes:

| GAP-ID | Module | Policy Gate | VAP Lifecycle | Crypto Audit | SBOM+Sign | Sandbox | Kill-Switch |
|--------|--------|:-----------:|:-------------:|:------------:|:---------:|:-------:|:-----------:|
| GAP-01 | Messaging Adapters | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-02 | Memory System | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-03 | Skill Marketplace | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-04 | Config-First Agents | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-05 | Cron & Scheduling | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-06 | Browser Automation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-07 | Agent Canvas | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-08 | Plugin System | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-09 | SSE Streaming | ✅ | ✅ | ✅ | ✅ | N/A | ✅ |
| GAP-10 | MCP Client | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-11 | Security Audit CLI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-13 | Webhook Receiver | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-14 | Event Triggers | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GAP-16 | Session Management | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Post-remediation coverage: 100% across all 6 governance requirements for all 13 integration plans (GAP-09 Sandbox N/A — transport layer).**
