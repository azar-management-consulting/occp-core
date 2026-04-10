# RESEARCH.md — OpenClaw Deep Research Evidence

**Version:** 1.0.0 | **Date:** 2026-02-27
**Standard:** Clean-room (evidence only — no code, no implementation spec)
**Disclaimer:** All information sourced from public GitHub, documentation, and security disclosures. No proprietary code reviewed.

---

## Organization Overview

| Field | Value |
|-------|-------|
| **GitHub Org** | `github.com/openclaw` |
| **Total Repos** | 20 |
| **Primary Language** | TypeScript |
| **License** | MIT (all repos) |
| **Creator** | Peter Steinberger (joined OpenAI Feb 14, 2026) |
| **History** | Clawdbot → Moltbot → OpenClaw (Jan 30, 2026) |
| **Stars (main)** | ~236,000 |
| **Audit** | CrowdStrike Jan 2026: 512 vulnerabilities, 8 critical |

---

## Per-Component Evidence

### 1. openclaw/openclaw (Main Runtime)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/openclaw` |
| **Stars** | ~236,000 |
| **License** | MIT |
| **Language** | TypeScript |

**Feature Summary:**
- Hub-and-spoke Gateway architecture (WebSocket on 127.0.0.1:18789)
- 6-stage message pipeline: Transport → Context Assembly → Sampling → Tool Exec → Response → Output
- Session-as-security-boundary model (no cross-session state leakage)
- Composable system prompt assembly (AGENTS.md, SOUL.md, TOOLS.md, KNOWLEDGE.md)
- Declarative agent definition via Markdown frontmatter
- Desktop application (Electron-based)
- Local-first architecture (no mandatory cloud dependency)

**Risk Notes:**
- CVE-2026-25157: Command injection via crafted tool name
- CVE-2026-25253: One-click RCE via prompt injection in tool description (CVSS 8.8)
- CVE-2026-24763: Docker sandbox bypass allowing container escape
- 42,665+ publicly exposed instances discovered (93.4% vulnerable)
- Single-user trust model — no RBAC, no multi-tenant isolation
- Gateway listens on localhost only — designed for single-user desktop use

**What's Valuable (Architecture Patterns):**
1. Hub-and-spoke Gateway: central message routing, decoupled transport from logic
2. Composable system prompt: AGENTS.md/SOUL.md/TOOLS.md pattern for declarative agent config
3. Session isolation: per-session state boundary, clean destruction on close
4. 6-stage message pipeline: structured processing stages with deterministic ordering

---

### 2. openclaw/clawhub (Skill Registry)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/clawhub` |
| **Stars** | ~3,100 |
| **License** | MIT |
| **Language** | TypeScript |

**Feature Summary:**
- Community skill registry with 5,705+ published skills
- Install via `openclaw install <name>`
- Versioned skill packages with README, config, entry point
- Skill categories: web tools, APIs, code analysis, data processing, automation
- Rating and review system

**Risk Notes:**
- 824+ malicious skills discovered (335 from "ClawHavoc" campaign)
- No code signing — skills execute with full trust
- No capability declaration — skills can access any system resource
- No SBOM generation per skill version
- No supply-chain verification at install time
- Malicious skill example: data exfiltration via DNS tunneling hidden in utility skill

**What's Valuable (Architecture Patterns):**
1. CLI-driven skill management: `install`, `publish`, `search`, `update` workflow
2. Versioned registry with metadata (README, config schema, entry point convention)
3. Community discovery: categories, search, ratings
4. OCCP must add: signing, capability declaration, SAST/SCA scan pipeline, SBOM

---

### 3. openclaw/skills (First-Party Skills Collection)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/skills` |
| **Stars** | ~1,600 |
| **License** | MIT |
| **Language** | TypeScript |

**Feature Summary:**
- 50+ first-party skills maintained by OpenClaw team
- Skills include: web browser, file system, Git, Docker, database, Slack, calendar
- Each skill: `index.ts` entry, `config.json` schema, `README.md`
- Skills expose typed tool interfaces consumed by Gateway

**Risk Notes:**
- No capability boundary — any skill can access any resource (file, network, process)
- Skills run in same process as Gateway (no crash isolation)
- File system skill allows arbitrary path traversal
- Docker skill allows container management with host Docker socket access

**What's Valuable (Architecture Patterns):**
1. Typed tool interface pattern: strongly-typed input/output schemas per tool
2. Config-driven skill behavior: `config.json` schema defines user-configurable parameters
3. Skill composition: skills can reference other skills as dependencies
4. OCCP must add: per-skill capability declaration, sandbox enforcement, process isolation

---

### 4. openclaw/lobster (Workflow Engine)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/lobster` |
| **Stars** | ~644 |
| **License** | MIT |
| **Language** | TypeScript |

**Feature Summary:**
- Deterministic YAML/JSON workflow definitions
- Flow control without LLM-driven routing (explicit steps, conditions, loops)
- Approval gates as first-class primitives (human-in-the-loop checkpoints)
- Parallel step execution with join semantics
- Error handling: retry, fallback, abort with cleanup
- Variable passing between steps with type validation

**Risk Notes:**
- No cryptographic signing of workflow definitions
- Workflow execution bypasses prompt-level safety checks (deterministic, not LLM-gated)
- No audit trail of workflow step execution
- Approval gates are UI-based only — no API-driven approval

**What's Valuable (Architecture Patterns):**
1. Deterministic workflow: YAML-defined steps outside LLM control loop (predictable, testable)
2. Approval gates: first-class human-in-the-loop checkpoints (REQ-GOV-04 alignment)
3. Parallel execution with join: fork/join semantics for concurrent steps
4. Error handling patterns: retry with backoff, fallback chains, cleanup on abort
5. OCCP must add: VAP enforcement per workflow step, crypto audit trail, signed definitions

---

### 5. openclaw/acpx (Agent Communication Protocol)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/acpx` |
| **Stars** | ~107 |
| **License** | MIT |
| **Language** | TypeScript |

**Feature Summary:**
- Agent-to-agent communication protocol
- Message passing with typed envelopes
- Service discovery for agent endpoints
- Request/response and pub/sub patterns
- Protocol versioning

**Risk Notes:**
- No message signing or integrity verification
- No access control between agents (any agent can message any agent)
- No rate limiting on inter-agent communication
- No audit trail of agent-to-agent messages

**What's Valuable (Architecture Patterns):**
1. Typed message envelope: structured inter-agent communication with schema validation
2. Service discovery: dynamic agent endpoint registration and lookup
3. Pub/sub pattern: event-driven agent coordination
4. OCCP must add: message signing, RBAC-gated agent communication, audit trail, rate limiting

---

### 6. openclaw/openclaw-ansible (Deployment Automation)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/openclaw-ansible` |
| **Stars** | ~420 |
| **License** | MIT |
| **Language** | YAML (Ansible) |

**Feature Summary:**
- Ansible playbooks for OpenClaw deployment
- Docker Compose orchestration
- Reverse proxy (Nginx/Caddy) configuration
- SSL certificate management
- Multi-node deployment support

**Risk Notes:**
- Default Docker Compose exposes Gateway on 0.0.0.0 (not localhost) in some configs
- No network isolation between containers by default
- No secrets management integration (credentials in plain text vars)

**What's Valuable (Architecture Patterns):**
1. Infrastructure-as-Code deployment patterns
2. Docker Compose service orchestration templates
3. OCCP already has better Docker security (no-new-privileges, read_only, capability drops)

---

### 7. openclaw/clawdinators (Multi-Agent Orchestration)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/clawdinators` |
| **Stars** | ~119 |
| **License** | MIT |
| **Language** | TypeScript |

**Feature Summary:**
- Multi-agent orchestration framework
- Sequential, parallel, and conditional agent chains
- Result aggregation and conflict resolution
- Shared context management between agents
- Supervisor agent pattern

**Risk Notes:**
- No recursion depth limits — agent chains can loop indefinitely
- Shared context has no access control — all agents see all data
- No cascade kill mechanism for runaway chains
- No proof-carrying outputs (agent outputs not signed or integrity-checked)

**What's Valuable (Architecture Patterns):**
1. Supervisor agent: meta-agent that coordinates sub-agents and resolves conflicts
2. Result aggregation: merge strategies for multi-agent outputs (vote, consensus, authoritative)
3. Agent chain patterns: sequential, parallel, conditional routing
4. OCCP must add: recursion limits, cascade kill, RBAC-gated context, proof-carrying outputs

---

### 8. openclaw/nix-openclaw (Nix Packaging)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/nix-openclaw` |
| **Stars** | ~458 |
| **License** | MIT |
| **Language** | Nix |

**Feature Summary:**
- Nix flake for reproducible OpenClaw builds
- Declarative dependency management
- Cross-platform build targets

**Risk Notes:**
- Nix-specific, not broadly applicable

**What's Valuable:**
- Reproducible build pattern (relevant to SLSA provenance requirements)
- OCCP equivalent: CycloneDX SBOM + Sigstore signing (Phase 2)

---

### 9. openclaw/clawgo (Go SDK)

| Field | Value |
|-------|-------|
| **URL** | `github.com/openclaw/clawgo` |
| **Stars** | ~42 |
| **License** | MIT |
| **Language** | Go |

**Feature Summary:**
- Go client for OpenClaw Gateway API
- Basic transport and tool definition

**Risk Notes:**
- Early-stage, minimal adoption

**What's Valuable:**
- SDK pattern: Gateway communication abstraction
- OCCP already has Python + TypeScript SDKs (more mature)

---

### 10. Minor Repos (Stars < 50)

| Repo | Stars | Purpose | Relevance to OCCP |
|------|-------|---------|-------------------|
| openclaw/docs | ~35 | Documentation site | Documentation patterns |
| openclaw/openclaw-desktop | ~28 | Electron desktop app | Not applicable (OCCP is server-first) |
| openclaw/benchmarks | ~22 | Performance benchmarks | Benchmark methodology |
| openclaw/examples | ~18 | Example configurations | Config patterns |
| openclaw/logo | ~8 | Brand assets | Not applicable |
| openclaw/RFC | ~15 | Protocol RFCs | Protocol design patterns |
| openclaw/web | ~12 | Website source | Not applicable |

---

### Components NOT Found

| Component | Search Result |
|-----------|--------------|
| **DSGN / Design System repo** | Not found in openclaw org. No dedicated design system repo. |
| **Dedicated Python SDK** | Not found. OpenClaw is TypeScript-only; no official Python SDK. |
| **Dedicated TypeScript SDK** | No separate SDK repo; SDK functionality embedded in main repo. |
| **Scheduler/Cron repo** | Not separate; scheduling is built into main `openclaw/openclaw` runtime. |

---

## Security Disclosure Summary

### Known CVEs

| CVE ID | CVSS | Type | Description | OCCP Mitigation |
|--------|------|------|-------------|-----------------|
| CVE-2026-25157 | — | Command Injection | Crafted tool name allows arbitrary command execution | VAP gate validates tool names against allowlist (REQ-GOV-01) |
| CVE-2026-25253 | 8.8 | One-Click RCE | Prompt injection in tool description field enables code execution | Injection guards (20+ patterns) + ML classifier (REQ-SEC-01) |
| CVE-2026-24763 | — | Sandbox Bypass | Docker container escape via exposed host socket | nsjail/bwrap sandbox with no host socket access (REQ-CBDB-02) |

### ClawHavoc Campaign (Feb 2026)

| Metric | Value |
|--------|-------|
| Malicious skills discovered | 824+ |
| Campaign-specific skills | 335 ("ClawHavoc") |
| Attack vector | Data exfiltration via DNS tunneling |
| Root cause | No skill signing, no capability declaration, no supply-chain scan |
| OCCP mitigation | 4-stage scan pipeline + cosign signing + capability declaration (REQ-TSF-01..05, REQ-CPC-01..04) |

### Exposure Assessment (Wiz Research, Feb 2026)

| Metric | Value |
|--------|-------|
| Publicly exposed instances | 42,665+ |
| Vulnerable instances | 93.4% |
| Root cause | Gateway designed for localhost; deployed publicly without authentication |
| OCCP mitigation | API-key/JWT authentication mandatory; RBAC enforcement (existing) |

---

## Architecture Patterns for Clean-Room Adaptation

The following patterns are **ideas and architecture concepts** extracted from OpenClaw research. Each must be re-implemented from first principles with OCCP's governance model (VAP, policy gates, crypto audit trail).

| # | Pattern | OpenClaw Implementation | OCCP Clean-Room Approach |
|---|---------|------------------------|--------------------------|
| 1 | Hub-and-Spoke Gateway | WebSocket Gateway on localhost, single process | FastAPI async server with JWT auth, multi-process |
| 2 | Composable Agent Config | AGENTS.md/SOUL.md/TOOLS.md Markdown files | YAML/Markdown config with JSON schema validation + hot-reload |
| 3 | Typed Tool Interface | TypeScript tool schemas in skill packages | Python Protocol classes with Pydantic models |
| 4 | Deterministic Workflows | Lobster YAML/JSON engine | `orchestrator/workflows.py` with VAP enforcement per step |
| 5 | Hybrid Memory | Vector + BM25 + SQLite in single process | `store/memory/` with ChromaDB/Qdrant + rank-bm25, tenant-isolated |
| 6 | Multi-Agent Orchestration | Clawdinators supervisor pattern | `orchestrator/multi_agent.py` with recursion limits + cascade kill |
| 7 | CLI Skill Management | `openclaw install/publish/search` | `occp skill install/publish/search` with 4-stage scan pipeline |
| 8 | Agent Communication | ACPX typed envelopes, pub/sub | `orchestrator/agent_comms.py` with signed messages + RBAC |

---

## Governance Gap: OpenClaw vs OCCP

| Governance Requirement | OpenClaw | OCCP v0.8.2 | OCCP v1.0 Target |
|----------------------|----------|-------------|-------------------|
| Policy Gate | Basic content filter | 5 guards (PII, injection, resource, output, human) | + ABAC, ML classifier, budget guard, browser policy |
| VAP Lifecycle | No structured pipeline | 5-stage VAP (Plan→Gate→Execute→Validate→Ship) | Non-bypassable, fuzz-verified |
| Crypto Audit Trail | None | SHA-256 hash chain | Per-entry linked, tamper-evident, SIEM export |
| SBOM + Signing | None | Supply chain scanner | CycloneDX SBOM + cosign signing + verification |
| Sandbox Isolation | Process-level only | nsjail → bwrap → process → mock | + browser sandbox, plugin sandbox |
| Kill-Switch | None | Circuit breaker (LLM failover) | + cascade kill, budget hard-stop, admin emergency halt |

---

## Risk Summary for OCCP Integration

| Risk Level | Count | Description |
|-----------|-------|-------------|
| **Critical** | 3 | CVE-based attacks (injection, RCE, sandbox escape) — all mitigated by OCCP's existing security |
| **High** | 4 | Supply chain (ClawHavoc), exposure (42K instances), Baileys instability, protocol evolution |
| **Medium** | 5 | API surface expansion, ML latency, false positive scanning, context exhaustion, multi-tenant |
| **Low** | 3 | Niche SDKs, local model support, design system absence |

**Bottom Line:** OpenClaw provides excellent runtime feature patterns but zero governance infrastructure. OCCP's value proposition is wrapping these runtime patterns in enterprise-grade governance (VAP, RBAC, crypto audit, SBOM, sandbox, kill-switch). Every adopted pattern must pass through OCCP's 6 mandatory governance gates.
