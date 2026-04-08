# ARCHITECTURE.md — OCCP v1.0 "Agent Control Plane"

**Version:** 2.0.0 | **Date:** 2026-02-27
**Scope:** End-to-end system architecture, component design, data flows, trust boundaries

---

## 1. Executive Architecture Overview

OCCP is a **governance-first agent control plane**. Every execution path routes through the Verified Autonomy Pipeline (VAP): `Plan → Gate → Execute → Validate → Ship`. Policy enforcement, cryptographic audit, and sandbox isolation are **non-bypassable by design**.

**Primary Architectural Objectives:**
- Deterministic governance for all agent actions (REQ-GOV-01..06)
- Cryptographic auditability and supply-chain verification (REQ-CPC-01..04)
- Secure extensibility via skills, plugins, adapters, and MCP (REQ-TSF, REQ-MARKET, REQ-MCP)
- Multi-tenant data isolation with compliance controls (REQ-MULTI-01..02)

**Architectural Invariants (must hold at all system states):**
1. VAP is non-bypassable — no execution path skips any stage
2. Every action emits an audit entry with hash-chain integrity
3. All extensions (skills/plugins/MCP/adapters) are policy-gated before execution
4. Sandbox isolation for any untrusted execution path
5. Tenant data never crosses org boundaries

---

## 2. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TB-0: EXTERNAL UNTRUSTED                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Dashboard │ │SDK Py/TS │ │ Channels │ │MCP Servers│ │ Browser  │ │
│  │(Next.js) │ │          │ │WA/TG/SL/D│ │(tool prov)│ │(Playwrgt)│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
└───────┼────────────┼────────────┼────────────┼────────────┼────────┘
        │            │            │            │            │
┌───────┴────────────┴────────────┴────────────┴────────────┴────────┐
│                     TB-1: NETWORK PERIMETER                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   API Layer (FastAPI)                         │   │
│  │  ┌─────┐ ┌──────┐ ┌──────────┐ ┌───────┐ ┌──────────────┐  │   │
│  │  │Auth │ │RBAC  │ │Rate Limit│ │CORS   │ │Request Norm. │  │   │
│  │  │JWT/ │ │Casbin│ │Middleware│ │Filter │ │+ Validation  │  │   │
│  │  │APIKey│ │      │ │          │ │       │ │              │  │   │
│  │  └─────┘ └──────┘ └──────────┘ └───────┘ └──────────────┘  │   │
│  │  Routes: /auth /tasks /pipeline /agents /skills /mcp /audit │   │
│  │          /tokens /policy /onboarding /ws /status /llm        │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
└────────────────────────────────┼───────────────────────────────────┘
                                 │
┌────────────────────────────────┼───────────────────────────────────┐
│                     TB-2: APPLICATION CORE                          │
│  ┌─────────────────────────────┴───────────────────────────────┐   │
│  │                   Orchestrator Core                           │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │   │
│  │  │Message       │ │Session       │ │Config-First Agent    │ │   │
│  │  │Pipeline      │ │Manager       │ │Definition Loader     │ │   │
│  │  │(REQ-CORE-01) │ │(REQ-CORE-02) │ │(REQ-CORE-03)         │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │   │
│  │  ┌──────────────────────────────────────────────────────────┐│   │
│  │  │              VAP Pipeline (REQ-GOV-01)                    ││   │
│  │  │  Plan ──► Gate ──► Execute ──► Validate ──► Ship         ││   │
│  │  └──────────────────────────────────────────────────────────┘│   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │   │
│  │  │Adapter       │ │Scheduler     │ │Plugin Host           │ │   │
│  │  │Registry      │ │(REQ-AUTO-01) │ │(REQ-MARKET-02)       │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
┌────────────────────────────────┼───────────────────────────────────┐
│                     TB-3: POLICY KERNEL                             │
│  ┌─────────────────────────────┴───────────────────────────────┐   │
│  │                   Policy Engine                               │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │   │
│  │  │Policy-as-Code│ │ABAC + RBAC   │ │Trust Level Enforcer  │ │   │
│  │  │(REQ-GOV-02)  │ │(REQ-POL-01)  │ │(REQ-GOV-06)          │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │   │
│  │  ┌──────────────────────────────────────────────────────────┐│   │
│  │  │  Guards: PII | Injection | Resource | Output | Budget    ││   │
│  │  │          (Existing)       (Existing) (Existing)(REQ-VSTA-03)│   │
│  │  └──────────────────────────────────────────────────────────┘│   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │   │
│  │  │Break-Glass   │ │Policy Audit  │ │Anomaly Detector      │ │   │
│  │  │(REQ-GOV-04)  │ │(REQ-POL-02)  │ │(REQ-RT-04)           │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
┌────────────────────────────────┼───────────────────────────────────┐
│                     TB-4: SECURITY KERNEL                           │
│  ┌─────────────────────────────┴───────────────────────────────┐   │
│  │                   Security Layer                              │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │   │
│  │  │Audit Chain   │ │Signing       │ │SLSA Provenance       │ │   │
│  │  │SHA-256+Merkle│ │cosign        │ │(REQ-CPC-01)          │ │   │
│  │  │(Existing+    │ │(REQ-CPC-02)  │ │                      │ │   │
│  │  │ REQ-SEC-06)  │ │              │ │                      │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │   │
│  │  │AES-256-GCM   │ │Credential    │ │Supply Chain Scanner  │ │   │
│  │  │Encryption    │ │Vault         │ │Semgrep+Snyk+GG       │ │   │
│  │  │(Existing)    │ │(REQ-SEC-03)  │ │(REQ-TSF-05)          │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │   │
│  │  ┌──────────────┐ ┌──────────────┐                          │   │
│  │  │Revocation    │ │SBOM          │                          │   │
│  │  │(REQ-CPC-04)  │ │(REQ-TSF-03)  │                          │   │
│  │  └──────────────┘ └──────────────┘                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
┌────────────────────────────────┼───────────────────────────────────┐
│                     TB-6: SANDBOX ZONE                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐ │
│  │Skill         │ │Worker Agent  │ │Browser       │ │MCP Client │ │
│  │Execution     │ │Sandbox       │ │Context       │ │Runtime    │ │
│  │(nsjail/bwrap)│ │(REQ-MAO-01)  │ │(REQ-CBDB-01) │ │(REQ-MCP-04)│ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘ │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
┌────────────────────────────────┼───────────────────────────────────┐
│                     TB-5: DATA LAYER                                │
│  ┌──────────────────┐ ┌──────────────┐ ┌────────────────────────┐ │
│  │SQL Store         │ │Memory Store  │ │Audit Store             │ │
│  │(tenant-aware ORM)│ │(vector+BM25) │ │(hash-chained, encrypted)│ │
│  │(REQ-MULTI-01)    │ │(REQ-MEM-01)  │ │(Existing)              │ │
│  └──────────────────┘ └──────────────┘ └────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Architecture

### 3.1 API Layer (`api/`)

```
api/
├── app.py              # FastAPI application factory, lifespan events
├── auth.py             # JWT + API key authentication
├── deps.py             # Dependency injection (DB sessions, pipeline)
├── middleware.py        # CORS, rate limiting, request logging, error handling
├── models.py           # Pydantic request/response schemas
├── rbac.py             # Casbin RBAC integration
├── ws_manager.py       # WebSocket connection manager
└── routes/
    ├── agents.py       # Agent CRUD + configuration
    ├── audit.py        # Audit trail queries
    ├── auth.py         # Login, register, token refresh
    ├── llm.py          # LLM provider proxy
    ├── mcp.py          # MCP server management
    ├── onboarding.py   # Setup wizard flow
    ├── pipeline.py     # Pipeline execution + monitoring
    ├── policy.py       # Policy evaluation queries
    ├── skills.py       # Skill management + marketplace
    ├── status.py       # Health check + version info
    ├── tasks.py        # Task CRUD + history
    ├── tokens.py       # Encrypted token management
    └── ws.py           # WebSocket event streaming
```

**Key design decisions:**
- All routes require authentication (JWT or API key) except `/health` and `/status`
- RBAC enforcement via Casbin middleware: viewer → operator → admin → system_admin
- Rate limiting: configurable per-route, per-user, sliding window
- Request validation: Pydantic v2 models for all inputs
- **v1.0 additions:** SSE streaming endpoints (REQ-SDK-01), webhook receiver (REQ-AUTO-02), MCP server mode (REQ-SDK-02)

### 3.2 Orchestrator (`orchestrator/`)

```
orchestrator/
├── pipeline.py         # VAP 5-stage pipeline (222 lines)
├── scheduler.py        # Task queue + scheduling
├── adapter_registry.py # Planner/executor registration
├── models.py           # Pipeline domain models (Task, Plan, Result)
├── exceptions.py       # Pipeline-specific exceptions
└── adapters/           # (registered via adapter_registry)
```

**VAP State Machine:**

```
                    ┌───────────────────────┐
                    │      SUBMITTED        │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │       PLANNING        │ ◄── Planner adapter creates plan
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │       GATING          │ ◄── Policy engine evaluates
                    │  (guards + RBAC +     │     PII, injection, resource,
                    │   ABAC + trust level) │     output, budget guards
                    └───────┬───────┬───────┘
                            │       │
                       PASS │       │ DENY → 403 + audit entry
                            │       │
                    ┌───────▼───────┘
                    │     EXECUTING         │ ◄── Sandbox executor runs tools
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │     VALIDATING        │ ◄── Output validation + guards
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │      SHIPPING         │ ◄── Results + audit hash
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │      COMPLETED        │
                    └───────────────────────┘
```

**Adapter failover chain:** Claude → OpenAI → Echo (with circuit breaker per provider)

**v1.0 additions:**
- Message Pipeline: normalize channel input → VAP (REQ-CORE-01)
- Session Manager: main/DM/group tiers with scoped tools (REQ-CORE-02)
- Config-First Agent Loader: YAML/Markdown agent definitions (REQ-CORE-03)
- Cron Scheduler: timezone-aware, retry, VAP-enforced (REQ-AUTO-01)
- Plugin Host: subprocess isolation, crash boundary (REQ-MARKET-02)

### 3.3 Policy Engine (`policy_engine/`)

```
policy_engine/
├── engine.py           # PolicyEngine: evaluate() + audit trail emission
├── guards.py           # 4 guards: PII, Injection, Resource, Output
├── models.py           # PolicyDecision, GuardResult, EvaluationContext
└── exceptions.py       # PolicyViolation, GuardError
```

**Guard evaluation order (sequential, fail-fast):**

```
Input → PromptInjectionGuard → PIIGuard → ResourceLimitGuard → [execute] → OutputSanitizationGuard
```

**v1.0 additions:**
- ABAC engine alongside Casbin RBAC (REQ-POL-01)
- ML injection classifier: DistilBERT dual-mode (REQ-SEC-01)
- Budget guard: per-org token limits (REQ-VSTA-03)
- Trust level enforcer: L0-L5 (REQ-GOV-06)
- Browser policy: domain allow/deny, form approval (REQ-CBDB-02..03)
- Anomaly detector: tool count, cost pattern (REQ-RT-04)
- Policy profiles: per-schedule template (REQ-VSTA-02)

### 3.4 Adapters (`adapters/`)

```
adapters/
├── claude_planner.py      # Anthropic Claude planner (primary)
├── openai_planner.py      # OpenAI planner (fallback)
├── echo_planner.py        # Deterministic echo planner (testing/mock)
├── multi_llm_planner.py   # Circuit-breaker failover chain
├── sandbox_executor.py    # nsjail → bwrap → process → mock executor
├── mock_executor.py       # Test/development executor
├── policy_gate.py         # Policy evaluation adapter
├── basic_validator.py     # Output validation adapter
└── log_shipper.py         # Audit log shipper adapter
```

**Sandbox executor chain (defense-in-depth):**

```
nsjail (preferred) → bwrap (fallback) → process (minimal) → mock (dev only)
```

**v1.0 additions:**
- Channel adapters: WhatsApp/Telegram/Slack/Discord (REQ-CHAN-01..05)
- Browser adapter: Playwright isolated contexts (REQ-CBDB-01..05)
- MCP client: tool discovery, scope enforcement (REQ-MCP-01..04)
- Ollama adapter: local model support (REQ-CORE-04)

### 3.5 Store (`store/`)

```
store/
├── base.py               # SQLAlchemy Base, cross-dialect types (GUID, JSONBText)
├── database.py            # Async engine factory, session maker
├── engine.py              # Connection management, URL resolution
├── models.py              # 6 ORM models (see schema below)
├── agent_store.py         # Agent config CRUD
├── audit_store.py         # Audit chain: append, verify, query
├── onboarding_store.py    # Onboarding wizard state
├── task_store.py          # Task lifecycle persistence
├── token_store.py         # Encrypted token CRUD
└── user_store.py          # User management + auth
```

**Database Schema (v0.8.2):**

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│     tasks        │     │  audit_entries    │     │   agent_configs     │
├─────────────────┤     ├──────────────────┤     ├─────────────────────┤
│ id (PK, str32)  │     │ id (PK, str32)   │     │ agent_type (PK)     │
│ name            │     │ timestamp        │     │ display_name        │
│ description     │     │ actor            │     │ capabilities (JSON) │
│ agent_type      │     │ action           │     │ max_concurrent      │
│ risk_level      │◄────│ task_id (FK)     │     │ timeout_seconds     │
│ status          │     │ detail (JSON)    │     │ metadata (JSON)     │
│ plan (JSON)     │     │ prev_hash        │     │ created_at          │
│ result (JSON)   │     │ hash             │     │ updated_at          │
│ error           │     └──────────────────┘     └─────────────────────┘
│ metadata (JSON) │
│ created_at      │     ┌──────────────────┐     ┌─────────────────────┐
│ updated_at      │     │     users         │     │ encrypted_tokens    │
└─────────────────┘     ├──────────────────┤     ├─────────────────────┤
                        │ id (PK, str32)   │     │ id (PK, str32)      │
┌─────────────────┐     │ username (unique)│     │ user_id             │
│onboarding_prog. │     │ password_hash    │     │ org_id              │
├─────────────────┤     │ role             │     │ provider            │
│ user_id (PK)    │     │ is_active        │     │ encrypted_value     │
│ org_id          │     │ display_name     │     │ masked_value        │
│ state           │     │ email            │     │ label               │
│ current_step    │     │ metadata (JSON)  │     │ is_active           │
│ completed_steps │     │ created_at       │     │ created_at          │
│ completed_flag  │     │ updated_at       │     │ updated_at          │
│ run_id          │     └──────────────────┘     └─────────────────────┘
│ audit_linkage   │
│ metadata (JSON) │
│ completed_at    │
│ created_at      │
│ updated_at      │
└─────────────────┘
```

**Cross-dialect support:** SQLite ↔ PostgreSQL via `GUID` and `JSONBText` custom types.

**v1.0 additions:**
- Memory store: vector (sqlite-vec / pgvector) + BM25 fusion retrieval (REQ-MEM-01)
- Memory compaction: ≥60% storage reduction (REQ-MEM-02)
- Knowledge base: cross-session, RBAC-filtered (REQ-MEM-03)
- Tenant isolation: org-scoped encryption keys, row-level security (REQ-MULTI-01)
- New tables: `memory_entries`, `knowledge_base`, `sessions`, `cron_jobs`, `skill_manifests`

### 3.6 Security (`security/`)

```
security/
├── encryption.py         # AES-256-GCM envelope encryption (HKDF-SHA256 per-token DEK)
├── governance.py         # Governance utilities + policy helpers
├── supply_chain.py       # Typosquatting + homoglyph detection
└── SECRETS_POLICY.md     # Credential handling policy
```

**Encryption architecture:**

```
Master Key (OCCP_ENCRYPTION_KEY env var)
    │
    ├── HKDF-SHA256 derivation
    │       │
    │       ├── Per-token DEK (unique per encrypted_tokens row)
    │       │       │
    │       │       └── AES-256-GCM encrypt/decrypt
    │       │
    │       └── Per-org DEK (future: REQ-MULTI-01)
    │
    └── Audit chain: SHA-256(prev_hash + entry_data) = hash
```

**v1.0 additions:**
- SLSA provenance attestation (REQ-CPC-01)
- Artifact signing via cosign (REQ-CPC-02)
- Runtime signature verification (REQ-CPC-03)
- Revocation framework: 5-min polling (REQ-CPC-04)
- Credential vault: per-org isolation (REQ-SEC-03)
- SBOM generation: CycloneDX (REQ-TSF-03)
- Scan pipeline: Semgrep + Snyk + GitGuardian (REQ-TSF-05)
- Merkle root per-run audit verification (REQ-SEC-06)
- ML injection classifier: DistilBERT INT8 (REQ-SEC-01)

### 3.7 Dashboard (`dash/`)

```
dash/src/app/
├── layout.tsx            # Root layout with providers
├── page.tsx              # Landing/home page
├── globals.css           # Global styles
├── providers.tsx         # React context providers
├── login/                # Authentication UI
├── agents/               # Agent management views
├── audit/                # Audit trail viewer
├── docs/                 # API documentation viewer
├── mcp/                  # MCP server management
├── pipeline/             # Pipeline execution & monitoring
├── policy/               # Policy rule viewer
├── settings/             # Application settings
└── skills/               # Skill marketplace browser
```

**Tech stack:** Next.js 15, React, TypeScript, Tailwind CSS, shadcn/ui

**v1.0 additions:**
- Compliance dashboard: SOC2/HIPAA/GDPR/EU AI Act mapping (REQ-COMP-01)
- Agent Canvas workspace: sandboxed iframe for agent-generated UI (REQ-A2UI-01)
- Agent config editor: YAML/Markdown agent definition UI (REQ-CORE-03)

### 3.8 SDKs (`sdk/`)

```
sdk/
├── python/               # Python SDK (sync client, pip installable)
│   ├── occp_sdk/
│   │   └── client.py     # OCCPClient: execute, get_task, list_agents
│   └── pyproject.toml
└── typescript/           # TypeScript SDK (sync client, npm installable)
    ├── src/
    │   └── index.ts      # OCCPClient class
    └── package.json
```

**v1.0 additions:**
- SSE streaming support in both SDKs (REQ-SDK-01)
- OCCP as MCP server mode (REQ-SDK-02)

---

## 4. Trust Boundaries

| Boundary | Zone | Components | Auth Mechanism | Data Crossing |
|----------|------|------------|----------------|---------------|
| **TB-0** | External Untrusted | Users, LLM providers, web pages, channel messages, MCP servers | None (untrusted) | All input sanitized before crossing TB-1 |
| **TB-1** | Network Perimeter | API server, dashboard, SDK endpoints | JWT / API key / session | TLS 1.3, rate limiting, CORS |
| **TB-2** | Application Core | Orchestrator, message pipeline, session manager, scheduler | Internal service calls | Authenticated context propagation |
| **TB-3** | Policy Kernel | Policy engine, VAP enforcement, guard rules, ABAC | Policy evaluation only | Decision objects (allow/deny + audit) |
| **TB-4** | Security Kernel | Audit chain, signing, revocation, vault, encryption | System-level credentials | Encrypted data only |
| **TB-5** | Data Layer | Tenant-isolated SQL, memory store, audit logs | Per-org DEK encryption | Row-level security, org-scoped queries |
| **TB-6** | Sandbox Zone | Skills, plugins, worker agents, browser contexts | Capability declarations | Sandboxed I/O only, no host access |

**Trust boundary crossing rules:**
- TB-0 → TB-1: All input treated as hostile. Injection scanning, schema validation.
- TB-1 → TB-2: Authenticated context required. No anonymous pipeline access.
- TB-2 → TB-3: Policy evaluation is mandatory and non-bypassable for all actions.
- TB-3 → TB-4: Only policy-approved actions reach security kernel for signing/audit.
- TB-2 → TB-6: All sandboxed execution passes through TB-3 gate first.
- TB-6 → TB-5: Sandboxed code has no direct data layer access. Results return via TB-2.

---

## 5. Key Data Flows

### 5.1 User Request → Agent Execution

```
1. Client submits request → API Server (TB-1)
2. Auth middleware validates JWT/API key
3. RBAC checks user role for requested action
4. Request normalized → Orchestrator (TB-2)
5. Message Pipeline routes to correct session
6. VAP Plan stage: planner adapter creates task plan
7. VAP Gate stage: policy engine evaluates (TB-3)
   - Guards: injection → PII → resource → budget
   - ABAC/RBAC: role + attributes + trust level
   - Trust level check: action within declared level
8. VAP Execute stage: sandbox executor runs tools (TB-6)
   - Skill execution in nsjail/bwrap sandbox
   - Tool calls via MCP client (if applicable)
   - Browser automation in isolated Playwright context
9. VAP Validate stage: output guards + validation
10. VAP Ship stage: results + audit hash → client
11. Audit entry: SHA-256 chained with prev_hash
```

### 5.2 Skill Installation (OCCPHub)

```
1. Skill publish → scan pipeline (REQ-TSF-05)
   - Semgrep SAST scan
   - Snyk SCA dependency check
   - GitGuardian secret detection
   - Capability declaration validation
2. SBOM generated (REQ-TSF-03, CycloneDX)
3. Artifact signed (REQ-CPC-02, cosign)
4. Published to private registry (REQ-TSF-01)
5. Install: runtime signature verification (REQ-CPC-03)
6. Version pinning enforced (REQ-TSF-04)
7. Revocation check on 5-min polling cycle (REQ-CPC-04)
```

### 5.3 MCP Tool Invocation

```
1. MCP server registered in enterprise registry (REQ-MCP-01)
2. Scope-based consent flow (REQ-MCP-02)
3. Tool call → VAP gate (policy evaluation)
4. Runtime scope enforcement (REQ-MCP-04)
5. Execution in sandboxed context
6. Result sanitization (output guard)
7. Audit entry with hash chain
```

### 5.4 Scheduled Job Execution

```
1. Cron definition with timezone + retry policy (REQ-AUTO-01)
2. Scheduler fires → creates pipeline task
3. Full VAP pipeline execution (REQ-VSTA-01)
4. Budget guard checks org limits (REQ-VSTA-03)
5. Time-bound execution enforced (REQ-VSTA-04)
6. On timeout: SIGTERM → 30s grace → SIGKILL
7. Results persisted + audit trail
```

### 5.5 Multi-Agent Orchestration

```
1. Parent agent creates worker agents (REQ-MAO-01)
2. Workers run in isolated sandbox containers
3. Recursion depth checked (REQ-MAO-02, max 10)
4. Workers produce proof-carrying outputs (REQ-MAO-05)
5. Deterministic merge contract combines results (REQ-MAO-04)
6. Parent failure → cascade stop to all children (REQ-MAO-03)
7. Total budget = recursion_depth × per_agent_budget
```

---

## 6. Deployment Architecture

### 6.1 Current Production (v0.8.2)

```
Hetzner cx42 (195.201.238.144)
├── Apache2 (reverse proxy, SSL termination)
│   ├── occp.ai → static landing page
│   ├── api.occp.ai → :8000 (Docker: occp-api)
│   ├── dash.occp.ai → :3000 (Docker: occp-dash)
│   └── mail.occp.ai → Mailcow
├── Docker Compose
│   ├── api (Python 3.12, FastAPI, read_only, no-new-privileges)
│   ├── dash (Node 20, Next.js 15, read_only, no-new-privileges)
│   └── Volume: occp-data (SQLite DB + persistent state)
└── Let's Encrypt (auto-renewal via certbot)
```

### 6.2 Target Production (v1.0)

```
Hetzner cx42+ (or cluster)
├── Apache2 / Nginx (reverse proxy, SSL, WebSocket upgrade)
│   ├── api.occp.ai → :8000 (API + SSE + WebSocket)
│   ├── dash.occp.ai → :3000 (Dashboard + Canvas)
│   └── webhook.occp.ai → :8000/api/v1/webhooks
├── Docker Compose (extended)
│   ├── api (+ cron scheduler, webhook receiver, MCP server)
│   ├── dash (+ compliance dashboard, agent canvas)
│   ├── memory-db (PostgreSQL + pgvector / SQLite + sqlite-vec)
│   ├── redis (optional: rate limiting, session cache)
│   └── Volumes: occp-data, memory-data, audit-data
├── Internal network bridge (services communicate internally)
└── External exposure: API + Dash only (via reverse proxy)
```

**Docker security hardening (applied to all containers):**
- `no-new-privileges: true`
- `read_only: true` (tmpfs for /tmp)
- `seccomp` profile (default or custom)
- Capability drops (no `NET_RAW`, no `SYS_ADMIN`)
- No Docker socket mounting
- Non-root user inside containers

---

## 7. Module Ownership Map

| Domain | REQ-IDs | Owner Module(s) | Phase |
|--------|---------|-----------------|-------|
| Governance | REQ-GOV-01..06 | `orchestrator/pipeline.py`, `policy_engine/engine.py` | 1, 8 |
| Policy | REQ-POL-01..03 | `policy_engine/engine.py`, `policy_engine/guards.py` | 1 |
| Cryptographic Provenance | REQ-CPC-01..04 | `security/provenance.py`, `security/signing.py` | 2 |
| Trusted Skill Fabric | REQ-TSF-01..05 | `security/supply_chain.py`, `config/registry.yaml` | 2 |
| Security Enhancement | REQ-SEC-01..06 | `security/`, `policy_engine/guards.py` | 1 |
| Core Pipeline | REQ-CORE-01..04 | `orchestrator/`, `adapters/` | 1 |
| Channel Adapters | REQ-CHAN-01..05 | `adapters/channel_*.py` | 4 |
| Memory | REQ-MEM-01..03 | `store/memory_store.py`, `store/knowledge_base.py` | 3 |
| Agent Canvas | REQ-A2UI-01 | `dash/src/app/canvas/` | 4 |
| Verified Scheduler | REQ-VSTA-01..04 | `orchestrator/scheduler.py`, `policy_engine/` | 5 |
| Automation | REQ-AUTO-01..04 | `orchestrator/cron.py`, `api/routes/webhooks.py` | 5, 8 |
| Multi-Agent | REQ-MAO-01..05 | `orchestrator/session_tools.py`, `orchestrator/merge.py` | 6 |
| Browser | REQ-CBDB-01..05 | `adapters/browser_adapter.py`, `policy_engine/browser_policy.py` | 7 |
| MCP | REQ-MCP-01..04 | `adapters/mcp_client.py`, `config/mcp_registry.py` | 7 |
| Marketplace | REQ-MARKET-01..02 | `api/routes/skills.py`, `orchestrator/plugin_host.py` | 8 |
| SDK | REQ-SDK-01..02 | `sdk/python/`, `sdk/typescript/` | 8 |
| Compliance | REQ-COMP-01..02 | `dash/src/app/compliance/`, `adapters/siem_export.py` | 8, 9 |
| Multi-Tenancy | REQ-MULTI-01..02 | `store/models.py`, `config/settings.py` | 9 |
| Red-Team | REQ-RT-01..05 | `tests/red_team/` | 10 |

---

## 8. Key Architectural Decisions

| # | Decision | Rationale | Alternatives Considered |
|---|----------|-----------|------------------------|
| AD-01 | Python (FastAPI) for API + orchestrator | Async ecosystem, ML classifier integration, existing codebase | Go (performance), Node.js (MCP native) |
| AD-02 | SQLAlchemy 2.0 async ORM | Cross-dialect (SQLite↔PostgreSQL), type-safe, migration support | Raw SQL, Tortoise ORM |
| AD-03 | Casbin for RBAC/ABAC | Declarative policy model, multi-backend, well-maintained | OPA (heavier), Cedar (AWS-specific) |
| AD-04 | AES-256-GCM envelope encryption | FIPS-compliant, per-token key derivation, forward secrecy | ChaCha20-Poly1305 (faster but less universal) |
| AD-05 | nsjail/bwrap sandbox chain | No Docker-in-Docker required, minimal overhead, defense-in-depth | gVisor (heavier), Firecracker (VM overhead) |
| AD-06 | SHA-256 hash chain for audit | Tamper-evident, verifiable, lightweight | Blockchain (overkill), append-only log (no integrity) |
| AD-07 | Next.js 15 for dashboard | SSR for SEO, React ecosystem, TypeScript native | Vue.js, SvelteKit |
| AD-08 | cosign for artifact signing | Cloud-native standard, keyless option, Sigstore integration | GPG (key management burden), Notation (Azure-specific) |
| AD-09 | SQLite default, PostgreSQL production | Zero-config dev, production-grade scaling path, pgvector for memory | MongoDB (schema-less risk), DynamoDB (vendor lock) |
| AD-10 | DistilBERT for ML injection detection | Small model (<300MB), fast inference (<50ms), fine-tunable | GPT-based (expensive), regex-only (limited accuracy) |
| AD-11 | Playwright for browser automation | Multi-browser, headless, isolated contexts, active maintenance | Puppeteer (Chrome-only), Selenium (heavier) |
| AD-12 | Trust levels L0-L5 per execution | Granular autonomy control, maps to compliance requirements | Binary allow/deny (too coarse), per-tool (too granular) |
