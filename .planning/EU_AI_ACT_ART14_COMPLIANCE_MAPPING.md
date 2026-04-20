# EU AI Act Article 14 (Human Oversight) — OCCP Compliance Mapping

**Dátum:** 2026-04-20
**Scope:** OCCP v0.10.0 → EU AI Act Regulation (EU) 2024/1689
**Deadline:** **2026-08-02** (applicable for high-risk AI systems per Art. 113)
**Source:** https://artificialintelligenceact.eu/article/14/

---

## §1. Art.14 — 3-tier Human Oversight

- **Art.14(1)** — HITL design + appropriate HMI tools
- **Art.14(4)(a)** — **UNDERSTAND:** monitor operation, detect anomalies
- **Art.14(4)(b)** — awareness of automation bias
- **Art.14(4)(c)** — correctly interpret output
- **Art.14(4)(d)** — **INTERVENE:** disregard / override / reverse output
- **Art.14(4)(e)** — **HALT:** "stop" button bringing system to safe state
- **Art.14(5)** — biometric dual-control (N/A for OCCP — no Annex III biometric module)

---

## §2. OCCP component → Art.14 tier mapping

| Tier | Requirement | OCCP component | Endpoint / file | Evidence |
|---|---|---|---|---|
| **L1 Understand** | Monitor + anomaly detection | L6 readiness markers | `GET /api/v1/observability/readiness` | `api/routes/observability.py:146-176` |
| L1 | Prometheus/JSON telemetry | MetricsCollector | `/observability/metrics`, `/snapshot`, `/health` | `api/routes/observability.py:43-73` |
| L1 | Anomaly detection | AnomalyDetector | `/observability/anomalies` | `api/routes/observability.py:78-95` |
| L1 | Narrative summary | DigestGenerator | `/observability/digest`, `/summary` | `api/routes/observability.py:98-141` |
| L1 | Audit trail (Art.12) | SHA-256 hash chain | `policy_engine/engine.py:399-433` |`verify_audit_chain()` |
| L1 | Policy decision record | GateResult.to_decision_record | `policy_engine/engine.py:51-73` | structured record with policy_hash |
| L1 | Drift detection | DriftDetector | `/governance/drift` | `api/routes/governance.py:299-304` |
| **L2 Intervene** | HITL approval | ApprovalQueue | `/autodev/run/{id}/approve|reject` | `autodev/approval_queue.py:28-80` |
| L2 | Per-action override | HumanOversightGuard | `policy_engine/guards.py:279-357` | `approve()` / `revoke_approval()` |
| L2 | Policy-level approval | REQUIRE_APPROVAL rule | `policy_engine/engine.py:285-297` | GateResult.approved=False |
| L2 | Feature flag | FlagStore | `PUT /governance/flags` | `api/routes/governance.py:321-337` |
| L2 | Canary rollback | CanaryEngine | `/governance/canary/recent` | `api/routes/governance.py:285-294` |
| L2 | Break-glass | `security/break_glass.py` | CLI + audit | `tests/test_break_glass.py` |
| **L3 Halt** | One-click STOP | KillSwitch | `POST /governance/kill_switch/activate` | `evaluation/kill_switch.py:119-145` |
| L3 | Fail-fast guard | `require_kill_switch_inactive()` | `orchestrator/pipeline.py:40-47` | L6 marker `kill_switch_runtime_guard: true` |
| L3 | Drill mode | `/kill_switch/drill` | `api/routes/governance.py:249-263` | logs without blocking |
| L3 | Auto-triggers | KillSwitchTrigger enum | `evaluation/kill_switch.py:41-49` | MANUAL / ANOMALY / CANARY_FAILURE / ERROR_SPIKE / SECURITY |
| L3 | Manual resume | `deactivate(actor, reason)` | `evaluation/kill_switch.py:174-198` | requires henry manual resume via Telegram /resume |

---

## §3. Gap analysis — 100% compliance TODOs

| # | Gap | Art.14 clause | Priority | Fix |
|---|---|---|---|---|
| G-1 | KillSwitch state process-global in-memory only. Container restart → history lost. | 14(4)(e) + 14(1) | **P0** | Persist `_history` + state to Postgres `kill_switch_audit` table; hydrate on boot. Art.19 5-year retention. |
| G-2 | `HumanOversightGuard._approved_actions` single-process set. Restart → approvals lost. | 14(4)(d) | **P0** | Back approvals with Redis/DB; scope session+user+action hash. |
| G-3 | No HITL UI for pending approvals (only Telegram + API). | 14(4)(b) | P1 | Dashboard `PendingApprovalsPanel`; risk level + diff preview + TTL. |
| G-4 | `/observability/readiness` requires auth. Compliance auditor may not have token. | 14(4)(a) | P1 | Add `GET /compliance/public-readiness` (sanitized). |
| G-5 | No Art.14(5) dual-control flow. Single approver only. | 14(5) if Annex III | P1 (N/A today) | `ApprovalRequest.approvers: list[str] + min_approvers: int`. |
| G-6 | `require_kill_switch_inactive()` only in `Pipeline.run()`. BrainFlow/MCPBridge/AutoDev entry points unguarded. | 14(4)(e) must cover ALL ops | **P0** | Insert guard at top of each entry path. Teszt: `test_halt_enforced_across_all_entry_points` (jelenleg xfail). |
| G-7 | Kill switch lacks hardware-independent channel (HTTPS only). DNS/cert fail → no halt. | 14(4)(e) | P1 | Telegram `/stop` command with Henry-only auth. |
| G-8 | Art.14 status `.planning/SECURITY_MAPPING.md:363` marked "IMPLEMENTED (partial)" — no machine-readable tag. | Art.13 overlap | P2 | `architecture/compliance.yaml` per-article status + evidence + test id. |
| G-9 | No test suite asserting all 3 tiers E2E. | 14(4)(a)(d)(e) | **P0** | `tests/test_eu_ai_act_compliance.py` — **DONE 2026-04-20** ✓ |
| G-10 | No deployer-facing Instructions for Use (IFU, Art.13(3)(b)(iv)). | Art.13/14 | P2 | Publish `COMPLIANCE.md`. |
| G-11 | `OutputSanitizationGuard` skips plan/metadata/capabilities unless `output` key present. | 14(4)(c) | P2 | Enforce post-exec mode for MEDIUM+ risk tasks. |
| G-12 | `RBAC` requires `governance.manage` to activate kill switch. Compromised admin → no fallback. | 14(4)(e) emergency | P1 | Document break-glass → kill-switch chain; `system_admin` immutable. |

---

## §4. Test suite — `tests/test_eu_ai_act_compliance.py`

**Létrehozva:** 2026-04-20 (7 test, 6 PASS + 1 xfail)

- ✅ `test_observability_readiness_endpoint_available` (L1)
- ✅ `test_kill_switch_halts_pipeline` (L3, Python)
- ✅ `test_kill_switch_endpoint_admin_only` (L3, HTTP)
- ✅ `test_hitl_oversight_guard_blocks_until_approved` (L2)
- ✅ `test_audit_chain_integrity` (Art.12)
- ✅ `test_transparency_metadata_on_automated_actions` (Art.13 overlap)
- ⚠️ `test_halt_enforced_across_all_entry_points` (Gap G-6 — xfail until fix lands)

Run: `.venv/bin/pytest tests/test_eu_ai_act_compliance.py -v`

---

## §5. Art.14(5) Biometric Dual-Control — Applicability

**Assessment:** NOT directly applicable to OCCP today.
- Art.14(5) applies to Annex III point 1(a) (remote biometric identification).
- OCCP has **no biometric identification module** (confirmed: 0 matches for biometric/face/fingerprint in codebase).

**Voluntary dual-approver for CRITICAL actions recommended (P1):**
- Kill-switch deactivation after SECURITY trigger
- `architecture/governance.yaml` + boundary immutable file edits
- Production deploy after canary rollback

**Implementation sketch** (`autodev/approval_queue.py:46-64` extension):
```python
@dataclass
class ApprovalRequest:
    ...
    min_approvers: int = 1
    approvers: list[str] = field(default_factory=list)
    # resolve when len(approvers) >= min_approvers AND none rejected
```

Wire to `HumanOversightGuard.OVERSIGHT_REQUIRED` with per-action min_approvers:
- `governance.override` → 2
- `token.rotate_all` → 2
- routine policy updates → 1

---

## §6. Sprint P0 (4 hét, 2026-08-02 előtt)

- **W1**: G-6 — wire `require_kill_switch_inactive()` into `brain_flow` / `mcp_bridge` / `autodev.orchestrator`
- **W2**: G-1/G-2 — persist kill-switch + HITL state to Postgres
- **W3**: AAI01/AAI05 (OWASP) — run `PromptInjectionGuard` on memory_store.write() + inter-agent hand-offs
- **W4**: G-8 — publish `architecture/compliance.yaml` + `COMPLIANCE.md`

---

## Evidence files

- `architecture/governance.yaml` (immutable + L6 markers + kill-switch triggers)
- `policy_engine/guards.py` (5 guards incl. HumanOversightGuard L279-357)
- `policy_engine/engine.py` (decision record + hash chain L399-433)
- `evaluation/kill_switch.py` (L3 halt primitive)
- `api/routes/governance.py` (kill-switch endpoints L196-280)
- `api/routes/observability.py` (L1 readiness L146-176)
- `autodev/approval_queue.py` (HITL L2)
- `.planning/SECURITY_MAPPING.md` §4 (Art.9-61 mapping L356-367)
- `tests/test_eu_ai_act_compliance.py` (NEW — 2026-04-20)

---
*v1.0 · 2026-04-20 · security-analyst agent output*
