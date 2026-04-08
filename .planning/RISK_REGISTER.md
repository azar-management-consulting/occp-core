RISK_REGISTER.md — OCCP v1.0 "Agent Control Plane"

Version: 1.0.0 | Date: 2026-02-27
Scope: Delivery risks + security risks for v0.9.x → v1.0.0

---

| Risk ID | Risk | Probability | Impact | Mitigation | Owner | REQ Link | Status |
|--------|------|-------------|--------|------------|-------|----------|--------|
| R-01 | OpenClaw adoption gap (runtime features lag) | High | High | Prioritize P0 gaps: messaging, cron, MCP client, memory | Product | REQ-CHAN-01..05, REQ-AUTO-01, REQ-MCP-01..04, REQ-MEM-01..03 | Open |
| R-02 | Baileys WhatsApp instability (unofficial API) | Medium | Medium | Adapter abstraction + hot-swap implementation | Eng | REQ-CHAN-02 | Open |
| R-03 | ML injection classifier latency >50ms p95 | Medium | Medium | Quantized model + fallback to regex | Security | REQ-SEC-01 | Open |
| R-04 | Supply-chain scanning false positives | Medium | Low | Tunable thresholds + manual override with audit | Security | REQ-TSF-05 | Open |
| R-05 | Multi-tenant isolation failure | Low | Critical | Tenant-aware ORM + per-org keys + pen test | Security | REQ-MULTI-01 | Open |
| R-06 | MCP protocol changes break client | Medium | Medium | Version pinning + adapter layer | Eng | REQ-MCP-01..04 | Open |
| R-07 | OpenClaw skills incompatible with governance | High | Medium | Compatibility wrapper + capability generation | Eng | REQ-TSF-02, REQ-TSF-05 | Open |
| R-08 | EU AI Act requirements evolve | Medium | High | Quarterly mapping review + compliance dashboard | Compliance | REQ-COMP-01 | Open |
| R-09 | Browser sandbox escape via Playwright | Low | Critical | Isolated contexts + domain policy + no host FS | Security | REQ-CBDB-01..05 | Open |
| R-10 | Context window exhaustion in multi-agent | Medium | Medium | Proof-carrying outputs + memory compaction | Eng | REQ-MAO-05, REQ-MEM-02 | Open |

---

Risk Acceptance Criteria:
- No critical risks can remain without explicit mitigation plan.
- All high risks require dedicated security review before release.
# RISK_REGISTER.md — OCCP v1.0 "Agent Control Plane"

**Version:** 1.0.0 | **Date:** 2026-02-27
**Methodology:** Probability x Impact x Mitigation Effectiveness
**Scale:** P (1-5), I (1-5), Risk Score = P x I (1-25), Residual = Score x (1 - Mitigation%)

---

## 1. Risk Scoring Guide

### Probability Scale

| Level | Score | Description | Frequency |
|-------|-------|-------------|-----------|
| Rare | 1 | Unlikely to occur | <5% chance per year |
| Unlikely | 2 | Could occur in unusual circumstances | 5-20% per year |
| Possible | 3 | Could occur at some point | 20-50% per year |
| Likely | 4 | Will probably occur in most circumstances | 50-80% per year |
| Almost Certain | 5 | Expected to occur | >80% per year |

### Impact Scale

| Level | Score | Description | Consequence |
|-------|-------|-------------|-------------|
| Negligible | 1 | Minor inconvenience | No data loss, <1h downtime |
| Minor | 2 | Limited operational impact | Partial feature degradation, <4h recovery |
| Moderate | 3 | Significant operational impact | Service degradation, <24h recovery, limited data exposure |
| Major | 4 | Severe operational impact | Service outage, data breach potential, regulatory notification |
| Critical | 5 | Catastrophic | Full compromise, mass data breach, regulatory action, business failure |

### Risk Categories

| Score Range | Category | Action Required |
|-------------|----------|-----------------|
| 1-4 | Low | Accept, monitor annually |
| 5-9 | Medium | Mitigate within release cycle |
| 10-15 | High | Mitigate before next release |
| 16-25 | Critical | Immediate action, block release |

---

## 2. Strategic Risks

| ID | Risk | P | I | Score | Category | Mitigation | Eff% | Residual | Owner | Phase | Status |
|----|------|---|---|-------|----------|-----------|------|----------|-------|-------|--------|
| SR-01 | OpenClaw ~236K star adoption lead creates market barrier | 4 | 4 | 16 | Critical | Governance differentiator: enterprise features OpenClaw cannot offer (multi-tenant, compliance, non-bypass VAP) | 60% | 6.4 | Product | 1-10 | ACTIVE |
| SR-02 | Enterprise buyers require SOC2/ISO27001 certification before purchase | 3 | 4 | 12 | High | Framework mapping dashboard, PDF compliance report, gap audit tooling | 50% | 6.0 | Compliance | 9 | PLANNED |
| SR-03 | EU AI Act requirements evolve faster than implementation | 3 | 4 | 12 | High | Modular compliance framework, quarterly mapping review, legal review cycle | 40% | 7.2 | Compliance | 9 | PLANNED |
| SR-04 | OpenClaw community skills incompatible with OCCP governance | 4 | 3 | 12 | High | Compatibility wrapper with capability declaration auto-generation, governance shim | 50% | 6.0 | Adapters | 8 | PLANNED |
| SR-05 | Team capacity insufficient for 25-week plan | 3 | 4 | 12 | High | Phase prioritization (P0 first), incremental delivery, automated testing | 40% | 7.2 | PM | All | ACTIVE |

---

## 3. Security Risks

| ID | Risk | P | I | Score | Category | Mitigation | Eff% | Residual | Owner | Phase | Status |
|----|------|---|---|-------|----------|-----------|------|----------|-------|-------|--------|
| SEC-01 | Prompt injection bypasses all detection (zero-day) | 3 | 4 | 12 | High | 4-layer defense (regex→ML→output guard→anomaly), regression scoreboard, continuous retraining | 70% | 3.6 | Security | 1,10 | PLANNED |
| SEC-02 | Supply chain attack via malicious skill (ClawHavoc pattern) | 3 | 5 | 15 | High | 4-stage scan (Semgrep+Snyk+GitGuardian+capability), cosign signing, SBOM | 80% | 3.0 | Security | 2 | PLANNED |
| SEC-03 | Cross-tenant data isolation failure | 2 | 5 | 10 | High | Per-org DEK encryption, row-level security, tenant-aware ORM, penetration testing | 85% | 1.5 | Store | 9 | PLANNED |
| SEC-04 | Sandbox escape (nsjail/bwrap) | 1 | 5 | 5 | Medium | Defense-in-depth: nsjail→bwrap→process chain, no host fs, no Docker socket, seccomp | 90% | 0.5 | Security | Existing | IMPLEMENTED |
| SEC-05 | Credential vault compromise | 2 | 5 | 10 | High | Per-org key isolation, HSM backing (future), auto-rotation, access audit | 75% | 2.5 | Security | 1 | PLANNED |
| SEC-06 | Audit chain tampering | 1 | 5 | 5 | Medium | SHA-256 hash chain + Merkle root per run + tamper detection + optional transparency log | 90% | 0.5 | Security | 1 | PLANNED |
| SEC-07 | JWT token theft/replay | 3 | 3 | 9 | Medium | Short expiry (1h), refresh rotation, HTTPS-only, secure cookie flags | 70% | 2.7 | API | Existing | IMPLEMENTED |
| SEC-08 | ML injection classifier latency >50ms p95 | 3 | 2 | 6 | Medium | DistilBERT INT8 quantization, fallback to regex-only on timeout, async eval | 70% | 1.8 | Security | 1 | PLANNED |
| SEC-09 | Break-glass token abuse | 1 | 5 | 5 | Medium | 2-of-3 multi-party approval, 1h max expiry, auto-revocation, immutable audit | 90% | 0.5 | Security | 1 | PLANNED |
| SEC-10 | Browser automation data exfiltration | 2 | 4 | 8 | Medium | Domain deny list, form approval, download sandbox, screenshot audit | 80% | 1.6 | Adapters | 7 | PLANNED |

---

## 4. Technical Risks

| ID | Risk | P | I | Score | Category | Mitigation | Eff% | Residual | Owner | Phase | Status |
|----|------|---|---|-------|----------|-----------|------|----------|-------|-------|--------|
| TECH-01 | WhatsApp Baileys library instability (unofficial API) | 3 | 3 | 9 | Medium | Abstract behind ChannelAdapter protocol; swap implementation without API break | 60% | 3.6 | Adapters | 4 | PLANNED |
| TECH-02 | MCP protocol spec changes breaking client | 3 | 3 | 9 | Medium | Version pinning, adapter layer absorbs changes, fallback to last known good | 60% | 3.6 | Adapters | 7 | PLANNED |
| TECH-03 | SQLite vector DB performance at scale (>1M vectors) | 3 | 3 | 9 | Medium | PostgreSQL pgvector migration path, index optimization, tiered storage | 50% | 4.5 | Store | 3 | PLANNED |
| TECH-04 | Context window exhaustion in multi-agent | 3 | 3 | 9 | Medium | Proof-carrying compact outputs, memory compaction, summarization chain | 60% | 3.6 | Orchestrator | 3,6 | PLANNED |
| TECH-05 | Supply chain scanner false positives blocking publishing | 3 | 2 | 6 | Medium | Tunable thresholds, manual override with audit trail, severity-based routing | 70% | 1.8 | Security | 2 | PLANNED |
| TECH-06 | Docker-in-Docker complexity for sandbox | 2 | 3 | 6 | Medium | Prefer nsjail (no Docker needed), bwrap fallback, process-level isolation | 70% | 1.8 | Adapters | Existing | IMPLEMENTED |
| TECH-07 | Database migration complexity (6+ tables, multi-version) | 2 | 3 | 6 | Medium | Alembic migrations, blue-green deployment, rollback scripts | 70% | 1.8 | Store | All | ACTIVE |
| TECH-08 | SSE streaming reliability across network conditions | 2 | 2 | 4 | Low | Heartbeat interval, auto-reconnect, event replay, buffered queue | 60% | 1.6 | SDK | 8 | PLANNED |

---

## 5. Operational Risks

| ID | Risk | P | I | Score | Category | Mitigation | Eff% | Residual | Owner | Phase | Status |
|----|------|---|---|-------|----------|-----------|------|----------|-------|-------|--------|
| OPS-01 | Cost explosion from adversarial LLM usage | 3 | 4 | 12 | High | Hard budget envelope per-org, per-job token limit, adaptive throttling, cost anomaly ML | 80% | 2.4 | Orchestrator | 5 | PLANNED |
| OPS-02 | Cron job stuck consuming resources indefinitely | 3 | 3 | 9 | Medium | Time-bound execution (5min default), SIGTERM→SIGKILL chain, resource cleanup | 80% | 1.8 | Orchestrator | 5 | PLANNED |
| OPS-03 | Hetzner IP abuse block (historical precedent) | 2 | 4 | 8 | Medium | Monitoring, rapid IP rotation procedure, DNS automation, backup IP allocated | 60% | 3.2 | Infra | Existing | MITIGATED |
| OPS-04 | Database backup failure/corruption | 2 | 4 | 8 | Medium | Automated daily backups, integrity checks, point-in-time recovery, offsite copies | 70% | 2.4 | Infra | Existing | ACTIVE |
| OPS-05 | Disk space exhaustion (audit logs, vector DB) | 3 | 2 | 6 | Medium | 180-day audit retention (auto-prune), memory compaction, storage monitoring | 80% | 1.2 | Store | Existing | IMPLEMENTED |
| OPS-06 | SSL certificate expiry (Let's Encrypt) | 2 | 3 | 6 | Medium | certbot auto-renewal, monitoring alerts 7 days before expiry | 90% | 0.6 | Infra | Existing | IMPLEMENTED |
| OPS-07 | Multi-channel adapter outage affecting all channels | 2 | 3 | 6 | Medium | Independent adapter processes, per-channel circuit breaker, health dashboard | 70% | 1.8 | Adapters | 4 | PLANNED |

---

## 6. Economic Risks

| ID | Risk | P | I | Score | Category | Mitigation | Eff% | Residual | Owner | Phase | Status |
|----|------|---|---|-------|----------|-----------|------|----------|-------|-------|--------|
| ECON-01 | Token bomb attack ($100K+ in API costs) | 2 | 5 | 10 | High | Hard budget envelope per-org, per-job token limit with kill switch | 90% | 1.0 | Orchestrator | 5 | PLANNED |
| ECON-02 | Slow drip cost attack (under radar) | 3 | 3 | 9 | Medium | Adaptive throttling with sliding window, org-level daily budget, cost anomaly ML | 70% | 2.7 | Security | 1 | PLANNED |
| ECON-03 | LLM provider pricing increase | 3 | 3 | 9 | Medium | Multi-LLM failover (Claude → OpenAI → Ollama local), provider-agnostic architecture | 60% | 3.6 | Adapters | Existing | IMPLEMENTED |
| ECON-04 | Recursive multi-agent cost amplification | 2 | 4 | 8 | Medium | Recursion depth × budget guard = bounded total, cascade stop propagation | 80% | 1.6 | Orchestrator | 6 | PLANNED |
| ECON-05 | Memory storage bomb (vector DB bloat) | 2 | 2 | 4 | Low | Per-org storage quotas, compaction (≥60% reduction), write rate limiting | 80% | 0.8 | Store | 3 | PLANNED |
| ECON-06 | Scheduler abuse (high-frequency cron jobs) | 2 | 3 | 6 | Medium | Per-org cron limits, minimum interval enforcement, total budget guard | 80% | 1.2 | Orchestrator | 5 | PLANNED |

---

## 7. Risk Heat Map

```
Impact
  5 │ SEC-03  SEC-05    SEC-02     SR-01
    │ SEC-04  ECON-01
    │ SEC-06
    │ SEC-09
  4 │ OPS-03  OPS-04   OPS-01     SR-02  SR-03
    │ OPS-04  ECON-04  SEC-01     SR-05
    │ SEC-10
  3 │ TECH-06 TECH-01  ECON-02    SR-04
    │ TECH-07 TECH-02  ECON-03
    │ OPS-06  TECH-03  OPS-02
    │ OPS-07  TECH-04
  2 │ TECH-08 TECH-05  SEC-08
    │ ECON-05 OPS-05
    │         ECON-06
  1 │
    └──────────────────────────────────
      1       2        3          4      5
                    Probability
```

---

## 8. Risk Treatment Plan

### Immediate (Phase 1 — v0.9.0)

| Risk | Treatment | Acceptance Criteria |
|------|-----------|-------------------|
| SEC-01 | ML injection classifier deployment | <50ms p95, 95%+ detection |
| SEC-05 | Credential vault implementation | Per-org isolation verified |
| SEC-06 | Merkle root audit verification | Tamper detection functional |
| SEC-08 | Classifier latency optimization | INT8 quantization, regex fallback |
| SEC-09 | Break-glass protocol | 2-of-3 approval, 1h expiry |
| ECON-02 | Adaptive throttling | Sliding window rate limiting |

### Short-term (Phase 2-3 — v0.9.1-v0.9.2)

| Risk | Treatment | Acceptance Criteria |
|------|-----------|-------------------|
| SEC-02 | Supply chain scan pipeline | 4-stage scan, all artifacts signed |
| TECH-03 | Memory performance testing | Benchmarks at 100K, 500K, 1M vectors |
| TECH-04 | Proof-carrying output design | Compact output schema defined |
| TECH-05 | Scanner threshold tuning | <5% false positive rate |
| ECON-05 | Storage quota system | Per-org limits enforced |

### Medium-term (Phase 4-7 — v0.9.3-v0.9.6)

| Risk | Treatment | Acceptance Criteria |
|------|-----------|-------------------|
| TECH-01 | WhatsApp adapter abstraction | ChannelAdapter protocol swap test |
| TECH-02 | MCP version pinning | Adapter layer absorbs spec changes |
| OPS-01 | Budget guard deployment | Hard kill at 100%, 80% warning |
| OPS-02 | Time-bound execution | SIGTERM→SIGKILL chain verified |
| SEC-10 | Browser policy enforcement | Domain deny + form approval tests |
| OPS-07 | Channel adapter isolation | Per-channel circuit breaker |
| ECON-04 | Recursive cost bounds | Depth × budget = bounded |
| ECON-06 | Scheduler rate limits | Per-org cron caps enforced |

### Long-term (Phase 8-10 — v0.9.7-v1.0.0)

| Risk | Treatment | Acceptance Criteria |
|------|-----------|-------------------|
| SR-01 | Feature differentiation delivery | All 68+ REQs implemented |
| SR-02 | Compliance dashboard | SOC2/HIPAA/GDPR/EU AI Act mapping |
| SR-03 | Quarterly compliance review | Mapping update process documented |
| SR-04 | Compatibility wrapper | OpenClaw skill import functional |
| SEC-03 | Multi-tenant penetration test | Zero cross-tenant leaks |
| ECON-01 | Token bomb defense | Budget kill switch verified at scale |

---

## 9. Risk Ownership

| Owner | Risks | Count | Highest Score |
|-------|-------|-------|---------------|
| **Security** | SEC-01..10, ECON-02 | 11 | 15 (SEC-02) |
| **Orchestrator** | OPS-01, OPS-02, ECON-01, ECON-04, ECON-06 | 5 | 12 (OPS-01) |
| **Store** | SEC-03, TECH-03, TECH-07, ECON-05, OPS-05 | 5 | 10 (SEC-03) |
| **Adapters** | TECH-01, TECH-02, TECH-06, SEC-10, OPS-07 | 5 | 9 (TECH-01) |
| **Product** | SR-01, SR-04 | 2 | 16 (SR-01) |
| **Compliance** | SR-02, SR-03 | 2 | 12 (SR-02) |
| **PM** | SR-05 | 1 | 12 (SR-05) |
| **Infra** | OPS-03, OPS-04, OPS-06 | 3 | 8 (OPS-03) |
| **SDK** | TECH-08 | 1 | 4 (TECH-08) |
| **API** | SEC-07 | 1 | 9 (SEC-07) |

---

## 10. Review Schedule

| Review Type | Frequency | Participants | Artifacts Updated |
|-------------|-----------|--------------|-------------------|
| Risk scoring review | Per phase completion | Security + PM | RISK_REGISTER.md |
| Threat model update | Per phase completion | Security | THREAT_MODEL.md |
| Security mapping update | Per phase completion | Security | SECURITY_MAPPING.md |
| Penetration test | Phase 9 (pre-release) | External reviewer | Test report |
| Red-team exercise | Phase 10 (release) | Security + External | RT results |
| Compliance mapping | Quarterly | Compliance | SECURITY_MAPPING.md |
| Residual risk acceptance | Per release | Product + Security | This register |
