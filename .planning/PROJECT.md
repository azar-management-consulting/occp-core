# PROJECT.md — OCCP v1.0 "Agent Control Plane"

**Version:** 1.0.0-draft
**Date:** 2026-02-27
**Author:** Fulop Henrik
**Status:** PLANNING

---

## Project Goal

Transform OCCP from a **governance-first AI orchestration engine** (v0.8.2) into a **full-spectrum Agent Control Plane** (v1.0) that can compete with and surpass OpenClaw's runtime capabilities while maintaining OCCP's core differentiator: **non-bypassable governance, tamper-evident audit, and EU AI Act compliance**.

The v1.0 release bridges the gap between OCCP's enterprise-grade security architecture and OpenClaw's consumer-facing runtime features (messaging integrations, skill marketplace, memory system, browser automation, cron scheduling) — delivering both under a single, policy-gated platform.

---

## Scope Boundaries

### In Scope

| Domain | Scope |
|--------|-------|
| **Messaging Adapters** | Channel adapter framework + WhatsApp, Telegram, Slack, Discord adapters |
| **Memory System** | Hybrid vector + BM25 + structured memory with compaction |
| **Skill Marketplace** | OCCPHub skill registry, submission pipeline, install flow |
| **Plugin System** | TypeScript/Python plugin host with sandboxed execution |
| **Cron & Webhooks** | Scheduled task execution + inbound webhook framework |
| **Browser Automation** | Playwright-based adapter with sandbox isolation |
| **Agent-to-Agent Comms** | Session tools: spawn, send, list, history |
| **MCP Native Client** | Full MCP protocol client (not just configurator) |
| **Enhanced Memory** | Vector + BM25 hybrid search, daily compaction, cross-session persistence |
| **Canvas/A2UI** | Agent-generated interactive UI workspace |
| **Multi-Tenant Isolation** | Org-scoped data isolation with tenant-aware RBAC |
| **Compliance Dashboards** | SOC2/HIPAA/GDPR/EU AI Act compliance status views |
| **SIEM Integration** | Structured audit event export (CEF/LEEF/JSON) |
| **SDK Streaming** | Server-Sent Events for real-time pipeline progress |

### Out of Scope (v1.0)

| Exclusion | Rationale |
|-----------|-----------|
| Voice/TTS/STT | Hardware-dependent; defer to v1.1+ |
| Device control (camera, GPS) | Mobile-only concern; not enterprise priority |
| iMessage adapter | Apple ecosystem lock-in; community contribution path |
| Signal adapter | Encryption complexity; community contribution path |
| Visual pipeline builder (drag-and-drop) | High UX investment; defer to v1.2 |
| Self-hosted model inference (Ollama) | Infra complexity; document integration path only |
| Mobile native app | Web-first; PWA sufficient for v1.0 |

---

## Non-Goals

1. **Replace OpenClaw as a personal assistant** — OCCP is an enterprise control plane, not a consumer chatbot runtime. Personal use is a side-effect, not a target.
2. **Vendor lock-in** — All integrations use open protocols (MCP, WebSocket, REST). No proprietary wire formats.
3. **Feature parity with OpenClaw** — Cherry-pick high-value features that align with governance model. Skip consumer-only features (voice, device control).
4. **Breaking VAP architecture** — Every new feature MUST pass through the Verified Autonomy Pipeline. No bypass paths.
5. **Abandoning Python backend** — The API/orchestrator remains Python (FastAPI). New adapters may be polyglot but core stays Python.

---

## Key Success Criteria

| ID | Criterion | Measurement | Target |
|----|-----------|-------------|--------|
| KSC-01 | All messaging adapters policy-gated | Every inbound/outbound message traverses VAP gate | 100% |
| KSC-02 | Skill marketplace operational | OCCPHub serves installable skills with supply-chain verification | ≥50 skills at launch |
| KSC-03 | Memory system hybrid search | Vector + BM25 retrieval with <200ms p95 latency | p95 < 200ms |
| KSC-04 | Audit chain integrity under load | SHA-256 chain verification passes under 100 concurrent pipelines | 0 chain breaks |
| KSC-05 | Multi-tenant data isolation | Org A cannot read Org B data via any API path | 0 cross-tenant leaks |
| KSC-06 | EU AI Act Art. 19 compliance | Audit retention, human oversight, risk classification operational | Full compliance |
| KSC-07 | MCP native client functional | Execute MCP tool calls through VAP pipeline with policy gating | ≥10 MCP servers tested |
| KSC-08 | Test coverage maintained | Unit + integration test coverage | ≥85% |
| KSC-09 | Zero critical CVEs at release | Snyk + Semgrep + GitGuardian clean | 0 critical/high |
| KSC-10 | Sub-5-minute onboarding | New user: install → first pipeline run | <5 min |

---

## Dependencies

### Internal Dependencies

| Dependency | Owner | Status | Risk |
|------------|-------|--------|------|
| FastAPI async pipeline | `orchestrator/` | Stable (v0.8.2) | Low |
| SQLAlchemy 2.0 async ORM | `store/` | Stable | Low |
| Casbin RBAC | `api/rbac.py` | Stable | Low |
| AES-256-GCM encryption | `security/encryption.py` | Stable | Low |
| Policy engine + guards | `policy_engine/` | Stable | Low |
| SHA-256 audit chain | `policy_engine/engine.py` | Stable | Low |
| Next.js 14 dashboard | `dash/` | Stable | Medium (major UI additions) |
| Python + TypeScript SDKs | `sdk/` | Stable | Medium (streaming additions) |
| Docker compose deployment | `docker-compose.yml` | Stable | Low |

### External Dependencies

| Dependency | Version | Purpose | Risk |
|------------|---------|---------|------|
| Python | 3.11+ | Runtime | Low |
| Node.js | 18+ | Dashboard + TS SDK | Low |
| SQLite / PostgreSQL | 3.x / 15+ | Database | Low |
| Anthropic API | Latest | Claude planner | Medium (API changes) |
| OpenAI API | Latest | GPT planner | Medium |
| Playwright | 1.40+ | Browser automation | Low |
| Baileys | 6.x | WhatsApp adapter | High (unofficial API) |
| grammY | 1.x | Telegram adapter | Low (official Bot API) |
| discord.js | 14.x | Discord adapter | Low |
| Slack Bolt | 3.x | Slack adapter | Low |
| chromadb / qdrant | Latest | Vector memory | Medium |
| sentence-transformers | Latest | Embedding model | Medium |
| MCP SDK | 1.x | MCP client | Low (Anthropic maintained) |

### Infrastructure Dependencies

| Dependency | Purpose | Risk |
|------------|---------|------|
| Hetzner VPS (195.201.238.144) | Production host | Low |
| GitHub Actions CI | 6-check pipeline | Low |
| Let's Encrypt | SSL certificates | Low |
| Hostinger DNS | Domain management | Low |
| Docker Hub | Image registry | Low |
