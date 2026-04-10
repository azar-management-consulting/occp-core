# RFC {NNNN}: {title}

**Status:** DRAFT | REVIEW | APPROVED | REJECTED | IMPLEMENTED
**Type:** architecture | policy | observability | migration | governance
**Author:** Claude Code (autonomous) | Henry (Fülöp Henrik) | other
**Created:** YYYY-MM-DD
**Target Release:** vX.Y.Z
**Risk Level:** low | medium | high | critical
**Affects Immutable Paths:** yes | no  (if yes → escalation required)
**Supersedes:** —
**Superseded by:** —

---

## 1. Summary

One-paragraph description of what this RFC proposes and why.

## 2. Motivation

What problem does this solve? Include evidence:
- Metric references (link to `/observability/metrics`)
- Critique references (`.planning/rfc/0000-critiques/*`)
- Runtime logs or audit entries (with timestamp + hash)
- Related issues or incidents

Do not write vague motivations. Cite.

## 3. Detailed Design

### 3.1 Current state
What exists today. Be specific: file paths, line numbers, module names.

### 3.2 Proposed change
Concrete diff preview. May include:
- New files (full path + purpose)
- Modified files (path + change summary)
- Deleted files (path + rationale)
- Schema changes (with migration plan)
- Config changes (with rollback plan)

### 3.3 Alternatives considered
At least 2 alternatives with pros/cons of each.

## 4. Impact Analysis

### 4.1 Affected components
List every service, agent, tool, dataflow, or boundary affected. Cross-reference `architecture/*.yaml`.

### 4.2 Compatibility
- Backward compatible? yes/no
- Forward compatible? yes/no
- Breaking API changes? list them

### 4.3 Risk assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| ... | low/med/high | low/med/high | ... |

## 5. Testing Plan

### 5.1 Unit tests
Files to add/modify under `tests/`.

### 5.2 Integration tests
End-to-end scenarios to verify.

### 5.3 Replay scenarios
Historical workflows from `workflow_executions` to replay against this change (cite execution_id).

### 5.4 Canary criteria
Metric thresholds for canary promotion. Cite current baseline from `/observability/snapshot`.

## 6. Rollout Plan

1. Feature flag: `{domain}.{feature}` (default OFF)
2. Deploy to staging
3. Run replay harness with N scenarios (target: 0 regressions)
4. Canary 10% for 1h → metric compare
5. Canary 50% for 4h → metric compare
6. Full rollout + monitor 24h
7. Remove feature flag after stable period

## 7. Rollback Plan

Explicit rollback steps, including:
- Git revert SHA range
- Feature flag flip
- DB migration downgrade (if applicable)
- Service restart commands

**Every RFC MUST have a tested rollback.**

## 8. Governance Check

- Affects immutable paths (see `architecture/boundaries.yaml`)? yes/no
- Requires human review? yes (always for non-autonomous_safe zones)
- Required reviewers: 1 | 2 | Henry + DBA | Henry + 2FA
- Self-escalation risk? yes/no — if yes, this RFC is auto-rejected

## 9. Success Criteria

- [ ] All tests pass
- [ ] Replay scenarios pass (0 regressions)
- [ ] Canary metrics stable
- [ ] Rollback tested
- [ ] Audit trail complete
- [ ] Monitoring in place

## 10. References

- Architecture YAML: `architecture/*.yaml`
- Governance: `architecture/governance.yaml`
- Baseline RFC: `.planning/rfc/0001-baseline.md`
- Related RFCs: —
- External docs: —
