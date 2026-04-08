# ROADMAP.md — OCCP v1.0 "Agent Control Plane"

**Version:** 2.0.0 | **Date:** 2026-02-27
**Baseline:** v0.8.2 (current production)

---

## Phase Overview

| Phase | Name | Target Version | Duration | REQ Count | Status |
|-------|------|---------------|----------|-----------|--------|
| 1 | Governance Core Hardening | v0.9.0 | 3 weeks | 16 | NOT STARTED |
| 2 | Provenance & Supply Chain | v0.9.1 | 2 weeks | 10 | NOT STARTED |
| 3 | Memory & Knowledge System | v0.9.2 | 2 weeks | 3 | NOT STARTED |
| 4 | Channel Adapter Framework | v0.9.3 | 3 weeks | 6 | NOT STARTED |
| 5 | Verified Scheduler & Automation | v0.9.4 | 2 weeks | 8 | NOT STARTED |
| 6 | Multi-Agent Orchestrator | v0.9.5 | 3 weeks | 5 | NOT STARTED |
| 7 | Controlled Browser & MCP Client | v0.9.6 | 2 weeks | 9 | NOT STARTED |
| 8 | Marketplace & Plugin System | v0.9.7 | 3 weeks | 7 | NOT STARTED |
| 9 | Multi-Tenancy & Compliance | v0.9.8 | 3 weeks | 4 | NOT STARTED |
| 10 | Red-Team & Release | v1.0.0 | 2 weeks | 5 | NOT STARTED |

**Total duration estimate:** 25 weeks (~6 months)
**Total requirements:** 72 (mapped below)

---

## Phase 1: Governance Core Hardening (v0.9.0)

**Goal:** Harden the governance foundation. Existing v0.8.2 features upgraded to production-grade.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-GOV-01 | VAP Lifecycle Enforcement | Medium |
| REQ-GOV-02 | Policy-as-Code Engine | High |
| REQ-GOV-03 | Non-Bypassable Policy Evaluation | High |
| REQ-GOV-04 | Break-Glass Protocol | Medium |
| REQ-POL-01 | ABAC + RBAC Hybrid Model | High |
| REQ-POL-02 | Policy Decision Audit | Medium |
| REQ-POL-03 | Testable Policies | Medium |
| REQ-SEC-01 | ML-Based Injection Detection | High |
| REQ-SEC-02 | Security Audit CLI | Medium |
| REQ-SEC-03 | Credential Vault | High |
| REQ-SEC-04 | Adaptive Rate Throttling | Medium |
| REQ-GOV-06 | Trust Level Declaration & Enforcement | High |
| REQ-CORE-01 | Message Pipeline | High |
| REQ-CORE-02 | Session Management | High |
| REQ-CORE-03 | Config-First Agent Definition | Medium |
| REQ-CORE-04 | Local Model Support (Ollama) | Low |

### Acceptance Gates

- [ ] All VAP stages enforce non-bypass (fuzz test: 10,000 calls, 0 bypass)
- [ ] ABAC policy rules functional alongside existing RBAC
- [ ] Policy test CLI passes on all production policies
- [ ] ML injection classifier deployed with <50ms p95
- [ ] `occp security audit` checks ≥15 items
- [ ] Credential vault operational with per-org isolation
- [ ] Message pipeline processes 4 channel types
- [ ] Session management with main/DM/group tiers
- [ ] Config-first agent definition functional
- [ ] Trust level enforcement: L1 agent browser access → blocked (fuzz: 5,000 calls, 0 bypass)
- [ ] Adaptive rate throttling: 3σ deviation → throttle within 500ms
- [ ] Test coverage ≥85%

---

## Phase 2: Provenance & Supply Chain (v0.9.1)

**Goal:** Establish cryptographic trust chain for all artifacts.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-CPC-01 | SLSA Provenance | High |
| REQ-CPC-02 | Artifact Signing | Medium |
| REQ-CPC-03 | Runtime Signature Verification | Medium |
| REQ-CPC-04 | Revocation Framework | Medium |
| REQ-TSF-01 | Private-First Registry | Medium |
| REQ-TSF-02 | Capability Declaration Schema | Medium |
| REQ-TSF-03 | Mandatory SBOM | Low |
| REQ-TSF-04 | Version Pinning | Low |
| REQ-TSF-05 | Automated Scan Pipeline | Medium |
| REQ-SEC-06 | Merkle Root Audit Verification | High |

### Acceptance Gates

- [ ] Unsigned artifact load blocked (100% enforcement)
- [ ] Revoked artifact blocked within 5-minute polling cycle
- [ ] Private registry operational without external network
- [ ] Capability declaration schema validated on all skills
- [ ] SBOM generated for all published skills
- [ ] Version pinning enforced in production mode
- [ ] Scan pipeline: Semgrep + Snyk + GitGuardian pass required
- [ ] Merkle root audit verification: `occp audit verify` validates chain integrity

---

## Phase 3: Memory & Knowledge System (v0.9.2)

**Goal:** Implement persistent, searchable agent memory with governance.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-MEM-01 | Hybrid Memory Retrieval | High |
| REQ-MEM-02 | Memory Compaction | Medium |
| REQ-MEM-03 | Cross-Session Knowledge | Medium |

### Acceptance Gates

- [ ] Vector + BM25 fusion retrieval p95 <200ms
- [ ] Memory compaction reduces storage ≥60%
- [ ] Cross-session knowledge shared with RBAC enforcement
- [ ] Memory writes produce audit trail entries
- [ ] Memory search results policy-filtered (no cross-org leaks)

---

## Phase 4: Channel Adapter Framework (v0.9.3)

**Goal:** Enable messaging platform integration with governance.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-CHAN-01 | Channel Adapter Protocol | Medium |
| REQ-CHAN-02 | WhatsApp Adapter | High |
| REQ-CHAN-03 | Telegram Adapter | Medium |
| REQ-CHAN-04 | Slack Adapter | Medium |
| REQ-CHAN-05 | Discord Adapter | Medium |
| REQ-A2UI-01 | Agent Canvas Workspace | Medium |

### Acceptance Gates

- [ ] All 4 messaging adapters implement ChannelAdapter Protocol
- [ ] Messages from all channels pass through VAP pipeline
- [ ] WhatsApp QR pairing functional
- [ ] Slack slash commands trigger VAP pipeline
- [ ] Agent Canvas renders in sandboxed iframe
- [ ] All channel events in audit trail

---

## Phase 5: Verified Scheduler & Automation (v0.9.4)

**Goal:** Enable autonomous scheduled and event-driven agent execution.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-VSTA-01 | VAP-Enforced Scheduled Jobs | Medium |
| REQ-VSTA-02 | Policy Template Profiles | Medium |
| REQ-VSTA-03 | Budget Guard | Medium |
| REQ-VSTA-04 | Time-Bound Execution | Low |
| REQ-AUTO-01 | Cron Scheduler | Medium |
| REQ-AUTO-02 | Webhook Receiver | Medium |
| REQ-AUTO-03 | Event Triggers | Medium |
| REQ-SEC-05 | Cost Anomaly Detection | High |

### Acceptance Gates

- [ ] Cron job execution passes through full VAP
- [ ] Budget guard terminates job at limit
- [ ] Timeout kills stuck jobs gracefully
- [ ] Webhook HMAC-SHA256 verification functional
- [ ] Event triggers fire within 500ms
- [ ] Cost anomaly detection: 5x baseline → CRITICAL alert within 60s; 10x → auto-kill
- [ ] All scheduled/triggered executions in audit trail

---

## Phase 6: Multi-Agent Orchestrator (v0.9.5)

**Goal:** Enable governed multi-agent collaboration.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-MAO-01 | Worker Sandbox Isolation | High |
| REQ-MAO-02 | Configurable Recursion Depth | Low |
| REQ-MAO-03 | Cascade Stop | Medium |
| REQ-MAO-04 | Deterministic Merge Contract | High |
| REQ-MAO-05 | Proof-Carrying Outputs | High |

### Acceptance Gates

- [ ] Worker agents run in isolated sandbox containers
- [ ] Recursion depth enforced (blocked at limit)
- [ ] Parent failure cascades to all children within 30s
- [ ] Consensus merge with 3 agents functional
- [ ] Proof chain independently verifiable
- [ ] All multi-agent interactions in audit trail

---

## Phase 7: Controlled Browser & MCP Client (v0.9.6)

**Goal:** Enable governed browser automation and native MCP client.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-CBDB-01 | Isolated Browser Profile | Medium |
| REQ-CBDB-02 | Domain Allow/Deny List | Medium |
| REQ-CBDB-03 | Form Submission Approval | Low |
| REQ-CBDB-04 | Download Restrictions | Low |
| REQ-CBDB-05 | Browser Interaction Audit | Medium |
| REQ-MCP-01 | Enterprise MCP Registry | Medium |
| REQ-MCP-02 | Scope-Based Consent | Medium |
| REQ-MCP-03 | Governed MCP Dependency | Medium |
| REQ-MCP-04 | Runtime Scope Enforcement | Medium |

### Acceptance Gates

- [ ] Browser sessions isolated per Playwright BrowserContext
- [ ] Domain deny list blocks unauthorized navigation
- [ ] Form submission blocked without approval flag
- [ ] Downloads sandboxed and scanned
- [ ] Browser actions hash-chained in audit
- [ ] MCP client executes tool calls through VAP
- [ ] MCP scope enforcement blocks out-of-scope calls
- [ ] All MCP interactions in audit trail

---

## Phase 8: Marketplace & Plugin System (v0.9.7)

**Goal:** Enable ecosystem growth with governed extensibility.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-MARKET-01 | OCCPHub Registry | High |
| REQ-MARKET-02 | Plugin System | High |
| REQ-SDK-01 | SSE Streaming | Medium |
| REQ-SDK-02 | OCCP as MCP Server | Medium |
| REQ-GOV-05 | Agent Boundary Enforcement | Medium |
| REQ-COMP-02 | SIEM/SOAR Integration | Medium |
| REQ-AUTO-04 | Workflow Templates | Low |

### Acceptance Gates

- [ ] OCCPHub serves ≥50 skills at launch
- [ ] Plugin crash doesn't crash host process
- [ ] SSE streaming functional in both SDKs
- [ ] OCCP discoverable as MCP server from Claude Desktop
- [ ] Agent boundary violations produce audit entries
- [ ] Syslog CEF events received by SIEM within 1s
- [ ] ≥5 workflow templates available

---

## Phase 9: Multi-Tenancy & Compliance (v0.9.8)

**Goal:** Enterprise multi-tenant isolation and compliance dashboards.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-MULTI-01 | Org-Scoped Data Isolation | High |
| REQ-MULTI-02 | Data Residency Controls | High |
| REQ-COMP-01 | Framework Mapping Dashboard | High |
| REQ-SEC-03 | Credential Vault (multi-org) | Medium |

### Acceptance Gates

- [ ] Zero cross-tenant data leaks (penetration test)
- [ ] EU org routes LLM calls to EU endpoints only
- [ ] Compliance dashboard shows SOC2/HIPAA/GDPR/EU AI Act mapping
- [ ] PDF compliance report export functional
- [ ] Per-org credential vault isolation verified

---

## Phase 10: Red-Team & Release (v1.0.0)

**Goal:** Comprehensive security validation and v1.0 release.

### Requirements

| REQ-ID | Short Name | Complexity |
|--------|-----------|-----------|
| REQ-RT-01 | Automated Injection Test Suite | Medium |
| REQ-RT-02 | Tool Poisoning Simulation | Medium |
| REQ-RT-03 | Data Exfiltration Tests | Medium |
| REQ-RT-04 | Excessive Agency Detection | High |
| REQ-RT-05 | Regression Scoreboard | Medium |

### Acceptance Gates

- [ ] ≥100 injection payloads tested, all blocked
- [ ] Tool poisoning: all poisoned results sanitized
- [ ] Data exfiltration: all exit paths monitored
- [ ] Excessive agency: anomaly detection deployed
- [ ] Regression scoreboard: ≥95% detection rate
- [ ] Full security audit pass (external reviewer)
- [ ] Documentation complete
- [ ] v1.0.0 tagged and released

---

## Milestone Summary

```
v0.8.2 (current) ──── Feb 2026
  │
  ├── v0.9.0 ──── Phase 1: Governance Core ──── Mar 2026
  ├── v0.9.1 ──── Phase 2: Provenance ──── Apr 2026
  ├── v0.9.2 ──── Phase 3: Memory ──── Apr 2026
  ├── v0.9.3 ──── Phase 4: Channels ──── May 2026
  ├── v0.9.4 ──── Phase 5: Scheduler ──── May 2026
  ├── v0.9.5 ──── Phase 6: Multi-Agent ──── Jun 2026
  ├── v0.9.6 ──── Phase 7: Browser+MCP ──── Jul 2026
  ├── v0.9.7 ──── Phase 8: Marketplace ──── Jul 2026
  ├── v0.9.8 ──── Phase 9: Multi-Tenant ──── Aug 2026
  │
  └── v1.0.0 ──── Phase 10: Release ──── Sep 2026
```
