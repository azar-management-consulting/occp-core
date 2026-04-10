# Phase 1 Execution Plan — Governance Core Hardening (v0.9.0)

**Created:** 2026-03-02 | **Target:** March 2026 (3 weeks)
**REQ Count:** 16 | **New Files:** 12 | **Modified Files:** 4

---

## Work Package Dependencies

```
WP1 (Policy ABAC) ──→ WP3 (Governance) ──→ WP4 (Core Pipeline)
        │                      ↑
        └──────→ WP2 (Security) ──┘
```

WP1 + WP2 can run in parallel. WP3 depends on both. WP4 depends on WP3.

---

## WP1: Policy Engine ABAC Extension (Week 1)

| REQ-ID | Target File | Action | Complexity |
|--------|-------------|--------|------------|
| REQ-POL-01 | `policy_engine/abac.py` | CREATE | High |
| REQ-POL-02 | `policy_engine/engine.py` | MODIFY | Medium |
| REQ-GOV-02 | `policy_engine/engine.py` | MODIFY | High |
| REQ-POL-03 | `cli/policy_test.py` | CREATE | Medium |

### REQ-POL-01: ABAC + RBAC Hybrid
- New `ABACEvaluator` class with attribute extraction
- Attributes: user_role, agent_type, tool_category, data_classification, time_of_day, source_ip, session_type
- ABAC rules in YAML alongside existing Casbin RBAC
- Integrates into PolicyEngine.evaluate() as second evaluation pass

### REQ-POL-02 + REQ-GOV-02: Policy Decision Audit + Policy-as-Code
- Extend PolicyEngine.evaluate() to emit structured decision records
- Add policy version SHA-256 hash tracking
- Add YAML policy loading alongside existing JSON
- Decision replay: same input + same policy version = same output

### REQ-POL-03: Testable Policies
- `occp policy test --file=policy.yaml --fixtures=test.yaml`
- Test fixtures: input → expected decision pairs
- Exit code integration for CI

---

## WP2: Security Hardening (Week 1-2, parallel with WP1)

| REQ-ID | Target File | Action | Complexity |
|--------|-------------|--------|------------|
| REQ-SEC-01 | `policy_engine/ml_classifier.py` | CREATE | High |
| REQ-SEC-03 | `security/vault.py` | CREATE | High |
| REQ-SEC-02 | `cli/security_audit.py` | CREATE | Medium |
| REQ-SEC-04 | `policy_engine/rate_limiter.py` | CREATE | Medium |

### REQ-SEC-01: ML Injection Detection
- DistilBERT-based classifier (or scikit-learn TF-IDF fallback for lightweight)
- Runs alongside regex PromptInjectionGuard
- p95 latency target: <50ms
- Fallback to regex-only on timeout (Risk R-03 mitigation)
- Training data: injection payloads corpus + benign prompts

### REQ-SEC-03: Credential Vault
- Extends existing `security/encryption.py` TokenEncryptor
- Per-org encryption key isolation
- CRUD API: store, retrieve, rotate, revoke
- Integration with existing AuditEntry chain
- Backend: SQLAlchemy model + encrypted blob storage

### REQ-SEC-02: Security Audit CLI
- `occp security audit` — ≥15 check items
- Checks: encryption config, policy files, guard status, audit chain integrity, credential vault health, RBAC config, sandbox config, etc.
- Structured JSON output for CI integration

### REQ-SEC-04: Adaptive Rate Throttling
- Statistical anomaly detection (3σ deviation from rolling mean)
- Per-agent, per-tool rate tracking
- Throttle response within 500ms of detection
- Configurable window size and sensitivity

---

## WP3: Governance Enforcement (Week 2)

| REQ-ID | Target File | Action | Complexity |
|--------|-------------|--------|------------|
| REQ-GOV-01 | `orchestrator/pipeline.py` | MODIFY | Medium |
| REQ-GOV-03 | `adapters/policy_gate.py` | CREATE | High |
| REQ-GOV-04 | `security/break_glass.py` | CREATE | Medium |
| REQ-GOV-06 | `policy_engine/trust_levels.py` | CREATE | High |

### REQ-GOV-01: VAP Lifecycle Enforcement
- Add startup validation: all 5 stages must have handlers
- Add stage-skip detection and rejection
- Fuzz test target: 10,000 random API calls, 0 bypass

### REQ-GOV-03: Non-Bypassable Gate + Policy Gate Adapter
- New `adapters/policy_gate.py` — universal gate wrapper for all adapters
- MCP tool calls, plugin calls, browser actions — all route through PolicyGate
- No code path from adapter to execution skips evaluate()

### REQ-GOV-04: Break-Glass Protocol
- Multi-party approval (2/3 system_admins)
- Time-limited token (max 1h, configurable)
- Auto-revocation on expiry
- Immutable audit trail with severity=CRITICAL

### REQ-GOV-06: Trust Levels (L0-L5)
- Trust level enum: L0 Deterministic → L5 Multi-agent orchestrator
- Enforcement at VAP Gate stage
- Child agent inherits parent level minus 1
- Fuzz test: 5,000 cross-level calls, 0 bypass

---

## WP4: Core Pipeline Enhancement (Week 2-3)

| REQ-ID | Target File | Action | Complexity |
|--------|-------------|--------|------------|
| REQ-CORE-01 | `orchestrator/message_pipeline.py` | CREATE | High |
| REQ-CORE-02 | `orchestrator/sessions.py` | CREATE | High |
| REQ-CORE-03 | `orchestrator/config_loader.py` | CREATE | Medium |
| REQ-CORE-04 | `adapters/ollama_planner.py` | CREATE | Low |

### REQ-CORE-01: Message Pipeline
- Channel-agnostic message processing
- 4 channel types: api, websocket, webhook, channel_adapter
- Message normalization → VAP pipeline → response routing

### REQ-CORE-02: Session Management
- Session tiers: main (full VAP), DM (restricted), group (multi-user)
- Session state persistence (SQLAlchemy)
- Session lifecycle: create → active → suspend → terminate

### REQ-CORE-03: Config-First Agent Definition
- YAML agent definitions in `agents/` directory
- Properties: name, trust_level, capabilities, tools, model, policy_profile
- Loaded at startup, validated against trust level constraints

### REQ-CORE-04: Local Model Support (Ollama)
- Ollama HTTP adapter implementing Planner protocol
- Model selection by agent config
- Fallback to cloud provider if Ollama unavailable

---

## Test Strategy

| Test Category | Target File | Min Tests |
|---------------|-------------|-----------|
| ABAC evaluation | `tests/test_abac.py` | 15 |
| ML classifier | `tests/test_ml_classifier.py` | 10 |
| Credential vault | `tests/test_vault.py` | 12 |
| Trust levels | `tests/test_trust_levels.py` | 10 |
| Break-glass | `tests/test_break_glass.py` | 8 |
| Policy gate | `tests/test_policy_gate.py` | 10 |
| Rate limiter | `tests/test_rate_limiter.py` | 8 |
| Message pipeline | `tests/test_message_pipeline.py` | 10 |
| Sessions | `tests/test_sessions.py` | 10 |
| Config loader | `tests/test_config_loader.py` | 8 |
| Security audit CLI | `tests/test_security_audit.py` | 10 |
| Policy test CLI | `tests/test_policy_test_cli.py` | 8 |
| **Total** | | **≥119 new tests** |

---

## Acceptance Gates (from ROADMAP.md)

- [ ] All VAP stages enforce non-bypass (fuzz: 10,000 calls, 0 bypass)
- [ ] ABAC policy rules functional alongside existing RBAC
- [ ] Policy test CLI passes on all production policies
- [ ] ML injection classifier deployed with <50ms p95
- [ ] `occp security audit` checks ≥15 items
- [ ] Credential vault operational with per-org isolation
- [ ] Message pipeline processes 4 channel types
- [ ] Session management with main/DM/group tiers
- [ ] Config-first agent definition functional
- [ ] Trust level enforcement: L1 → browser access blocked (fuzz: 5,000 calls, 0 bypass)
- [ ] Adaptive rate throttling: 3σ deviation → throttle within 500ms
- [ ] Test coverage ≥85%

---

## Execution Order

1. **WP1a** — REQ-POL-01: `policy_engine/abac.py` + tests
2. **WP2a** — REQ-SEC-03: `security/vault.py` + tests (parallel)
3. **WP1b** — REQ-POL-02 + REQ-GOV-02: engine.py upgrades + tests
4. **WP2b** — REQ-SEC-01: `policy_engine/ml_classifier.py` + tests (parallel)
5. **WP1c** — REQ-POL-03: `cli/policy_test.py` + tests
6. **WP2c** — REQ-SEC-04: `policy_engine/rate_limiter.py` + tests
7. **WP2d** — REQ-SEC-02: `cli/security_audit.py` + tests
8. **WP3a** — REQ-GOV-06: `policy_engine/trust_levels.py` + tests
9. **WP3b** — REQ-GOV-03: `adapters/policy_gate.py` + tests
10. **WP3c** — REQ-GOV-04: `security/break_glass.py` + tests
11. **WP3d** — REQ-GOV-01: pipeline.py hardening + fuzz tests
12. **WP4a** — REQ-CORE-03: `orchestrator/config_loader.py` + tests
13. **WP4b** — REQ-CORE-02: `orchestrator/sessions.py` + tests
14. **WP4c** — REQ-CORE-01: `orchestrator/message_pipeline.py` + tests
15. **WP4d** — REQ-CORE-04: `adapters/ollama_planner.py` + tests
16. **Integration** — Full acceptance gate validation
