---
name: risk-check
description: Evaluate task risk level and assign execution tier before agent dispatch
user-invocable: true
command-dispatch: tool
command-tool: policy_evaluate
---

## Risk Classification

Assign one of three tiers to every incoming task before execution begins.

**HIGH (manual approval required):**
- Production deploy, database migration on live system
- Force push, branch deletion, git history rewrite
- Credential rotation, secret management, API key ops
- DNS cutover affecting live traffic
- Bulk data deletion or schema DROP

**MEDIUM (review before delivery):**
- Staging deploy or non-critical VPS changes
- Third-party API integration (new external calls)
- WordPress plugin activation on live site
- Payment or billing configuration changes
- Any operation affecting >100 users

**LOW (auto-execute):**
- Content creation, copy writing, design briefs
- Research and analysis tasks
- Local file edits, non-deployed code generation
- Read-only database queries
- Test generation and execution in CI

## Output Format
```json
{
  "risk_tier": "LOW|MEDIUM|HIGH",
  "reasons": ["production deploy detected", "DNS change"],
  "requires_human": true,
  "block_execution": false
}
```

## Quality Criteria
- When in doubt, escalate to MEDIUM (fail-safe principle)
- Log every HIGH decision with full task context to audit trail
- Never downgrade a HIGH classification based on agent confidence alone
