# CROSS-REFERENCE.md — OCCP v1.0 "Agent Control Plane"

**Version:** 2.0.0 | **Date:** 2026-02-27
**Total Requirements:** 72 across 19 categories

---

## Table 1: REQ-ID → Owner Module

| REQ-ID | Short Name | Owner Module |
|--------|-----------|--------------|
| REQ-GOV-01 | VAP Lifecycle Enforcement | `orchestrator/pipeline.py` |
| REQ-GOV-02 | Policy-as-Code Engine | `policy_engine/engine.py` |
| REQ-GOV-03 | Non-Bypassable Policy Evaluation | `policy_engine/engine.py`, `adapters/policy_gate.py` |
| REQ-GOV-04 | Break-Glass Protocol | `security/break_glass.py` |
| REQ-GOV-05 | Agent Boundary Enforcement | `policy_engine/agent_boundary.py` |
| REQ-GOV-06 | Trust Level Declaration & Enforcement | `policy_engine/trust_levels.py` |
| REQ-POL-01 | ABAC + RBAC Hybrid Model | `policy_engine/abac.py` |
| REQ-POL-02 | Policy Decision Audit | `policy_engine/engine.py` |
| REQ-POL-03 | Testable Policies | `cli/policy_test.py` |
| REQ-CPC-01 | SLSA Provenance | `security/provenance.py` |
| REQ-CPC-02 | Artifact Signing | `security/signing.py` |
| REQ-CPC-03 | Runtime Signature Verification | `security/supply_chain.py` |
| REQ-CPC-04 | Revocation Framework | `security/revocation.py` |
| REQ-TSF-01 | Private-First Registry | `api/routes/skills.py` |
| REQ-TSF-02 | Capability Declaration Schema | `orchestrator/skill_manifest.py` |
| REQ-TSF-03 | Mandatory SBOM | `security/sbom.py` |
| REQ-TSF-04 | Version Pinning | `cli/skills.py` |
| REQ-TSF-05 | Automated Scan Pipeline | `.github/workflows/skill-scan.yml` |
| REQ-VSTA-01 | VAP-Enforced Scheduled Jobs | `orchestrator/cron.py` |
| REQ-VSTA-02 | Policy Template Profiles | `policy_engine/profiles.py` |
| REQ-VSTA-03 | Budget Guard | `policy_engine/budget_guard.py` |
| REQ-VSTA-04 | Time-Bound Execution | `orchestrator/scheduler.py` |
| REQ-MAO-01 | Worker Sandbox Isolation | `orchestrator/session_tools.py` |
| REQ-MAO-02 | Configurable Recursion Depth | `orchestrator/session_tools.py` |
| REQ-MAO-03 | Cascade Stop | `orchestrator/session_tools.py` |
| REQ-MAO-04 | Deterministic Merge Contract | `orchestrator/merge.py` |
| REQ-MAO-05 | Proof-Carrying Outputs | `orchestrator/proof.py` |
| REQ-CBDB-01 | Isolated Browser Profile | `adapters/browser_adapter.py` |
| REQ-CBDB-02 | Domain Allow/Deny List | `policy_engine/browser_policy.py` |
| REQ-CBDB-03 | Form Submission Approval | `policy_engine/browser_policy.py` |
| REQ-CBDB-04 | Download Restrictions | `adapters/browser_adapter.py` |
| REQ-CBDB-05 | Browser Interaction Audit | `adapters/browser_adapter.py` |
| REQ-MCP-01 | Enterprise MCP Registry | `config/mcp_registry.py` |
| REQ-MCP-02 | Scope-Based Consent | `api/routes/mcp.py` |
| REQ-MCP-03 | Governed MCP Dependency | `security/supply_chain.py` |
| REQ-MCP-04 | Runtime Scope Enforcement | `adapters/mcp_client.py` |
| REQ-RT-01 | Automated Injection Test Suite | `tests/red_team/injection.py` |
| REQ-RT-02 | Tool Poisoning Simulation | `tests/red_team/tool_poisoning.py` |
| REQ-RT-03 | Data Exfiltration Tests | `tests/red_team/exfiltration.py` |
| REQ-RT-04 | Excessive Agency Detection | `policy_engine/anomaly_detector.py` |
| REQ-RT-05 | Regression Scoreboard | `.github/workflows/red-team.yml` |
| REQ-CHAN-01 | Channel Adapter Protocol | `adapters/channels/base.py` |
| REQ-CHAN-02 | WhatsApp Adapter | `adapters/channels/whatsapp.py` |
| REQ-CHAN-03 | Telegram Adapter | `adapters/channels/telegram.py` |
| REQ-CHAN-04 | Slack Adapter | `adapters/channels/slack.py` |
| REQ-CHAN-05 | Discord Adapter | `adapters/channels/discord.py` |
| REQ-MEM-01 | Hybrid Memory Retrieval | `store/memory/hybrid.py` |
| REQ-MEM-02 | Memory Compaction | `store/memory/compactor.py` |
| REQ-MEM-03 | Cross-Session Knowledge | `store/memory/knowledge.py` |
| REQ-A2UI-01 | Agent Canvas Workspace | `dash/src/app/canvas/`, `api/routes/canvas.py` |
| REQ-SEC-01 | ML-Based Injection Detection | `policy_engine/ml_classifier.py` |
| REQ-SEC-02 | Security Audit CLI | `cli/security_audit.py` |
| REQ-SEC-03 | Credential Vault | `security/vault.py` |
| REQ-SEC-04 | Adaptive Rate Throttling | `policy_engine/rate_limiter.py` |
| REQ-SEC-05 | Cost Anomaly Detection | `policy_engine/cost_anomaly.py` |
| REQ-SEC-06 | Merkle Root Audit Verification | `store/audit_merkle.py` |
| REQ-COMP-01 | Framework Mapping Dashboard | `dash/src/app/compliance/` |
| REQ-COMP-02 | SIEM/SOAR Integration | `security/siem_export.py` |
| REQ-SDK-01 | SSE Streaming | `sdk/python/client.py`, `sdk/typescript/src/client.ts` |
| REQ-SDK-02 | OCCP as MCP Server | `sdk/mcp_server/` |
| REQ-MARKET-01 | OCCPHub Registry | `cli/skills.py`, `api/routes/hub.py` |
| REQ-MARKET-02 | Plugin System | `orchestrator/plugins.py` |
| REQ-AUTO-01 | Cron Scheduler | `orchestrator/cron.py` |
| REQ-AUTO-02 | Webhook Receiver | `api/routes/webhooks.py` |
| REQ-AUTO-03 | Event Triggers | `orchestrator/triggers.py` |
| REQ-AUTO-04 | Workflow Templates | `orchestrator/workflows.py` |
| REQ-CORE-01 | Message Pipeline | `orchestrator/message_pipeline.py` |
| REQ-CORE-02 | Session Management | `orchestrator/sessions.py` |
| REQ-CORE-03 | Config-First Agent Definition | `orchestrator/config_loader.py` |
| REQ-CORE-04 | Local Model Support (Ollama) | `adapters/ollama_planner.py` |
| REQ-MULTI-01 | Org-Scoped Data Isolation | `store/tenant.py`, `api/middleware.py` |
| REQ-MULTI-02 | Data Residency Controls | `config/residency.py` |

---

## Table 2: REQ-ID → Phase

| REQ-ID | Phase | Version | Phase Name |
|--------|-------|---------|------------|
| REQ-GOV-01 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-GOV-02 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-GOV-03 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-GOV-04 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-POL-01 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-POL-02 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-POL-03 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-SEC-01 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-SEC-02 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-SEC-03 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-SEC-04 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-GOV-06 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-CORE-01 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-CORE-02 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-CORE-03 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-CORE-04 | 1 | v0.9.0 | Governance Core Hardening |
| REQ-CPC-01 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-CPC-02 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-CPC-03 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-CPC-04 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-TSF-01 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-TSF-02 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-TSF-03 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-TSF-04 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-TSF-05 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-SEC-06 | 2 | v0.9.1 | Provenance & Supply Chain |
| REQ-MEM-01 | 3 | v0.9.2 | Memory & Knowledge System |
| REQ-MEM-02 | 3 | v0.9.2 | Memory & Knowledge System |
| REQ-MEM-03 | 3 | v0.9.2 | Memory & Knowledge System |
| REQ-CHAN-01 | 4 | v0.9.3 | Channel Adapter Framework |
| REQ-CHAN-02 | 4 | v0.9.3 | Channel Adapter Framework |
| REQ-CHAN-03 | 4 | v0.9.3 | Channel Adapter Framework |
| REQ-CHAN-04 | 4 | v0.9.3 | Channel Adapter Framework |
| REQ-CHAN-05 | 4 | v0.9.3 | Channel Adapter Framework |
| REQ-A2UI-01 | 4 | v0.9.3 | Channel Adapter Framework |
| REQ-VSTA-01 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-VSTA-02 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-VSTA-03 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-VSTA-04 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-AUTO-01 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-AUTO-02 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-AUTO-03 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-SEC-05 | 5 | v0.9.4 | Verified Scheduler & Automation |
| REQ-MAO-01 | 6 | v0.9.5 | Multi-Agent Orchestrator |
| REQ-MAO-02 | 6 | v0.9.5 | Multi-Agent Orchestrator |
| REQ-MAO-03 | 6 | v0.9.5 | Multi-Agent Orchestrator |
| REQ-MAO-04 | 6 | v0.9.5 | Multi-Agent Orchestrator |
| REQ-MAO-05 | 6 | v0.9.5 | Multi-Agent Orchestrator |
| REQ-CBDB-01 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-CBDB-02 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-CBDB-03 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-CBDB-04 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-CBDB-05 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-MCP-01 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-MCP-02 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-MCP-03 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-MCP-04 | 7 | v0.9.6 | Controlled Browser & MCP Client |
| REQ-MARKET-01 | 8 | v0.9.7 | Marketplace & Plugin System |
| REQ-MARKET-02 | 8 | v0.9.7 | Marketplace & Plugin System |
| REQ-SDK-01 | 8 | v0.9.7 | Marketplace & Plugin System |
| REQ-SDK-02 | 8 | v0.9.7 | Marketplace & Plugin System |
| REQ-GOV-05 | 8 | v0.9.7 | Marketplace & Plugin System |
| REQ-COMP-02 | 8 | v0.9.7 | Marketplace & Plugin System |
| REQ-AUTO-04 | 8 | v0.9.7 | Marketplace & Plugin System |
| REQ-MULTI-01 | 9 | v0.9.8 | Multi-Tenancy & Compliance |
| REQ-MULTI-02 | 9 | v0.9.8 | Multi-Tenancy & Compliance |
| REQ-COMP-01 | 9 | v0.9.8 | Multi-Tenancy & Compliance |
| REQ-SEC-03* | 9 | v0.9.8 | Multi-Tenancy & Compliance |
| REQ-RT-01 | 10 | v1.0.0 | Red-Team & Release |
| REQ-RT-02 | 10 | v1.0.0 | Red-Team & Release |
| REQ-RT-03 | 10 | v1.0.0 | Red-Team & Release |
| REQ-RT-04 | 10 | v1.0.0 | Red-Team & Release |
| REQ-RT-05 | 10 | v1.0.0 | Red-Team & Release |

*REQ-SEC-03 appears in Phase 1 (initial vault) and Phase 9 (multi-org extension).
*REQ-AUTO-03 appears in Phase 5 (Event Triggers implementation) only. REQ-AUTO-04 (Workflow Templates) is a separate requirement in Phase 8.

---

## Table 3: REQ-ID → Acceptance Test Summary

| REQ-ID | Key Acceptance Test |
|--------|-------------------|
| REQ-GOV-01 | Fuzz test: 10,000 calls → 0 VAP bypass |
| REQ-GOV-02 | Policy change requires git commit; decision includes policy version hash |
| REQ-GOV-03 | Plugin direct tool call → blocked + audit; no code path skips PolicyGate.evaluate() |
| REQ-GOV-04 | Single admin cannot activate break-glass alone; token auto-expires |
| REQ-GOV-05 | Fuzz: 1,000 cross-boundary calls → 0 bypass; boundary violation → DENY + audit |
| REQ-GOV-06 | Fuzz: 5,000 cross-level calls → 0 bypass; L1 agent browser → blocked; L5 child spawns at L4 |
| REQ-POL-01 | Time-based ABAC rule enforced (operator + business hours) |
| REQ-POL-02 | Every ALLOW/DENY produces audit entry with policy SHA-256 |
| REQ-POL-03 | `occp policy test` runs fixtures; CI blocks on failure |
| REQ-CPC-01 | Skill without SLSA provenance → rejected at install |
| REQ-CPC-02 | `cosign verify` passes; tampered artifact rejected at load |
| REQ-CPC-03 | Modified skill file on disk → load failure + alert |
| REQ-CPC-04 | Revoked skill blocked within 5-minute polling cycle |
| REQ-TSF-01 | Fresh install has empty registry; OCCPHub opt-in only |
| REQ-TSF-02 | Skill declaring network scope blocked from undeclared domains |
| REQ-TSF-03 | `occp skill info --sbom` displays dependency tree; license violations flagged |
| REQ-TSF-04 | `@latest` in production → error; `skills.lock` required |
| REQ-TSF-05 | Hardcoded API key → rejected; vulnerable dependency → rejected |
| REQ-VSTA-01 | Cron job creates Task with `source=cron`; passes all 5 VAP stages |
| REQ-VSTA-02 | `profile=strict` activates all guards; profile YAML version-controlled |
| REQ-VSTA-03 | Job terminated at token budget limit; 80% warning threshold |
| REQ-VSTA-04 | Timeout kills job; graceful SIGTERM → 10s → SIGKILL |
| REQ-MAO-01 | Worker cannot read parent state; container destroyed on completion |
| REQ-MAO-02 | Agent at depth 3 spawn → blocked; depth violation severity=HIGH |
| REQ-MAO-03 | Parent failure → child stop within 5s; graceful shutdown first |
| REQ-MAO-04 | Consensus merge: 3 agents, 2 agreeing required |
| REQ-MAO-05 | Output without proof chain → rejected by receiver; chain independently verifiable |
| REQ-CBDB-01 | Session A cookies invisible to Session B; profile destroyed in 10s |
| REQ-CBDB-02 | Non-allowlisted domain → blocked + audit; wildcard patterns supported |
| REQ-CBDB-03 | Form submit without approval flag → blocked; PII redacted in audit |
| REQ-CBDB-04 | .exe blocked by default; >50MB blocked; downloads scanned |
| REQ-CBDB-05 | Every navigation → audit entry; form submission includes screenshot |
| REQ-MCP-01 | Private registry serves catalog; unapproved servers blocked |
| REQ-MCP-02 | Connection without consent → blocked; consent revocable per-org |
| REQ-MCP-03 | Install triggers scan; version pinned in mcp.lock; health check 60s |
| REQ-MCP-04 | Out-of-scope tool call → blocked + audit; scope violation alert |
| REQ-RT-01 | ≥100 injection payloads; all blocked; new bypass → added in 24h |
| REQ-RT-02 | Poisoned tool result stripped; exfiltration URL blocked |
| REQ-RT-03 | PII to external URL → blocked; paste-bin exfil → blocked |
| REQ-RT-04 | 10+ tools/turn → flagged; 3x avg tokens → throttled |
| REQ-RT-05 | Scoreboard in CI; <95% detection → CI failure |
| REQ-CHAN-01 | New adapter in <200 LOC; failure triggers reconnect; events in audit |
| REQ-CHAN-02 | QR pairing; text/image/doc normalized; session persists restart |
| REQ-CHAN-03 | Webhook mode; inline keyboards; files to sandbox |
| REQ-CHAN-04 | `/occp run` triggers VAP; thread replies maintain session |
| REQ-CHAN-05 | Discord roles → OCCP roles; DM sessions isolated |
| REQ-MEM-01 | Semantic + keyword retrieval; fusion p95 <200ms |
| REQ-MEM-02 | 24h+ conversations compacted; storage reduced ≥60% |
| REQ-MEM-03 | Agent A writes fact → Agent B retrieves cross-session; entries versioned |
| REQ-A2UI-01 | HTML via WebSocket renders; iframe sandbox; policy-gated default-off |
| REQ-SEC-01 | Zero regression; ≥3 novel attacks caught; <50ms p95 |
| REQ-SEC-02 | Checks ≥15 items; `--deep` probes endpoints; exit code 1 if critical |
| REQ-SEC-03 | Rotation without downtime; per-org isolation; every decrypt audited |
| REQ-SEC-04 | 3σ deviation → throttle within 500ms; rate limits per trust level; operator override |
| REQ-SEC-05 | 5x baseline → CRITICAL alert within 60s; 10x → auto-kill; 90-day retention |
| REQ-SEC-06 | `occp audit verify` validates chain; tampered entry detected; root every 1K entries or 1h |
| REQ-COMP-01 | SOC2 CC6.1-CC9.9 mapped; controls link to audit; PDF export |
| REQ-COMP-02 | CEF via syslog within 1s; Splunk CIM validated; webhook retry |
| REQ-SDK-01 | Python yields typed events; TypeScript AsyncIterator; auto-reconnect |
| REQ-SDK-02 | Claude Desktop discovers OCCP; tool calls through VAP; MCP session auth |
| REQ-MARKET-01 | `occp skill publish` uploads; auto scan; search + version pinning |
| REQ-MARKET-02 | Plugin auto-discovered; crash isolation; API version-pinned |
| REQ-AUTO-01 | `occp cron add` works; tasks through VAP; all executions audited |
| REQ-AUTO-02 | Valid HMAC accepted; invalid → 403; failed retried 3x |
| REQ-AUTO-03 | Trigger fires <500ms; YAML definitions; non-blocking eval |
| REQ-AUTO-04 | ≥5 templates; `occp workflow init` creates configured workflow; signed templates verified |
| REQ-CORE-01 | 4 channels → identical InboundMessage; full audit per message |
| REQ-CORE-02 | Group can't invoke main-only tools; DM state invisible cross-DM |
| REQ-CORE-03 | AGENT.md auto-registers; edit updates <5s; schema validated |
| REQ-CORE-04 | Connects localhost:11434; fallback on failure; responses pass guards |
| REQ-MULTI-01 | Org A → 403 on Org B; direct DB query zero cross-org rows; pen test |
| REQ-MULTI-02 | EU org → EU endpoints only; residency immutable post-creation |

---

## Table 4: Module → Risks

| Module | Owner Path | Risk Level | Risk Description | Mitigating REQs |
|--------|-----------|------------|------------------|-----------------|
| **orchestrator/pipeline.py** | Core VAP | Low | Well-tested v0.8.2 foundation | REQ-GOV-01, REQ-GOV-03 |
| **policy_engine/engine.py** | Policy core | Medium | ABAC extension adds complexity to existing Casbin | REQ-POL-01, REQ-POL-02, REQ-POL-03 |
| **policy_engine/abac.py** | ABAC (new) | Medium | New module; must integrate without breaking RBAC | REQ-POL-01 |
| **policy_engine/ml_classifier.py** | ML injection (new) | High | Latency risk; model training data quality | REQ-SEC-01 |
| **policy_engine/anomaly_detector.py** | Anomaly (new) | High | Baseline behavior model accuracy; false positive rate | REQ-RT-04 |
| **policy_engine/budget_guard.py** | Budget (new) | Low | Straightforward token counting | REQ-VSTA-03 |
| **policy_engine/browser_policy.py** | Browser policy (new) | Medium | Domain matching complexity; bypass via redirects | REQ-CBDB-02, REQ-CBDB-03 |
| **policy_engine/profiles.py** | Profiles (new) | Low | Configuration-only; no runtime logic | REQ-VSTA-02 |
| **security/provenance.py** | SLSA (new) | Medium | SLSA spec complexity; build system integration | REQ-CPC-01 |
| **security/signing.py** | Signing (new) | Medium | Key management; Sigstore dependency | REQ-CPC-02 |
| **security/supply_chain.py** | Supply chain | Low | Extends existing scanner | REQ-CPC-03, REQ-MCP-03 |
| **security/revocation.py** | Revocation (new) | Medium | Distributed consistency; network partition handling | REQ-CPC-04 |
| **security/vault.py** | Vault (new) | High | Crypto key management; must not leak keys | REQ-SEC-03 |
| **security/siem_export.py** | SIEM (new) | Low | Standard CEF/syslog; well-documented | REQ-COMP-02 |
| **security/sbom.py** | SBOM (new) | Low | CycloneDX generation; tooling mature | REQ-TSF-03 |
| **security/break_glass.py** | Break-glass (new) | High | Emergency bypass must be bulletproof; time-limited | REQ-GOV-04 |
| **adapters/channels/base.py** | Channel protocol (new) | Medium | Protocol design affects all adapters | REQ-CHAN-01 |
| **adapters/channels/whatsapp.py** | WhatsApp (new) | High | Baileys unofficial API; frequent breaking changes | REQ-CHAN-02 |
| **adapters/channels/telegram.py** | Telegram (new) | Low | Official Bot API; grammY stable | REQ-CHAN-03 |
| **adapters/channels/slack.py** | Slack (new) | Low | Bolt framework; official SDK | REQ-CHAN-04 |
| **adapters/channels/discord.py** | Discord (new) | Low | discord.js stable; good docs | REQ-CHAN-05 |
| **adapters/browser_adapter.py** | Browser (new) | High | Sandbox escape risk; Playwright dependency | REQ-CBDB-01, REQ-CBDB-04, REQ-CBDB-05 |
| **adapters/mcp_client.py** | MCP client (new) | Medium | MCP protocol evolving; scope enforcement complexity | REQ-MCP-04 |
| **adapters/ollama_planner.py** | Ollama (new) | Low | Simple HTTP client; circuit breaker pattern | REQ-CORE-04 |
| **store/memory/hybrid.py** | Memory hybrid (new) | High | Vector DB + BM25 fusion tuning; latency target | REQ-MEM-01 |
| **store/memory/compactor.py** | Compactor (new) | Medium | Summarization quality; data loss risk | REQ-MEM-02 |
| **store/memory/knowledge.py** | Knowledge (new) | Medium | Cross-session consistency; RBAC on writes | REQ-MEM-03 |
| **store/tenant.py** | Multi-tenant (new) | Critical | Data isolation failure = security breach | REQ-MULTI-01 |
| **config/mcp_registry.py** | MCP registry (new) | Medium | Registry sync; caching strategy | REQ-MCP-01 |
| **config/residency.py** | Residency (new) | High | Immutable routing; EU compliance impact | REQ-MULTI-02 |
| **orchestrator/cron.py** | Cron (new) | Medium | VAP integration for unattended execution | REQ-VSTA-01, REQ-AUTO-01 |
| **orchestrator/scheduler.py** | Scheduler (new) | Low | Timeout + cleanup; well-understood patterns | REQ-VSTA-04 |
| **orchestrator/session_tools.py** | Session tools | Medium | Multi-agent isolation; resource tracking | REQ-MAO-01, REQ-MAO-02, REQ-MAO-03 |
| **orchestrator/merge.py** | Merge (new) | High | Consensus algorithm; determinism guarantee | REQ-MAO-04 |
| **orchestrator/proof.py** | Proof chain (new) | High | Cryptographic correctness; verification cost | REQ-MAO-05 |
| **orchestrator/plugins.py** | Plugin host (new) | High | Crash isolation; hot-loading safety | REQ-MARKET-02 |
| **orchestrator/message_pipeline.py** | Message pipeline (new) | Medium | Normalization across 4+ channel formats | REQ-CORE-01 |
| **orchestrator/sessions.py** | Sessions (new) | Medium | State isolation; tool scoping per session type | REQ-CORE-02 |
| **orchestrator/config_loader.py** | Config loader (new) | Low | YAML/Markdown parsing; schema validation | REQ-CORE-03 |
| **orchestrator/triggers.py** | Triggers (new) | Medium | Event matching; <500ms latency target | REQ-AUTO-03 |
| **orchestrator/workflows.py** | Workflows (new) | Medium | YAML workflow engine; deterministic execution | REQ-AUTO-04 |
| **policy_engine/agent_boundary.py** | Agent boundary (new) | High | Capability enforcement; privilege escalation prevention | REQ-GOV-05 |
| **policy_engine/trust_levels.py** | Trust levels (new) | High | L0–L5 enforcement; cross-level bypass prevention | REQ-GOV-06 |
| **policy_engine/rate_limiter.py** | Rate limiter (new) | Medium | Adaptive throttling; baseline accuracy; false positive rate | REQ-SEC-04 |
| **policy_engine/cost_anomaly.py** | Cost anomaly (new) | High | Real-time cost tracking; anomaly model accuracy; auto-kill safety | REQ-SEC-05 |
| **store/audit_merkle.py** | Merkle audit (new) | High | Cryptographic correctness; root publication reliability | REQ-SEC-06 |
| **api/routes/webhooks.py** | Webhooks (new) | Medium | HMAC verification; replay attack prevention | REQ-AUTO-02 |
| **api/routes/mcp.py** | MCP routes (new) | Medium | Consent flow; scope management | REQ-MCP-02 |
| **api/routes/hub.py** | Hub routes (new) | Medium | Registry API; search ranking | REQ-MARKET-01 |
| **api/routes/canvas.py** | Canvas routes (new) | Low | WebSocket push; iframe security | REQ-A2UI-01 |
| **api/middleware.py** | Middleware | Medium | Tenant injection; org-scoping all queries | REQ-MULTI-01 |
| **cli/policy_test.py** | Policy test (new) | Low | Test runner; fixture format | REQ-POL-03 |
| **cli/security_audit.py** | Security audit (new) | Medium | ≥15 check items; accuracy of findings | REQ-SEC-02 |
| **cli/skills.py** | Skills CLI (new) | Low | Package manager CLI; well-understood patterns | REQ-TSF-04, REQ-MARKET-01 |
| **sdk/mcp_server/** | MCP server (new) | Medium | MCP protocol compliance; VAP passthrough | REQ-SDK-02 |
| **dash/src/app/compliance/** | Compliance UI (new) | Medium | Framework mapping accuracy; evidence linking | REQ-COMP-01 |
| **dash/src/app/canvas/** | Canvas UI (new) | Low | iframe sandbox; WebSocket render | REQ-A2UI-01 |
| **tests/red_team/** | Red-team suite (new) | Medium | Payload coverage; detection rate maintenance | REQ-RT-01 to REQ-RT-05 |
| **.github/workflows/** | CI pipelines | Low | Extends existing 6-check pipeline | REQ-TSF-05, REQ-RT-05 |

---

## Summary Statistics

| Dimension | Count |
|-----------|-------|
| Total REQ-IDs | 72 |
| Owner Modules (unique) | 54 |
| New Modules (not in v0.8.2) | 45 |
| Critical Risk Modules | 1 (store/tenant.py) |
| High Risk Modules | 14 |
| Medium Risk Modules | 24 |
| Low Risk Modules | 15 |
| Phases | 10 |
| Phase with most REQs | Phase 1 (16 REQs) |
| Phase with fewest REQs | Phase 3 (3 REQs) |
