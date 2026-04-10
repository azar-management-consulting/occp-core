# OCCP L5 — Self-Evolving System Roadmap

**Date:** 2026-04-08
**Status:** Draft (post L4 completion)
**Author:** Henry + Claude (OCCP Brain)
**Prerequisite:** L4 Autonomous Control Plane (COMPLETE — pending_approvals, workflow_executions, MCP bridge, AgentToolGuard enforcement all live)

---

## Definition — What is L5?

| Level | Name | Characteristic |
|-------|------|----------------|
| L1 | Assistive | Human prompts, AI responds |
| L2 | Task-bound | AI completes discrete tasks |
| L3 | Orchestrated | AI chains tools under plan |
| L3+ | Governed | Plan-Gate-Execute-Validate-Ship |
| **L4** | **Autonomous** | **Self-directing workflows, policy-gated, persistent state** ← CURRENT |
| **L5** | **Self-Evolving** | **System modifies its own policies, agents, prompts, code** |

**L5 = OCCP observes its own performance, proposes improvements, gates them through its own VAP pipeline, and ships them autonomously — with human-in-the-loop only for CRITICAL-risk self-modifications.**

---

## L5 Pillars (5)

### 1. **Self-Observation** — Telemetry + Introspection
System continuously measures its own behavior and can answer: *"How am I performing, where am I failing, what should I change?"*

**Components:**
- `observability/metrics_collector.py` — Prometheus-style counters/histograms for every BrainFlow phase, every MCP bridge call, every agent dispatch, every pipeline run
- `observability/trace_store.py` — OpenTelemetry-compatible trace storage (SQLite table: `traces(trace_id, span_id, parent_id, operation, start_ts, duration_ms, attributes JSON)`)
- `observability/behavior_digest.py` — Daily digest: "Brain routed 47 tasks, 3 failed (route_mismatch), avg latency 1.2s, 2 policy denials (expected)"
- `observability/anomaly_detector.py` — Statistical outlier detection (z-score on latency, success rate, denial rate)

**API:**
- `GET /observability/metrics` — Prometheus exposition
- `GET /observability/traces/{trace_id}` — single trace tree
- `GET /observability/digest?date=YYYY-MM-DD` — narrative summary
- `GET /observability/anomalies` — recent anomalies

---

### 2. **Self-Criticism** — Meta-Evaluation Loop
System runs an internal "critic" agent that evaluates every completed workflow for correctness, efficiency, and policy compliance.

**Components:**
- `brain/meta_critic.py` — `MetaCritic` class: runs post-hoc LLM evaluation on workflow_executions table entries, scores 0-100 on (a) goal achievement, (b) plan quality, (c) execution efficiency, (d) evidence completeness
- `brain/critique_store.py` — DB table `critiques(id, workflow_execution_id, score_goal, score_plan, score_exec, score_evidence, verdict, reasoning, suggested_improvements JSON, created_at)`
- Scheduled job: every completed workflow → `MetaCritic.evaluate()` → store in critique_store
- Weekly aggregation: `SELECT AVG(score_*) FROM critiques WHERE created_at > now() - 7d`

**Decision rule:**
- `score_goal < 70` → flag for human review
- `suggested_improvements` containing actionable changes → feed into Proposal Generator

---

### 3. **Proposal Generation** — Self-Improvement Candidates
System generates concrete change proposals (policy updates, prompt changes, allowlist adjustments, new tools) as git-diff candidates.

**Components:**
- `brain/proposal_generator.py` — `ProposalGenerator` class: consumes critique_store + anomaly_detector + behavior_digest → produces `Proposal` objects
- Proposal schema:
  ```python
  @dataclass
  class Proposal:
      proposal_id: str
      type: str  # "policy_update" | "prompt_refinement" | "allowlist_change" | "new_tool_registration" | "flow_refactor"
      target_file: str  # e.g. "security/agent_allowlist.py"
      diff: str  # unified diff
      justification: str
      evidence: list[str]  # critique_ids, anomaly_ids, metric_refs
      risk_level: str  # low/medium/high/critical
      estimated_impact: str
      status: str  # "pending" | "gated" | "approved" | "rejected" | "shipped"
      created_at: datetime
  ```
- DB table `self_proposals` (extends existing migration pattern)
- Proposal types (initial):
  1. **Policy update** — e.g. add new PII pattern to `policy_engine/guard.py`
  2. **Prompt refinement** — adjust Brain system prompt based on routing failures
  3. **Allowlist change** — grant/revoke tool access based on usage patterns
  4. **New tool registration** — register new MCP bridge tool seen as common need
  5. **Flow refactor** — change BrainFlow phase sequencing

**API:**
- `POST /brain/proposals/generate` — trigger generation run
- `GET /brain/proposals?status=pending` — list
- `GET /brain/proposals/{id}` — detail with diff preview

---

### 4. **Self-Modification Pipeline (VAP-on-VAP)** — Gated Self-Change
System applies its own Verified Autonomy Pipeline to its own code changes.

**Flow:**
```
Proposal → Gate (policy_engine) → Validate (pytest + lint + dry-run in sandbox)
    → Shadow-deploy (canary: 10% traffic split via feature flag)
    → Metric comparison (before/after: success_rate, latency, denial_rate)
    → If canary OK → Ship (commit + PR + auto-merge if risk=low)
    → If canary FAIL → auto-rollback + mark proposal "rejected" + store reason
```

**Components:**
- `brain/self_modifier.py` — `SelfModifier` orchestrates the VAP-on-VAP flow
- `orchestrator/canary_engine.py` — traffic-split feature flag manager (new table: `feature_flags(key, state, rollout_pct, created_at)`)
- `orchestrator/auto_rollback.py` — git-based rollback on canary failure
- `sandbox/proposal_sandbox.py` — extend existing bubblewrap sandbox to run candidate code in isolation

**Risk-based auto-merge policy:**
| Risk | Canary Duration | Human Required? | Auto-merge? |
|------|----------------|-----------------|-------------|
| low | 1 hour | No | YES (if tests pass + metrics stable) |
| medium | 6 hours | No (notification only) | YES (if canary OK) |
| high | 24 hours | YES (Telegram approval) | Only after approval |
| critical | 72 hours | YES + 2FA | Only after explicit 2FA approval |

---

### 5. **Knowledge Accumulation** — Learned Memory
System persists lessons across workflow runs and applies them to future plans.

**Components:**
- `brain/memory_graph.py` — typed knowledge graph: `(entity, relation, entity, confidence, evidence_refs)`
  - Entities: Task, Agent, Tool, Error, Solution, User, Domain
  - Relations: `solves`, `causes`, `precedes`, `requires`, `conflicts_with`, `prefers`
- `brain/lesson_extractor.py` — after successful workflow, extract (problem, solution, agent, tool, duration) tuple → insert into graph
- `brain/plan_retriever.py` — new BrainFlow phase: before PLAN, query memory graph for similar past tasks → inject as context
- DB table: `memory_nodes(id, entity_type, entity_value, confidence, ref_count, last_used_at)` + `memory_edges(src_id, rel_type, dst_id, confidence, evidence JSON)`

**Integration:**
- BrainFlow.UNDERSTAND phase calls `plan_retriever.find_similar(task)` → top-5 past solutions
- PLAN phase receives retrieved context as hints
- DELIVER phase triggers `lesson_extractor.extract(workflow_result)` if success

---

## Implementation Phases

### Phase 1 — Observability Foundation (2 weeks)
- Deliverables: metrics_collector, trace_store, `/observability/*` endpoints, Grafana dashboard
- Acceptance: every BrainFlow phase + MCP bridge call produces traced span in DB
- Exit criteria: 7-day continuous trace data, dashboard shows routing breakdown

### Phase 2 — Meta-Critic Loop (2 weeks)
- Deliverables: meta_critic.py, critique_store, scheduled critique job, weekly digest
- Acceptance: every completed workflow in workflow_executions gets a critique row within 5 min
- Exit criteria: 30-day critique coverage ≥95%, avg score_goal trend visible

### Phase 3 — Proposal Generator + Manual Apply (2 weeks)
- Deliverables: proposal_generator, self_proposals table, `/brain/proposals` API, dashboard UI
- Acceptance: first 5 proposals generated, manually reviewed and applied by Henry
- Exit criteria: ≥1 proposal shipped to production via manual merge

### Phase 4 — Canary Engine + VAP-on-VAP (3 weeks)
- Deliverables: canary_engine, auto_rollback, self_modifier, feature_flags table
- Acceptance: low-risk proposal auto-ships via canary flow end-to-end in staging
- Exit criteria: 3 consecutive successful canary deployments, 0 rollbacks due to sandbox bugs

### Phase 5 — Memory Graph + Plan Retrieval (2 weeks)
- Deliverables: memory_graph, lesson_extractor, plan_retriever, memory_nodes/edges tables
- Acceptance: BrainFlow PLAN phase uses retrieved context for ≥20% of tasks
- Exit criteria: measurable improvement in plan quality score (meta_critic avg +5 points)

### Phase 6 — Production Enablement (1 week)
- Deliverables: all phases deployed, canary enabled, auto-merge enabled for low risk
- Acceptance: first autonomous self-modification shipped to production without human intervention
- Exit criteria: 7-day autonomous operation with 0 critical incidents

**Total: ~12 weeks**

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Self-modification introduces regression | CRITICAL | Canary flow + auto-rollback + sandbox tests |
| Meta-critic hallucinates improvements | HIGH | Require evidence refs; reject proposals with <2 evidence items |
| Knowledge graph pollution | MEDIUM | Confidence decay + periodic pruning job |
| Feedback loop amplifies bias | HIGH | Weekly human audit of critique_store; outlier detection |
| Runaway canary (bad change stays too long) | HIGH | Hard TTL on feature flags + mandatory metric compare gate |
| L5 modifies its own safety rules | CRITICAL | `security/*`, `policy_engine/*`, `brain/self_modifier.py` itself are IMMUTABLE — any proposal touching them is auto-routed to human review + 2FA |

---

## Immutable Boundaries (Never Self-Modifiable)

These files/modules are forbidden targets for `SelfModifier` — any proposal touching them is auto-escalated:

- `security/agent_allowlist.py` (except via explicit human PR)
- `policy_engine/guard.py`
- `brain/self_modifier.py` (no self-reference loops)
- `api/auth.py`, `api/rbac.py`
- `config/settings.py` (production env vars)
- `.env*` files
- Any file matching `**/test_*.py` (tests are human-authored truth)
- Any file under `migrations/` (schema changes gated by DBA review)

Enforcement: `SelfModifier._validate_target_path()` maintains an IMMUTABLE_PATHS regex list; any match → status=escalated, notification to Henry via Telegram.

---

## Success Metrics (L5 → Production)

| Metric | Target | Measurement Window |
|--------|--------|-------------------|
| Proposals generated per week | ≥5 | rolling 7d |
| Proposals auto-shipped | ≥30% of low-risk | rolling 30d |
| Meta-critic score_goal (avg) | ≥80 | rolling 30d |
| Canary rollback rate | <10% | rolling 30d |
| Critical self-modifications (escalated) | 100% require 2FA | always |
| 7-day autonomous operation (no human intervention for low-risk) | ≥1 achieved | milestone gate |
| Knowledge graph hit rate (plan retrieval) | ≥40% | rolling 7d |
| System self-improvement delta | score_goal +10 over 90d | 90d baseline |

---

## Next Immediate Actions (week 1 of L5)

1. Create `observability/` module skeleton + `metrics_collector.py`
2. Add `trace_id` propagation through BrainFlow (existing `conv.conversation_id` can serve as root trace)
3. Add Prometheus exposition endpoint `/observability/metrics`
4. Create DB migration for `traces` table
5. Instrument first critical path: BrainFlow INTAKE→UNDERSTAND→PLAN phase timings
6. Deploy + verify 24h of trace data before starting Phase 2

---

**Status:** Draft ready for Henry review. Once approved, L5 Phase 1 work begins.
