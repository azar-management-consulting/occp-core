# OWASP Agentic AI Top 10 Risks (2026 release) — OCCP Audit

**Dátum:** 2026-04-20
**Source:** OWASP GenAI Security Project — Agentic AI Top 10 (release 2025-12-09)
**URL:** https://genai.owasp.org/resource/agentic-ai-top-10-risks/
**Scope:** OCCP v0.10.0

---

## Summary

| ID | Title | State | Priority |
|---|---|---|---|
| AAI01 | Memory Poisoning | PARTIAL | **P0** |
| AAI02 | Tool Misuse | MITIGATED | P2 |
| AAI03 | Privilege Escalation | MITIGATED | P2 |
| AAI04 | Resource Overload | PARTIAL | P1 |
| AAI05 | Cascading Multi-agent Failure | PARTIAL | **P0** |
| AAI06 | Identity Spoofing | MITIGATED | P2 |
| AAI07 | Inadequate Human Oversight | PARTIAL | **P0** |
| AAI08 | Misaligned Goal | PARTIAL | P1 |
| AAI09 | Supply Chain | PARTIAL | P1 |
| AAI10 | Unsafe Output | PARTIAL | P1 |

**P0: 3** (AAI01, AAI05, AAI07) · **P1: 4** · **P2: 3**

---

## AAI01 — Memory Poisoning / Context Manipulation

**Desc:** Attacker injects persistent content into agent memory/RAG so later decisions are biased.

**OCCP state:** PARTIAL.

**Evidence:** `policy_engine/guards.py:75-154` `PromptInjectionGuard` runs at GATE. Memory writes referenced in `store/memory_store.py` (REQ-MEM-01 `.planning/SECURITY_MAPPING.md:135`). However memory-write injection guard marked PLANNED (Phase 3).

**Gap:** `PromptInjectionGuard.check()` NOT on `memory_store.write()` path. No per-entry integrity hash.

**Fix:** Enforce guard on every memory write; add per-entry SHA-256 + RBAC-filtered reads.

**Priority: P0.**

---

## AAI02 — Tool Misuse / Excessive Tool Privileges

**Desc:** Agent invokes legitimate tools with attacker-influenced arguments.

**State:** MITIGATED.

**Evidence:** `adapters/sandbox_executor.py` (nsjail/bwrap, IMPLEMENTED per SECURITY_MAPPING.md:290). Node-exec safe-command allowlist (`OCCP_SYSTEM_MANUAL.md:253-263`). MCP bridge capability declaration. `HumanOversightGuard.OVERSIGHT_REQUIRED` (`guards.py:293-302`).

**Gap:** Tool-call anomaly detection (sequence-based) PLANNED (SECURITY_MAPPING.md:220).

**Priority: P2** (monitoring enhancement).

---

## AAI03 — Privilege Escalation (Scope Drift)

**Desc:** Agent gains capabilities beyond declared trust level.

**State:** MITIGATED.

**Evidence:** `architecture/governance.yaml:89-101` `self_escalation → forbidden`. `policy_engine/trust_levels.py` + `engine.py:288-298` ABAC enforcement. Boundary immutable list includes governance.yaml + guards.py.

**Gap:** Runtime attestation that `boundaries.yaml` hash unchanged intra-session.

**Priority: P2.**

---

## AAI04 — Resource Overload / Cost Exhaustion

**Desc:** Recursive agent loops burn tokens / spawn unlimited subtasks.

**State:** PARTIAL.

**Evidence:** `policy_engine/guards.py:241-276` `ResourceLimitGuard` (timeout + max_output_bytes IMPLEMENTED). Recursion limits PLANNED (Phase 6). Budget guard PLANNED (Phase 5).

**Fix:** Ship Phase 5/6 — per-org hard budget envelope, recursion depth enforcement in `orchestrator/pipeline.py`.

**Priority: P1.**

---

## AAI05 — Cascading / Multi-agent Failure

**Desc:** Agent A's malicious output becomes Agent B's trusted input.

**State:** PARTIAL.

**Evidence:** `OutputSanitizationGuard` (`guards.py:157-238`) runs post-exec. BrainFlow 7-phase (`OCCP_SYSTEM_MANUAL.md:119-128`). Cascade-stop PLANNED (Phase 6).

**Fix:** Treat inter-agent messages as untrusted — re-run `PromptInjectionGuard` at each hand-off; cascade-stop kill-switch for multi-agent runs.

**Priority: P0.**

---

## AAI06 — Identity Spoofing / Agent Impersonation

**State:** MITIGATED.

**Evidence:** `api/auth.py` JWT + `api/rbac.py` PermissionChecker. `security/agent_allowlist.py` + `tests/test_agent_allowlist.py`. Casbin 4-tier RBAC.

**Gap:** Per-agent signed messages on internal bus (REQ-CPC-02 SLSA signing covers artifacts, not runtime messages).

**Priority: P2.**

---

## AAI07 — Inadequate Human Oversight (L1-L3 gaps)

**Desc:** Operator cannot understand, intervene, or halt. Overlaps EU AI Act Art.14.

**State:** PARTIAL (see `EU_AI_ACT_ART14_COMPLIANCE_MAPPING.md` §3 Gaps G-1…G-12).

**Evidence:** KillSwitch IMPLEMENTED (`evaluation/kill_switch.py`), HITL IMPLEMENTED (`autodev/approval_queue.py`), readiness IMPLEMENTED. But G-1 (non-persistent), G-6 (single-entry), G-3 (no UI) open.

**Fix:** Close gaps G-1/G-6/G-3.

**Priority: P0** (2026-08-02 Art.14 deadline).

---

## AAI08 — Misaligned Goal / Specification Gaming

**Desc:** Agent optimizes proxy metric, not intent.

**State:** PARTIAL.

**Evidence:** `orchestrator/pipeline.py` VALIDATE stage (`adapters/basic_validator.py` IMPLEMENTED). Proof-carrying outputs PLANNED (REQ-MAO-05).

**Fix:** Phase 6 proof-carrying outputs + regression scoreboard.

**Priority: P1.**

---

## AAI09 — Supply Chain Attack

**Desc:** Malicious/typosquatted skill, compromised MCP server, unsigned model artifact.

**State:** PARTIAL → MITIGATED roadmap.

**Evidence:** Typosquatting detection IMPLEMENTED (`security/supply_chain.py`, `tests/test_hardening.py`). SLSA provenance + cosign + SBOM + private registry PLANNED Phase 2 (`SECURITY_MAPPING.md:165-177`). Revocation `security/revocation.py` + tests exist.

**Fix:** Complete Phase 2 (8 controls). MCP servers currently run without runtime signature verification (REQ-MCP-03 PLANNED).

**Priority: P1.**

---

## AAI10 — Unsafe Output / Injection into Downstream

**Desc:** Agent output is executed/rendered unsanitized downstream (SQL, HTML, shell, tool-call).

**State:** PARTIAL.

**Evidence:** `OutputSanitizationGuard` (`guards.py:157-238`) IMPLEMENTED for PII/JWT/api_key/ip. Domain allow/deny + form approval for browser PLANNED Phase 7.

**Gap:** `OutputSanitizationGuard` skips `plan/metadata/capabilities` unless `output` key present (`guards.py:191-213`). Attacker-controlled plan fields pass through.

**Fix:** Enforce post-exec mode always for tasks with downstream execution.

**Priority: P1.**

---

## Sprint P0 (4 hét, 2026-08-02 előtt)

- **W1**: AAI07 G-6 — wire kill-switch guard into all entry points
- **W2**: AAI07 G-1/G-2 — persist kill-switch + HITL state
- **W3**: AAI01 + AAI05 — PromptInjectionGuard on memory writes + inter-agent
- **W4**: Audit + compliance.yaml publish

---

## References

- OWASP GenAI Security Project — Agentic AI Top 10 (2025-12-09)
- `.planning/EU_AI_ACT_ART14_COMPLIANCE_MAPPING.md` (OCCP Art.14 mapping, 2026-04-20)
- `.planning/SECURITY_MAPPING.md` — existing Art.9-61 + REQ mapping
- `tests/test_eu_ai_act_compliance.py` (2026-04-20)

---
*v1.0 · 2026-04-20 · security-analyst agent output*
