# OCCP Communication + Control Protocol Evaluation (2026 Q1)

> **Date:** 2026-03-30
> **Evaluator:** Deep Research Agent (Opus 4.6)
> **Status:** COMPLETE
> **Confidence:** CONFIRMED (multi-source cross-verified)

---

## Executive Summary

The proposed OCCP Control Protocol covers **~75% of required orchestration patterns** for a production multi-agent system. The existing codebase already implements key components (VAP pipeline, brain flow engine, DAG orchestrator, confirmation gate, channel adapters) providing a **solid foundation**. However, the protocol has **critical gaps** in: (1) CloudCode integration — no hook mechanism exists, (2) event sourcing for state — current state is in-memory with partial DB persistence, (3) missing event types (DELEGATION, RETRY, HEARTBEAT, TIMEOUT), (4) no A2A-compatible agent card discovery, and (5) incomplete OWASP ASI (Agentic Security) coverage. The approval system (STOP-REQUEST-WAIT) is well-implemented via `ConfirmationGate` but lacks multi-party approval, escalation timeout chains, and cross-channel auth consistency. **Recommendation:** evolve the protocol to v2 with A2A agent cards, event sourcing, Claude Code hooks integration, and OWASP ASI compliance.

---

## 1. Protocol Completeness — SCORE: 7/10

### Current Protocol Assessment

| Pattern | Protocol Coverage | Industry Standard (2026) |
|---------|------------------|--------------------------|
| Sequential pipeline | YES (VAP: Plan->Gate->Execute->Validate->Ship) | Anthropic: composable sequential chains |
| Parallel fan-out/fan-in | YES (multi_agent.py wave execution) | LangGraph: scatter-gather nodes |
| DAG orchestration | YES (topological sort, wave-based) | CrewAI: hierarchical crew, AutoGen: group chat |
| Delegation/escalation | PARTIAL (brain_flow dispatches, no escalation chain) | A2A: capability discovery + task delegation |
| Human-in-the-loop | YES (ConfirmationGate, risk-based auto-approve) | LangGraph: interrupt_before/after nodes |
| Checkpoint/resume | YES (WorkflowExecution checkpoints, DB persistence) | LangGraph: MemorySaver/PostgresSaver per-node |
| Kill-switch | YES (kill_flags per execution) | Industry standard |
| Retry with backoff | PARTIAL (execute_retries, no exponential backoff) | Best practice: jittered exponential |
| Agent discovery | NO | A2A: Agent Cards (JSON, /.well-known/agent.json) |
| Cross-agent messaging | PARTIAL (webhook callback, no pub/sub) | A2A: streaming SSE, AutoGen: async messaging |

**Missing patterns vs. industry standards:**

1. **A2A Agent Cards** — Google A2A protocol (v0.3, Linux Foundation) defines `/.well-known/agent.json` for capability discovery. OCCP has no equivalent; agent registry is hardcoded in `TaskRouter.ROUTING_RULES`. ([Source](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/))

2. **Evaluator-Optimizer Loop** — Anthropic recommends an evaluator agent that scores output and loops back to the executor. OCCP's `QualityGate` + revision loop in `pipeline.py:437-488` partially covers this. ([Source](https://www.anthropic.com/research/building-effective-agents))

3. **Streaming Progress** — A2A supports SSE streaming for long-running tasks. OCCP has `SSEAdapter` in `channel_adapters.py` but it's stub-mode only.

### Sources
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Google A2A Protocol](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [A2A GitHub](https://github.com/a2aproject/A2A)
- [LangGraph 2.0 Production Guide](https://dev.to/richard_dillon_b9c238186e/langgraph-20-the-definitive-guide-to-building-production-grade-ai-agents-in-2026-4j2b)

---

## 2. CloudCode Integration — SCORE: 3/10

### Protocol Gap: No CloudCode Hook System

The protocol specifies "CloudCode (high priority, hooks)" as an input source, but **no implementation exists**.

**Claude Code Hooks (2026 Q1) support 12 event types:**

| Hook Event | Purpose | OCCP Relevance |
|-----------|---------|----------------|
| `PreToolUse` | Gate before tool execution | Security gate, block dangerous ops |
| `PostToolUse` | Validate after tool execution | Audit trail, quality check |
| `Notification` | Agent status updates | Forward to Telegram/dashboard |
| `Stop` | Agent halted | Kill-switch integration |

**Recommended integration approach:**

```
Claude Code Hook (PreToolUse/PostToolUse)
    -> Shell command -> HTTP POST to OCCP API
    -> OCCP Brain processes as high-priority task
    -> Response routed back via exit code / stdout
```

**Transport recommendation:** HTTP webhooks (not WebSocket) for Claude Code hooks because:
- Hooks are fire-and-forget shell commands with JSON stdin
- PreToolUse hooks need synchronous response (exit code 0/2)
- WebSocket adds unnecessary complexity for request-response pattern
- SSE only for dashboard real-time progress streaming

**Current gap:** `adapters/channel_adapters.py` has `WebhookAdapter`, `SSEAdapter`, `WebSocketAdapter` — all in stub mode. No Claude Code hook receiver endpoint exists.

### Sources
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks: 12 Events Guide](https://www.pixelmojo.io/blogs/claude-code-hooks-production-quality-ci-cd-patterns)

---

## 3. Telegram Command Protocol — SCORE: 7/10

### "Brian:" Prefix Evaluation

**Current implementation:** `voice_handler.py` routes ALL messages through `BrainFlowEngine.process_message()` — no prefix needed. The "Brian:" prefix concept from the protocol is **NOT implemented** and **NOT necessary** in the current design because the bot already owns the chat channel.

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| "Brian:" prefix | Clear intent signal, multi-bot safe | Extra typing, missed messages | NOT RECOMMENDED (single-bot channel) |
| All messages to Brain | Zero friction, natural conversation | No escape hatch | CURRENT (good for single-user) |
| Slash commands (/task, /status) | Telegram native, auto-complete | Less natural, rigid | RECOMMENDED as supplement |
| Inline keyboards | Rich UI, guided flow | Complex state, no voice | PARTIALLY IMPLEMENTED (actions list) |

**Recommendation:** Keep current approach (all messages to Brain) + add slash commands for structured operations (`/status`, `/cancel`, `/history`). The `brain_flow.py` conversation state machine (7 phases) is well-designed with proper keyword detection for Hungarian.

**Rate limiting/auth gaps:**
- No rate limiting on incoming messages (vulnerability)
- Auth is implicit via Telegram chat_id (single user) — acceptable for current scope
- No anti-replay protection on webhook payloads

### Existing Implementation Quality
- `brain_flow.py:36-48` — FlowPhase enum (9 states) — GOOD
- `brain_flow.py:307-356` — Confirm handler with approve/cancel/modify — GOOD
- `brain_flow.py:611-625` — Clarification logic (confidence < 0.6, high risk) — GOOD
- `voice_handler.py:226-260` — Text handler with BrainFlow routing — GOOD

---

## 4. State Management — SCORE: 6/10

### Current State Architecture

| Component | Storage | Persistence | Queryable |
|-----------|---------|-------------|-----------|
| BrainConversation | In-memory dict | NO (lost on restart) | By user_id only |
| WorkflowExecution | In-memory + SQLAlchemy | YES (PostgreSQL/SQLite) | YES |
| Session | In-memory dict | NO | By session_id |
| Task | In-memory + TaskStore | YES (SQLAlchemy) | YES |
| Audit | AuditStore + Merkle chain | YES | YES |
| ConfirmationGate pending | In-memory dict | NO (lost on restart) | By chat_id/task_id |

**Critical gap:** `BrainConversation` and `ConfirmationGate` state is in-memory only. Server restart loses all active conversations and pending approvals.

### Event Sourcing vs CRUD

| Approach | Fit for OCCP | Rationale |
|----------|-------------|-----------|
| CRUD (current) | GOOD for tasks, agents | Simple, SQLAlchemy ORM works |
| Event sourcing | IDEAL for workflow/conversation | Full replay, audit trail, time-travel debug |
| Hybrid | RECOMMENDED | CRUD for entities + event log for state transitions |

**LangGraph comparison:** LangGraph uses per-node checkpointing with `PostgresSaver` — every state transition is persisted. OCCP's `WorkflowExecution.checkpoints` achieves similar but only at wave boundaries, not per-node. ([Source](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025))

**Recommendation:**
1. Persist `BrainConversation` to DB (P0 — data loss risk)
2. Add event log table for all state transitions (P1)
3. Per-node checkpointing in multi_agent.py (P1)
4. Move `ConfirmationGate` pending state to Redis or DB (P0)

### Sources
- [LangGraph Checkpointing Best Practices](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)
- [LangGraph Persistence Docs](https://docs.langchain.com/oss/python/langgraph/persistence)

---

## 5. Approval System — SCORE: 7/10

### STOP -> REQUEST -> WAIT Evaluation

**Current implementation (`confirmation_gate.py`):**
- Risk-based auto-approve (LOW -> auto, MEDIUM/HIGH/CRITICAL -> human) — CONFIRMED at line 145
- asyncio.Event-based blocking wait — CONFIRMED at line 177
- 5-minute timeout with configurable override — CONFIRMED at line 29
- Hungarian keyword matching for approve/reject — CONFIRMED at lines 23-26, 213-221

**Gaps vs. best practices:**

| Feature | Status | Industry Standard |
|---------|--------|-------------------|
| Risk-based auto-approve | IMPLEMENTED | Standard (LangGraph interrupt_before) |
| Timeout handling | IMPLEMENTED (5 min default) | Good, but needs escalation |
| Multi-party approval | MISSING | Required for critical ops (2+ approvers) |
| Escalation path | MISSING | Timeout -> escalate to backup approver |
| Approval delegation | MISSING | "Approve if I don't respond in X" |
| Approval audit trail | PARTIAL (stats only) | Full audit with who/when/what |
| Cross-channel approval | MISSING | Approve from Telegram OR dashboard |
| Conditional approval | MISSING | "Approve but skip deploy step" |

**Recommendation:**
1. Add multi-party approval for `critical` risk tasks (P1)
2. Add escalation chain: timeout -> secondary approver -> auto-reject (P1)
3. Persist pending approvals to DB for restart safety (P0)
4. Add approval audit entries to Merkle audit chain (P1)

---

## 6. Output Event Types — SCORE: 5/10

### Current 6 Types vs. Recommended

| Proposed Event | Status | Need | Priority |
|---------------|--------|------|----------|
| STATUS | Covered by `FlowPhase` transitions | YES | Existing |
| PROGRESS | Covered by `_handle_monitor` | YES | Existing |
| COMPLETION | Covered by `complete_task` callback | YES | Existing |
| QUESTION | Covered by `_handle_intake` clarification | YES | Existing |
| APPROVAL | Covered by `ConfirmationGate` | YES | Existing |
| ERROR | Covered by pipeline error handling | YES | Existing |
| **DELEGATION** | MISSING — no event when Brain delegates to agent | YES | P1 |
| **RETRY** | MISSING — retries happen silently in `_execute_with_retry` | YES | P1 |
| **TIMEOUT** | PARTIAL — `ConfirmationTimeoutError` exists but no broadcast event | YES | P1 |
| **ESCALATION** | MISSING — no escalation mechanism exists | YES | P1 |
| **HEARTBEAT** | MISSING — no liveness signal for long-running tasks | YES | P0 |
| **CANCELLED** | EXISTS in `FlowPhase.CANCELLED` but no broadcast event | YES | P2 |
| **CHECKPOINT** | MISSING — no event when workflow saves checkpoint | NICE | P2 |
| **METRIC** | MISSING — no telemetry event (duration, token usage) | NICE | P2 |

**Recommended minimum: 10 event types** (current 6 + DELEGATION, RETRY, HEARTBEAT, TIMEOUT)

**A2A comparison:** A2A protocol defines task lifecycle states: `submitted -> working -> input-required -> completed/failed/canceled` with streaming updates via SSE. OCCP should adopt similar structured event schema.

---

## 7. Security — OWASP ASI Top 10 (Agentic) — SCORE: 5/10

### OWASP Top 10 for Agentic Applications 2026 Mapping

| OWASP ASI Risk | OCCP Coverage | Gap | Priority |
|---------------|---------------|-----|----------|
| **ASI01: Agent Goal Hijacking** | PARTIAL — `pii_guard` evaluates LLM output, but no input sanitization for cross-channel injection | Telegram message -> Brain -> Agent chain allows indirect prompt injection | P0 |
| **ASI02: Tool Misuse** | PARTIAL — PolicyEngine gates, but tool allowlists are per-tier not per-agent | Agent can request tools outside its intended scope | P1 |
| **ASI03: Identity & Privilege Abuse** | WEAK — auth is implicit (chat_id), no per-agent identity, no credential rotation | Cross-channel auth inconsistency (Telegram vs API vs CloudCode) | P0 |
| **ASI04: Data Leakage** | PARTIAL — PII guard exists, but no data classification or exfiltration monitoring | Agent output may contain sensitive data from other sessions | P1 |
| **ASI05: Insecure Output Handling** | PARTIAL — `_escape_md` for Telegram, but no sanitization for webhook/SSE outputs | XSS risk in dashboard if agent output contains HTML | P1 |
| **ASI06: Inadequate Sandboxing** | GOOD — `sandbox_executor.py` exists, `browser_sandbox.py` for browser ops | Sandbox escape vectors need periodic review | P2 |
| **ASI07: Supply Chain Vulnerabilities** | PARTIAL — Snyk/GitGuardian in CI, but no runtime dependency check | OpenClaw skill injection via malicious SKILL.md | P1 |
| **ASI08: Excessive Autonomy** | GOOD — VAP pipeline enforces Plan->Gate->Execute, risk-based approval | Could strengthen with per-action cost/impact limits | P2 |
| **ASI09: Logging & Monitoring Failures** | GOOD — Merkle audit chain, per-command logging | Missing: cross-agent correlation ID, no real-time anomaly detection | P1 |
| **ASI10: Rogue Agents** | PARTIAL — trust levels mentioned in architecture, not enforced in code | No agent behavior baseline or drift detection | P1 |

**Cross-channel auth consistency gap:**
- Telegram: chat_id (implicit, no token)
- API: JWT token (full auth)
- CloudCode: No auth defined
- OpenClaw: Basic Auth + HMAC webhook

**Recommendation:** Unified identity layer with per-channel auth adapters mapping to a single user identity.

### Sources
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [OWASP Agentic Security Release](https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/)

---

## 8. Current OCCP Implementation Gap Analysis

### What's ALREADY Implemented (Coverage Map)

| Protocol Requirement | OCCP Module | File | Status |
|---------------------|------------|------|--------|
| Central orchestrator (Brain) | BrainFlowEngine | `orchestrator/brain_flow.py` | IMPLEMENTED (7-phase flow) |
| Bidirectional Telegram | VoiceCommandHandler | `adapters/voice_handler.py` | IMPLEMENTED (voice + text) |
| Command parsing (objective, scope, risk) | TaskRouter | `orchestrator/task_router.py` | IMPLEMENTED (keyword + pattern scoring) |
| Decompose -> Assign | MultiAgentOrchestrator | `orchestrator/multi_agent.py` | IMPLEMENTED (DAG + wave execution) |
| Track state | WorkflowExecution | `orchestrator/multi_agent.py:332-365` | IMPLEMENTED (in-memory + DB) |
| Verify (quality gate) | QualityGate + revision loop | `orchestrator/quality_gate.py`, `pipeline.py:437` | IMPLEMENTED |
| Output events | FlowPhase + Pipeline status | `brain_flow.py:36-48`, `pipeline.py` | PARTIAL (6/10 types) |
| State: ACTIVE/COMPLETED/FAILED | WorkflowStatus + TaskStatus | `multi_agent.py:92-99`, `models.py` | IMPLEMENTED |
| PENDING_APPROVALS | ConfirmationGate | `adapters/confirmation_gate.py` | IMPLEMENTED |
| Approval system | ConfirmationGate (risk-based) | `adapters/confirmation_gate.py` | IMPLEMENTED (single approver) |
| Persistent state | WorkflowStore (SQLAlchemy) | `store/workflow_store.py` | PARTIAL (workflows yes, conversations no) |
| Queryable state | WorkflowStore queries | `store/workflow_store.py` | IMPLEMENTED |
| CloudCode hooks | — | — | NOT IMPLEMENTED |
| A2A agent discovery | — | — | NOT IMPLEMENTED |
| Multi-party approval | — | — | NOT IMPLEMENTED |
| Heartbeat/liveness | — | — | NOT IMPLEMENTED |
| Event sourcing | — | — | NOT IMPLEMENTED |
| Cross-channel auth | — | — | NOT IMPLEMENTED |

### Implementation Percentage

- **Protocol requirements covered:** 12/18 = **67%**
- **Production-ready:** 8/18 = **44%** (in-memory state reduces production readiness)
- **Industry best-practice alignment:** ~60% (missing A2A, event sourcing, heartbeats)

---

## GAP Analysis Summary Table

| # | Protocol Requirement | Current Status | Gap Severity | Action Required |
|---|---------------------|---------------|-------------|-----------------|
| G1 | CloudCode hook integration | NOT IMPLEMENTED | CRITICAL | Build hook receiver endpoint + shell command adapter |
| G2 | BrainConversation persistence | IN-MEMORY ONLY | CRITICAL | Persist to DB (data loss on restart) |
| G3 | ConfirmationGate persistence | IN-MEMORY ONLY | CRITICAL | Persist pending approvals to DB/Redis |
| G4 | Cross-channel auth | INCONSISTENT | HIGH | Unified identity layer |
| G5 | Agent prompt injection guard | PARTIAL | HIGH | Input sanitization on all channels before Brain |
| G6 | Heartbeat/liveness events | MISSING | HIGH | WebSocket heartbeat for long-running tasks |
| G7 | DELEGATION/RETRY/TIMEOUT events | MISSING | MEDIUM | Add 4+ event types to protocol |
| G8 | A2A agent card discovery | MISSING | MEDIUM | Implement `/.well-known/agent.json` endpoint |
| G9 | Multi-party approval | MISSING | MEDIUM | Add for critical risk tasks |
| G10 | Escalation paths | MISSING | MEDIUM | Timeout -> escalate chain |
| G11 | Event sourcing for state transitions | MISSING | MEDIUM | Hybrid CRUD + event log |
| G12 | Per-node checkpointing | WAVE-LEVEL ONLY | LOW | Add node-level checkpoints |
| G13 | Streaming SSE (production) | STUB ONLY | LOW | Implement real SSE delivery |
| G14 | Rogue agent detection | MISSING | LOW | Agent behavior baseline + drift detection |

---

## Prioritized Action Items

### P0 — Must Fix Before Production

1. **Persist BrainConversation to DB** — `brain_flow.py` stores conversations in `dict[str, BrainConversation]`. Server restart = total data loss. Add SQLAlchemy model + store.
2. **Persist ConfirmationGate pending state** — `confirmation_gate.py:99` stores pending in `dict[str, PendingConfirmation]`. Restart during approval = stuck task. Move to Redis or DB with TTL.
3. **Cross-channel input sanitization** — All input channels (Telegram, API, CloudCode) must sanitize before reaching Brain to prevent ASI01 (Agent Goal Hijacking).
4. **Unified auth identity** — Map Telegram chat_id, API JWT, CloudCode session to single user identity for consistent access control.

### P1 — Required for Production Quality

5. **CloudCode hook receiver** — Add `POST /api/v1/hooks/claude-code` endpoint that receives PreToolUse/PostToolUse JSON and routes through Brain.
6. **Expand event types** — Add DELEGATION, RETRY, HEARTBEAT, TIMEOUT events. Define structured event schema (type, timestamp, correlation_id, payload).
7. **Multi-party approval for critical ops** — Require 2+ approvals for `risk_level=critical`.
8. **Escalation chain** — Timeout on primary approver -> notify secondary -> auto-reject after N minutes.
9. **A2A agent card endpoint** — Serve `/.well-known/agent.json` with OCCP Brain capabilities.
10. **Event log table** — Append-only table for all state transitions (enables replay, debugging, audit).
11. **Per-agent tool allowlists** — Enforce tool restrictions per agent type, not just per session tier.

### P2 — Nice to Have

12. **Per-node checkpointing** — Checkpoint after each node in DAG, not just wave boundaries.
13. **Production SSE/WebSocket** — Replace stub adapters with real aiohttp/starlette implementations.
14. **Agent behavior baseline** — Track agent output patterns for rogue agent detection (ASI10).
15. **Conditional approval** — Allow "approve with modifications" response.

---

## Recommended Protocol v2

```
SYSTEM ROLE: Brian the Brain — OCCP CONTROL PLANE v2
GLOBAL OBJECTIVE: Tri-directional control (CloudCode + Telegram + Dashboard API)

INPUT SOURCES:
  - CloudCode: PreToolUse/PostToolUse hooks -> POST /api/v1/hooks/claude-code (HIGH priority)
  - Telegram: webhook -> BrainFlowEngine (MEDIUM priority, all messages, no prefix needed)
  - Dashboard API: REST + WebSocket -> standard API auth (MEDIUM priority)

IDENTITY:
  - Unified identity layer: channel-specific auth -> mapped user_id
  - Per-agent identity: agent cards with capability + tool declarations
  - A2A compatible: /.well-known/agent.json for external discovery

COMMAND PARSING: (unchanged, well-designed)
  - objective, scope, risk, required agents, work packages
  - TaskRouter keyword + pattern scoring (Hungarian + English)

EXECUTION FLOW:
  - Decompose -> Assign -> Track -> Checkpoint (per-node) -> Verify -> Deliver
  - DAG wave execution with topological sort
  - Fan-out/fan-in with partial failure handling

EVENT TYPES (10):
  - STATUS, PROGRESS, COMPLETION, QUESTION, APPROVAL, ERROR (existing)
  - DELEGATION (agent assignment), RETRY (transient failure recovery)
  - HEARTBEAT (liveness signal, 30s interval), TIMEOUT (operation exceeded limit)

STATE MANAGEMENT:
  - Entity state: SQLAlchemy ORM (tasks, agents, users, workflows)
  - Conversation state: DB-persisted BrainConversation (not in-memory)
  - Transition log: append-only event table (event sourcing hybrid)
  - Checkpoints: per-node with PostgreSQL persistence
  - Approval state: Redis/DB with TTL (not in-memory)
  - Queryable: full API for state inspection + time-travel debug

APPROVAL SYSTEM:
  - LOW -> auto-approve
  - MEDIUM -> single approver, 5min timeout -> auto-reject
  - HIGH -> single approver, 10min timeout -> escalate to secondary
  - CRITICAL -> 2 approvers required, 15min timeout -> escalate + notify all channels
  - Cross-channel: approve from any authenticated channel
  - Audit: every approval decision in Merkle audit chain

SECURITY (OWASP ASI 2026):
  - Input sanitization on all channels before Brain (ASI01)
  - Per-agent tool allowlists (ASI02)
  - Unified identity + least privilege (ASI03)
  - PII guard on all outputs (ASI04)
  - Output escaping per channel (ASI05)
  - Sandbox enforcement (ASI06)
  - Dependency audit (ASI07)
  - VAP pipeline enforcement (ASI08)
  - Correlation-ID tracing across agents (ASI09)
  - Agent behavior baseline + drift alerts (ASI10)
```

---

## Score Summary

| Area | Score | Confidence |
|------|-------|------------|
| 1. Protocol Completeness | 7/10 | CONFIRMED |
| 2. CloudCode Integration | 3/10 | CONFIRMED |
| 3. Telegram Command Protocol | 7/10 | CONFIRMED |
| 4. State Management | 6/10 | CONFIRMED |
| 5. Approval System | 7/10 | CONFIRMED |
| 6. Output Event Types | 5/10 | CONFIRMED |
| 7. Security (OWASP ASI) | 5/10 | CONFIRMED |
| 8. Implementation Coverage | 6.7/10 | CONFIRMED |
| **Overall** | **5.8/10** | |

---

## Sources

- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Google A2A Protocol](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [A2A v0.3 Upgrade](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade)
- [A2A GitHub Repository](https://github.com/a2aproject/A2A)
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [LangGraph Checkpointing Best Practices](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)
- [LangGraph 2.0 Production Guide](https://dev.to/richard_dillon_b9c238186e/langgraph-20-the-definitive-guide-to-building-production-grade-ai-agents-in-2026-4j2b)
- [Multi-Agent Frameworks Comparison 2026](https://gurusup.com/blog/best-multi-agent-frameworks-2026)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks: 12 Events](https://www.pixelmojo.io/blogs/claude-code-hooks-production-quality-ci-cd-patterns)
- [CrewAI vs AutoGen 2026](https://kanerika.com/blogs/crewai-vs-autogen/)
