# RFC 0001: Baseline — OCCP L4+ → L6 Foundation

**Status:** APPROVED (self-documenting baseline)
**Type:** architecture
**Author:** Claude Code (autonomous principal architect)
**Created:** 2026-04-08
**Target Release:** v0.10.0
**Risk Level:** low
**Affects Immutable Paths:** no
**Supersedes:** —

---

## 1. Summary

This RFC codifies the L4+ → L6 foundation for OCCP. It establishes the
architecture memory, observability, evaluation lane, and governance rules
required for OCCP to reach L6 — *disciplined architectural self-redesign
with bounded autonomy*.

No existing production behavior is changed. All new subsystems are
additive, opt-in via feature flags, and default to safe modes.

## 2. Motivation

As of v0.9.0, OCCP is at L4+ maturity:
- ✅ Autonomous execution (VAP)
- ✅ Policy gating (4 guards + AgentToolGuard enforcement)
- ✅ Audit trail (hash chain, 319 entries in prod)
- ✅ Persistence (9 DB tables)
- ✅ Multi-channel I/O (Telegram, REST, CloudCode)
- ✅ DAG workflows (tested)
- ✅ MCP runtime bridge (7 tools, 1.0 success rate)

But L6 requires three capabilities OCCP currently lacks:
1. **Machine-readable self-model** — nothing describes the system to itself
2. **Runtime telemetry** — only unstructured JSON logs, no metrics/traces
3. **Safe evaluation lane** — no replay, no canary, no feature flags

Evidence:
- `observability_current_state.metrics: NONE` in `architecture/runtime_inventory.yaml`
- No `.planning/rfc/` directory existed before this RFC
- `security/agent_allowlist.py` lists 21 agents but no code verifies they match the runtime
- `FeatureFlagRow` table does not exist in `store/models.py`

## 3. Detailed Design

### 3.1 Current state

Pipeline flow (VAP) is Protocol-abstracted:
```
adapters/.../Planner → policy_engine.evaluate → Executor → Validator → Shipper
```
BrainFlow is a 7-phase conversation engine (`orchestrator/brain_flow.py`).
Policy guards: `pii_guard`, `prompt_injection_guard`, `resource_limit_guard`, `output_sanitization_guard`.
Audit: `audit_entries` table + hash chain.

Seed architecture memory already existed in `.planning/protocol/`:
- `MASTER_PROTOCOL_v1.md`
- `NODE_REGISTRY.yaml`
- `AGENT_ROLE_MAP.yaml`
- `MCP_ROLE_MAP.yaml`

These are **prose-heavy**, not validated by code, and incomplete.

### 3.2 Proposed change

**New directories:**
```
architecture/
├── README.md
├── services.yaml        (8 services catalogued)
├── agents.yaml          (8 specialists + brain + 12 seeded)
├── tools.yaml           (7 MCP bridge tools)
├── dataflows.yaml       (5 critical flows)
├── boundaries.yaml      (3 tiers: autonomous / review / immutable)
├── runtime_inventory.yaml
└── governance.yaml      (L6 bounded autonomy contract)

observability/
├── __init__.py
└── metrics_collector.py (Counter + Histogram + Gauge, Prometheus text format)

evaluation/
├── __init__.py
├── feature_flags.py     (in-memory store, 6 default flags)
└── replay_harness.py    (skeleton, stub run())

.planning/rfc/
├── TEMPLATE.md
└── 0001-baseline.md     (this file)

api/routes/
└── observability.py     (/observability/metrics|snapshot|health|reset)
```

**Modified files:**
- `api/app.py` — include `observability_route.router`
- `orchestrator/pipeline.py` — emit metrics on every terminal path (success + 4 exception classes)

**Deleted files (cruft):**
- `.planning/REPAIR_PROMPT.md`
- `.planning/FINAL_REPAIR_PROMPT.md`
- `.planning/MASTER_REPAIR_PROMPT.md`
- `.planning/ULTIMATE_REPAIR_PROMPT.md`

### 3.3 Alternatives considered

**Alt 1: Use Prometheus client library directly**
- Pros: battle-tested
- Cons: adds runtime dep; vendored prometheus_client has known issues with async context; distracts from foundation goals
- **Rejected** for v0.10.0; revisit in v0.11.0

**Alt 2: Skip architecture memory, go straight to proposal engine**
- Pros: faster visible output
- Cons: proposals without self-model produce hallucinated redesigns; violates "evidence over assumption" principle
- **Rejected** — self-model is the prerequisite

**Alt 3: Implement real replay harness in v0.10.0**
- Pros: usable evaluation lane now
- Cons: requires sandbox integration, git worktree management, OCCP instance boot — 3-week effort
- **Rejected** for v0.10.0; land skeleton + data contract; full impl in v0.11.0

## 4. Impact Analysis

### 4.1 Affected components
- `api/app.py` — +2 lines (router include)
- `orchestrator/pipeline.py` — +~80 lines (_emit_metrics method + hook calls)
- New: `architecture/` (7 YAML), `observability/` (2 py), `evaluation/` (3 py), `api/routes/observability.py`, `.planning/rfc/` (2 md)

### 4.2 Compatibility
- Backward compatible: yes
- Forward compatible: yes
- Breaking API changes: none

### 4.3 Risk assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Metrics overhead slows pipeline | low | low | non-blocking emit with try/except |
| YAML drift (code vs declaration) | medium | low | tests/architecture/ schema validators |
| Feature flag misuse | low | low | default OFF for all experimental |
| Observability endpoint unauth | low | medium | requires JWT (`get_current_user_payload`) |

## 5. Testing Plan

### 5.1 Unit tests
- `tests/test_observability_metrics.py` — Counter/Histogram/Gauge behavior
- `tests/architecture/test_yaml_schema.py` — parse + cross-ref checks
- `tests/test_feature_flags.py` — store CRUD + singleton
- `tests/test_replay_harness.py` — scenario registration

### 5.2 Integration tests
- `GET /observability/metrics` after triggering a pipeline run → expect non-zero counter
- `GET /observability/snapshot` → valid JSON with 3 top-level keys

### 5.3 Replay scenarios
None yet (harness is stub).

### 5.4 Canary criteria
Not applicable — additive changes only, no behavioral modification.

## 6. Rollout Plan

1. Commit to `feat/v0.10.0-l6-foundation` branch
2. Full pytest run (expect 2618+ pass)
3. PR to main with evidence
4. Merge after review
5. Deploy via docker compose build + up
6. Verify `GET /observability/metrics` returns 200 with data

## 7. Rollback Plan

```bash
git revert <commit-range>
cd /opt/occp && docker compose build api && docker compose up -d api
```
No schema changes → no migration rollback needed.

## 8. Governance Check

- Affects immutable paths: **no** (all new files are in autonomous_safe zones per `architecture/boundaries.yaml`)
- Requires human review: **yes** (PR to main = standard review policy)
- Required reviewers: 1 (Henry)
- Self-escalation risk: **no** — this RFC does not grant Claude Code new authority; it formalizes existing bounded autonomy

## 9. Success Criteria

- [x] All 7 architecture YAML files created and valid
- [x] observability/ package imports cleanly
- [x] /observability/metrics route registered
- [x] evaluation/ skeleton imports cleanly
- [x] RFC template + this baseline RFC written
- [x] 4 cruft files deleted
- [x] Pipeline emits metrics on success + failure paths
- [ ] tests/architecture/ passes (next wave)
- [ ] Full pytest passes 2618+ (next wave)
- [ ] Deployed to prod (next wave)
- [ ] Prometheus scrape test succeeds (next wave)

## 10. References

- Master protocol: `.planning/protocol/MASTER_PROTOCOL_v1.md`
- L5 roadmap (prior art): `.planning/L5_SELF_EVOLVING_ROADMAP.md`
- Governance contract: `architecture/governance.yaml`
- Boundaries: `architecture/boundaries.yaml`
- Dataflows: `architecture/dataflows.yaml`
- Current state snapshot: `.planning/CURRENT_STATE_2026-04-08.md` (companion doc)
