SECURITY_MAPPING.md — OCCP v1.0 "Agent Control Plane"

Version: 1.0.0 | Date: 2026-02-27
Scope: OWASP LLM Top 10 (v1.1 / 2025) mapped to OCCP controls and REQ-IDs

---

Mapping Key:
- Control: Concrete OCCP mechanism
- Evidence: Requirement IDs and planning artifacts

---

LLM01: Prompt Injection
Control:
- Input/output sanitization guards, injection detection
- Red-team injection test suite
Evidence:
- REQ-SEC-01, REQ-RT-01, REQ-RT-02, REQ-RT-04

LLM02: Insecure Output Handling
Control:
- Output sanitization guard, PII redaction, policy gate on tool calls
Evidence:
- REQ-GOV-03, REQ-POL-02, REQ-CBDB-02..05

LLM03: Training Data Poisoning
Control:
- Supply-chain controls on skills/plugins/MCP; signed artifacts; SBOM
- Memory write gating for shared knowledge
Evidence:
- REQ-CPC-01..04, REQ-TSF-01..05, REQ-MEM-01..03

LLM04: Model Denial of Service
Control:
- Budget guard, time-bound execution, recursion limits
- Scheduler kill-switch for runaway tasks
Evidence:
- REQ-VSTA-03..04, REQ-MAO-02, REQ-AUTO-01, REQ-GOV-05

LLM05: Supply Chain Vulnerabilities
Control:
- SLSA provenance, cosign signing, runtime verification, revocation
- Scan pipeline (SAST/SCA/Secrets)
Evidence:
- REQ-CPC-01..04, REQ-TSF-05, REQ-MCP-03

LLM06: Sensitive Information Disclosure
Control:
- PII guard, tenant isolation, RBAC, encrypted storage
Evidence:
- REQ-POL-01..02, REQ-MULTI-01, REQ-MEM-01..03, REQ-CBDB-02..04

LLM07: Insecure Plugin / Tool Design
Control:
- Capability declaration, sandbox isolation, policy gate
- Plugin crash isolation + version pinning
Evidence:
- REQ-TSF-02, REQ-MARKET-02, REQ-MAO-01, REQ-GOV-03

LLM08: Excessive Agency
Control:
- Trust-level enforcement, recursion limits, anomaly detection
- Budget guard + throttling
Evidence:
- REQ-GOV-05, REQ-MAO-02..03, REQ-RT-04, REQ-VSTA-03

LLM09: Overreliance
Control:
- Validation stage in VAP, approval gates, audit traceability
Evidence:
- REQ-GOV-01, REQ-GOV-04, REQ-POL-02

LLM10: Model Theft / Data Exfiltration
Control:
- Domain allow/deny, form approval, download restrictions
- Audit chain with tamper detection
Evidence:
- REQ-CBDB-02..05, REQ-POL-02, REQ-CPC-04

---

Coverage Summary:
All OWASP LLM Top 10 items are mapped to concrete OCCP controls with REQ-IDs.
# SECURITY_MAPPING.md — OCCP v1.0 "Agent Control Plane"

**Version:** 1.0.0 | **Date:** 2026-02-27
**Framework:** OWASP Top 10 for LLM Applications (2025) + NIST AI RMF
**Scope:** Full OCCP platform security controls → framework mapping → evidence

---

## 1. OWASP LLM Top 10 (2025) Mapping

### LLM01: Prompt Injection

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| Direct injection (jailbreak) | PromptInjectionGuard: 20+ regex patterns | `policy_engine/guards.py` | Existing | `tests/test_policy_engine.py` — 15+ injection variants tested | IMPLEMENTED |
| ML-based injection detection | DistilBERT classifier, dual-mode (regex+ML) | `policy_engine/guards.py` | REQ-SEC-01 | Target: <50ms p95, 95%+ detection rate | PLANNED (Phase 1) |
| Indirect injection (tool result) | Output sanitization guard on tool results | `policy_engine/guards.py` | REQ-RT-02 | Tool poisoning simulation suite | PLANNED (Phase 10) |
| Encoding attacks (base64/unicode) | Decoder normalization before guard eval | `policy_engine/guards.py` | REQ-RT-01 | Automated injection test suite (100+ payloads) | PLANNED (Phase 10) |
| Multi-turn injection | Session-scoped scanning per turn, anomaly detection | `orchestrator/pipeline.py` | REQ-RT-04 | Excessive agency detection with regression scoreboard | PLANNED (Phase 10) |
| Memory-via injection | Memory writes pass injection guard | `store/memory_store.py` | REQ-MEM-01 | Memory injection test coverage | PLANNED (Phase 3) |
| Cross-channel injection | Per-channel injection scanning, channel isolation | `adapters/channel_*.py` | REQ-CHAN-01 | Channel adapter protocol tests | PLANNED (Phase 4) |

**Residual Risk:** Medium — multi-turn injection remains hardest to detect; ML classifier improves with retraining.

**Defense Depth:** 4 layers (regex → ML classifier → output guard → anomaly detector)

---

### LLM02: Insecure Output Handling

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| HTML/script injection in output | OutputSanitizationGuard | `policy_engine/guards.py` | Existing | `tests/test_policy_engine.py` | IMPLEMENTED |
| PII leakage in agent response | PIIGuard (email, phone, SSN, CC) | `policy_engine/guards.py` | Existing | `tests/test_policy_engine.py` | IMPLEMENTED |
| SSE stream injection | Real-time redaction in SSE streaming | `sdk/python/client.py` | REQ-SDK-01 | SSE integration test | PLANNED (Phase 8) |
| Structured data injection | Per-field injection scan on JSON/YAML output | `policy_engine/guards.py` | REQ-RT-01 | Nested injection test suite | PLANNED (Phase 10) |
| Cross-org data in output | Tenant-aware output filtering | `store/models.py` | REQ-MULTI-01 | Penetration test: zero cross-tenant leaks | PLANNED (Phase 9) |
| MCP tool result sanitization | Output guard on all MCP responses | `adapters/mcp_client.py` | REQ-MCP-04 | MCP scope enforcement tests | PLANNED (Phase 7) |

**Residual Risk:** Low — multi-layer output sanitization with PII detection.

**Defense Depth:** 3 layers (guard → PII scan → tenant filter)

---

### LLM03: Training Data Poisoning

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| External LLM training (not applicable) | OCCP does not fine-tune external LLMs | N/A | N/A | By design — API-only LLM usage | N/A |
| Memory store poisoning | Memory writes pass VAP gate + injection guard | `store/memory_store.py` | REQ-MEM-01 | Memory write audit trail | PLANNED (Phase 3) |
| Knowledge base corruption | Versioned entries, RBAC-filtered writes | `store/knowledge_base.py` | REQ-MEM-03 | Cross-session knowledge tests | PLANNED (Phase 3) |
| RAG index poisoning | Compaction preserves provenance, integrity checks | `store/memory_store.py` | REQ-MEM-02 | Compaction integrity verification | PLANNED (Phase 3) |

**Residual Risk:** Low — OCCP uses external LLMs via API, no training data modification.

**Defense Depth:** 2 layers (VAP gate → memory integrity)

---

### LLM04: Model Denial of Service

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| Token budget exhaustion | Hard budget envelope per-org, per-job token limit | `policy_engine/guards.py` | REQ-VSTA-03 | Budget guard terminates at limit | PLANNED (Phase 5) |
| Recursive agent loops | Configurable recursion depth (default 3, max 10) | `orchestrator/pipeline.py` | REQ-MAO-02 | Recursion enforcement test | PLANNED (Phase 6) |
| Time-bomb prompt | Time-bound execution (5min default), SIGTERM chain | `orchestrator/scheduler.py` | REQ-VSTA-04 | Timeout kill test | PLANNED (Phase 5) |
| Slow drip cost attack | Adaptive throttling with sliding window | `policy_engine/guards.py` | REQ-SEC-04 | Cost anomaly detection tests | PLANNED (Phase 1) |
| Channel message flood | Per-channel rate limiting, backpressure | `adapters/channel_*.py` | REQ-CHAN-01 | Channel adapter stress test | PLANNED (Phase 4) |
| Cost explosion (multi-agent) | Recursion depth x budget = bounded total cost | `orchestrator/pipeline.py` | REQ-MAO-02, REQ-VSTA-03 | Multi-agent cost bounds test | PLANNED (Phase 6) |

**Residual Risk:** Medium — novel cost attack patterns may evade initial ML model.

**Defense Depth:** 4 layers (budget → throttle → timeout → anomaly ML)

---

### LLM05: Supply Chain Vulnerabilities

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| Malicious skill (ClawHavoc) | 4-stage scan: Semgrep+Snyk+GitGuardian+capability | `security/supply_chain.py` | REQ-TSF-05 | Automated scan pipeline tests | PLANNED (Phase 2) |
| Typosquatting | Typosquatting + homoglyph detection | `security/supply_chain.py` | Existing | `tests/test_hardening.py` | IMPLEMENTED |
| Dependency confusion | Private-first registry, version pinning | `config/registry.yaml` | REQ-TSF-01, REQ-TSF-04 | Private registry isolation test | PLANNED (Phase 2) |
| Unsigned artifacts | cosign signature verification at install + runtime | `security/signing.py` | REQ-CPC-02, REQ-CPC-03 | Unsigned load blocked (100%) | PLANNED (Phase 2) |
| SBOM tracking | Mandatory SBOM for published skills | `security/sbom.py` | REQ-TSF-03 | SBOM generation test | PLANNED (Phase 2) |
| Compromised MCP server | Runtime signature verification, health monitoring | `adapters/mcp_client.py` | REQ-MCP-03 | MCP dependency governance test | PLANNED (Phase 7) |
| SLSA provenance | SLSA Build L2+ attestation | `security/provenance.py` | REQ-CPC-01 | Provenance verification test | PLANNED (Phase 2) |
| Revocation | Block within 5min polling cycle | `security/revocation.py` | REQ-CPC-04 | Revocation enforcement test | PLANNED (Phase 2) |

**Residual Risk:** Low — comprehensive supply chain defense (8 controls).

**Defense Depth:** 5 layers (scan → sign → SBOM → registry → revocation)

---

### LLM06: Sensitive Information Disclosure

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| System prompt leakage | System prompt isolation, output guard | `policy_engine/guards.py` | REQ-RT-01 | Injection test suite checks prompt leakage | PLANNED (Phase 10) |
| PII in agent response | PIIGuard: email, phone, SSN, credit card | `policy_engine/guards.py` | Existing | `tests/test_policy_engine.py` | IMPLEMENTED |
| Cross-tenant data leak | Org-scoped encryption, row-level security | `store/models.py` | REQ-MULTI-01 | Penetration test: zero cross-tenant | PLANNED (Phase 9) |
| Credential exposure | Vault with per-org isolation, auto-rotation | `security/vault.py` | REQ-SEC-03 | Vault isolation test | PLANNED (Phase 1) |
| Browser data exfiltration | Domain deny, form approval, download restrictions | `adapters/browser.py` | REQ-CBDB-02..04 | Browser policy enforcement tests | PLANNED (Phase 7) |
| Audit data exposure | Encrypted at rest, system_admin access only | `store/audit_store.py` | Existing | `tests/test_store.py` | IMPLEMENTED |
| Data residency violation | Per-org LLM routing, EU → EU endpoints | `config/settings.py` | REQ-MULTI-02 | Residency enforcement test | PLANNED (Phase 9) |

**Residual Risk:** Medium — system prompt partial leakage has no perfect defense.

**Defense Depth:** 4 layers (PII guard → encryption → isolation → residency routing)

---

### LLM07: Insecure Plugin Design

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| Plugin crash cascade | Subprocess isolation, circuit breaker (3 fail → disable) | `orchestrator/plugin_host.py` | REQ-MARKET-02 | Plugin crash boundary test | PLANNED (Phase 8) |
| Plugin sandbox escape | nsjail → bwrap → process → mock chain | `adapters/sandbox_executor.py` | Existing | `tests/test_sandbox_executor.py` | IMPLEMENTED |
| Plugin excessive permissions | Capability declaration schema, least-privilege | `config/skills.yaml` | REQ-TSF-02 | Capability validation test | PLANNED (Phase 2) |
| Plugin API version exploit | Versioned API, deprecated versions logged/rejected | `orchestrator/plugin_host.py` | REQ-MARKET-02 | API version enforcement test | PLANNED (Phase 8) |
| Plugin secret access | Plugin secrets scoped, no cross-plugin access | `security/vault.py` | REQ-SEC-03 | Vault scope isolation test | PLANNED (Phase 1) |
| Agent boundary violation | Agent-scoped resource boundaries at policy layer | `policy_engine/engine.py` | REQ-GOV-05 | Boundary enforcement test | PLANNED (Phase 8) |

**Residual Risk:** Low — mandatory sandbox + capability declaration + crash isolation.

**Defense Depth:** 4 layers (sandbox → capability → circuit breaker → boundary enforcement)

---

### LLM08: Excessive Agency

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| Tool call anomaly | Tool count anomaly detection, per-turn limit | `policy_engine/guards.py` | REQ-RT-04 | Excessive agency detection tests | PLANNED (Phase 10) |
| Unauthorized file access | Agent boundary enforcement at policy layer | `policy_engine/engine.py` | REQ-GOV-05 | Boundary violation test | PLANNED (Phase 8) |
| Scope creep in automation | Trust level enforcement (L0-L5) per run | `policy_engine/engine.py` | REQ-GOV-06 | Trust level escalation blocked | PLANNED (Phase 1) |
| Multi-agent amplification | Recursion depth limit + cascade stop | `orchestrator/pipeline.py` | REQ-MAO-02, REQ-MAO-03 | Multi-agent containment test | PLANNED (Phase 6) |
| Unattended autonomy | Time-bound execution, budget guard | `orchestrator/scheduler.py` | REQ-VSTA-03, REQ-VSTA-04 | Scheduler autonomy bounds test | PLANNED (Phase 5) |
| VAP bypass (all paths) | Non-bypassable gate: 10K fuzz → 0 bypass | `orchestrator/pipeline.py` | REQ-GOV-03 | Fuzz test evidence | PLANNED (Phase 1) |

**Residual Risk:** Low — VAP non-bypass + trust levels + budget guard.

**Defense Depth:** 5 layers (VAP → trust level → budget → boundary → anomaly)

---

### LLM09: Overreliance

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| Hallucinated tool calls | VAP validation stage checks execution results | `orchestrator/pipeline.py` | REQ-GOV-01 | Validation stage tests | IMPLEMENTED |
| Fabricated facts in output | Proof-carrying outputs with provenance hash | `orchestrator/pipeline.py` | REQ-MAO-05 | Proof chain verification test | PLANNED (Phase 6) |
| False confidence scores | Output validation includes confidence calibration | `adapters/basic_validator.py` | Existing | Validator output checks | IMPLEMENTED (partial) |
| Automation without review | Human-in-the-loop at configurable stages | `orchestrator/pipeline.py` | REQ-GOV-01 | VAP gate approval flow | IMPLEMENTED |

**Residual Risk:** Medium — LLM hallucinations remain an inherent limitation.

**Defense Depth:** 3 layers (VAP validation → proof chain → human-in-loop)

---

### LLM10: Model Theft

| Sub-Risk | OCCP Control | Module | REQ-ID | Evidence | Status |
|----------|-------------|--------|--------|----------|--------|
| External model theft (N/A) | OCCP uses external LLMs via API, no local model to steal | N/A | N/A | By design | N/A |
| Local model (Ollama) isolation | Ollama access controlled via API key, localhost binding | `adapters/ollama_adapter.py` | REQ-CORE-04 | Ollama integration test | PLANNED (Phase 1) |
| Agent prompt/config theft | Config files signed, access requires admin role | `config/` | REQ-CORE-03 | Config signing test | PLANNED (Phase 1) |
| Skill IP theft from registry | Private-first registry, access control on publish | `config/registry.yaml` | REQ-TSF-01 | Registry access control test | PLANNED (Phase 2) |

**Residual Risk:** Low — OCCP primarily uses API-based external LLMs.

**Defense Depth:** 2 layers (access control → signing)

---

## 2. Control Coverage Summary

### By OWASP LLM Category

| OWASP ID | Category | Controls | Implemented | Planned | Coverage |
|----------|----------|----------|-------------|---------|----------|
| LLM01 | Prompt Injection | 7 | 1 | 6 | 100% (planned) |
| LLM02 | Insecure Output | 6 | 2 | 4 | 100% (planned) |
| LLM03 | Training Data Poisoning | 4 | 0 | 3 | 100% (planned, 1 N/A) |
| LLM04 | Model DoS | 6 | 0 | 6 | 100% (planned) |
| LLM05 | Supply Chain | 8 | 1 | 7 | 100% (planned) |
| LLM06 | Sensitive Info Disclosure | 7 | 3 | 4 | 100% (planned) |
| LLM07 | Insecure Plugin | 6 | 1 | 5 | 100% (planned) |
| LLM08 | Excessive Agency | 6 | 1 | 5 | 100% (planned) |
| LLM09 | Overreliance | 4 | 2 | 2 | 100% (planned) |
| LLM10 | Model Theft | 4 | 0 | 2 | 100% (planned, 2 N/A) |
| **TOTAL** | | **58** | **11** | **44** | **100%** |

### Implemented Controls (v0.8.2)

| Control | OWASP | Module | Test File |
|---------|-------|--------|-----------|
| PromptInjectionGuard (20+ regex) | LLM01 | `policy_engine/guards.py` | `tests/test_policy_engine.py` |
| PIIGuard (email, phone, SSN, CC) | LLM02, LLM06 | `policy_engine/guards.py` | `tests/test_policy_engine.py` |
| OutputSanitizationGuard | LLM02 | `policy_engine/guards.py` | `tests/test_policy_engine.py` |
| ResourceLimitGuard | LLM04 | `policy_engine/guards.py` | `tests/test_policy_engine.py` |
| Typosquatting detection | LLM05 | `security/supply_chain.py` | `tests/test_hardening.py` |
| nsjail/bwrap sandbox | LLM07 | `adapters/sandbox_executor.py` | `tests/test_sandbox_executor.py` |
| VAP 5-stage pipeline | LLM08 | `orchestrator/pipeline.py` | `tests/test_orchestrator.py` |
| SHA-256 audit chain | LLM09 | `store/audit_store.py` | `tests/test_store.py` |
| AES-256-GCM encryption | LLM06 | `security/encryption.py` | `tests/test_hardening.py` |
| Casbin RBAC (4 roles) | LLM06, LLM08 | `policy_engine/engine.py` | `tests/test_rbac.py` |
| Rate limiting (auth endpoints) | LLM04 | `api/middleware.py` | `tests/test_api.py` |

### Phase Delivery Schedule

| Phase | OWASP Categories Addressed | Key Controls Delivered |
|-------|---------------------------|----------------------|
| Phase 1 (v0.9.0) | LLM01, LLM04, LLM06, LLM08, LLM10 | ML classifier, credential vault, ABAC, trust levels, budget guard |
| Phase 2 (v0.9.1) | LLM05 | SLSA provenance, cosign signing, SBOM, private registry, scan pipeline |
| Phase 3 (v0.9.2) | LLM01, LLM03, LLM06 | Memory integrity, RAG injection defense, cross-session RBAC |
| Phase 4 (v0.9.3) | LLM01, LLM04 | Channel adapters with per-channel injection scanning, rate limiting |
| Phase 5 (v0.9.4) | LLM04, LLM08 | Budget guard, time-bound execution, scheduler autonomy controls |
| Phase 6 (v0.9.5) | LLM04, LLM08, LLM09 | Recursion limits, cascade stop, proof-carrying outputs |
| Phase 7 (v0.9.6) | LLM05, LLM06 | Browser isolation, MCP scope enforcement, domain policies |
| Phase 8 (v0.9.7) | LLM02, LLM07, LLM08 | Plugin isolation, SSE streaming, agent boundaries |
| Phase 9 (v0.9.8) | LLM06 | Multi-tenant isolation, data residency, compliance dashboard |
| Phase 10 (v1.0.0) | LLM01, LLM02, LLM08 | Red-team suite, injection test suite, regression scoreboard |

---

## 3. NIST AI RMF Mapping

### Govern (GV)

| NIST Function | OCCP Control | REQ-ID | Phase |
|---------------|-------------|--------|-------|
| GV-1: AI governance | VAP lifecycle enforcement | REQ-GOV-01 | 1 |
| GV-1: Policy framework | Policy-as-Code engine | REQ-GOV-02 | 1 |
| GV-2: Accountability | SHA-256 audit chain, Merkle root | REQ-SEC-06, Existing | 1 |
| GV-3: Workforce | Trust level declaration (L0-L5) | REQ-GOV-06 | 1 |
| GV-4: Organizational | Break-glass protocol | REQ-GOV-04 | 1 |
| GV-5: Compliance | Framework mapping dashboard | REQ-COMP-01 | 9 |

### Map (MP)

| NIST Function | OCCP Control | REQ-ID | Phase |
|---------------|-------------|--------|-------|
| MP-2: Context | Agent capability declaration schema | REQ-TSF-02 | 2 |
| MP-3: Benefits/costs | Budget guard with cost tracking | REQ-VSTA-03 | 5 |
| MP-4: Risk tolerance | Risk level in task model (LOW/MEDIUM/HIGH/CRITICAL) | Existing | — |

### Measure (MS)

| NIST Function | OCCP Control | REQ-ID | Phase |
|---------------|-------------|--------|-------|
| MS-1: Metrics | Regression scoreboard (95%+ detection) | REQ-RT-05 | 10 |
| MS-2: Monitoring | Cost anomaly detection, tool sequence anomaly | REQ-SEC-05, REQ-RT-04 | 1, 10 |
| MS-3: Tracking | Audit trail with hash chain integrity | Existing | — |

### Manage (MG)

| NIST Function | OCCP Control | REQ-ID | Phase |
|---------------|-------------|--------|-------|
| MG-1: Risk management | SIEM/SOAR integration | REQ-COMP-02 | 8 |
| MG-2: Response | Kill-switch (cascade stop, revocation) | REQ-MAO-03, REQ-CPC-04 | 2, 6 |
| MG-3: Communication | Compliance report export (PDF) | REQ-COMP-01 | 9 |
| MG-4: Continuous improvement | Red-team test suite, regression scoreboard | REQ-RT-01..05 | 10 |

---

## 4. EU AI Act Alignment

| Article | Requirement | OCCP Control | REQ-ID | Status |
|---------|------------|-------------|--------|--------|
| Art. 9 | Risk management system | THREAT_MODEL.md + RISK_REGISTER.md | — | DOCUMENTED |
| Art. 10 | Data governance | Memory RBAC, tenant isolation | REQ-MEM-01, REQ-MULTI-01 | PLANNED |
| Art. 11 | Technical documentation | Architecture, security, threat model | — | THIS FILE |
| Art. 12 | Record-keeping | SHA-256 audit chain, 180-day retention | Existing | IMPLEMENTED |
| Art. 13 | Transparency | VAP stage visibility, audit trail access | REQ-GOV-01 | IMPLEMENTED |
| Art. 14 | Human oversight | VAP gate (human approval), break-glass | REQ-GOV-01, REQ-GOV-04 | IMPLEMENTED (partial) |
| Art. 15 | Accuracy, robustness, security | Sandbox, guards, red-team, regression | Multiple | IN PROGRESS |
| Art. 19 | Quality management | CI/CD 6 checks, test coverage 85%+ | Existing | IMPLEMENTED |
| Art. 52 | Transparency obligations | Agent identifies as AI in channel messages | REQ-CHAN-01 | PLANNED |
| Art. 61 | Post-market monitoring | SIEM integration, regression scoreboard | REQ-COMP-02, REQ-RT-05 | PLANNED |

---

## 5. OpenClaw Comparative Gap

| OWASP Category | OpenClaw Controls | OCCP Controls | OCCP Advantage |
|----------------|------------------|---------------|----------------|
| LLM01: Prompt Injection | Regex guards + approval pipeline | Regex + ML classifier + multi-layer | ML detection + cross-channel isolation |
| LLM02: Output Handling | Output sanitization guard | PII guard + output guard + tenant filter | Tenant-aware filtering |
| LLM03: Training Data | N/A (no fine-tuning) | Memory integrity + RAG injection defense | Memory governance |
| LLM04: Model DoS | Rate limiting (gateway) | Budget guard + throttle + timeout + anomaly | Economic attack defense |
| LLM05: Supply Chain | Skill scanner (regex) + VirusTotal | 4-stage pipeline + cosign + SLSA + SBOM | Cryptographic provenance |
| LLM06: Info Disclosure | Single-operator (no isolation needed) | Multi-tenant + vault + residency routing | Enterprise isolation |
| LLM07: Insecure Plugin | Docker sandbox (optional) | Mandatory sandbox + capability declaration | Non-optional isolation |
| LLM08: Excessive Agency | Approval pipeline + dangerous tool list | VAP non-bypass + trust levels + boundaries | Trust level system |
| LLM09: Overreliance | N/A | Proof-carrying outputs + validation stage | Verifiable outputs |
| LLM10: Model Theft | N/A (API-only) | Config signing + private registry | Registry controls |
