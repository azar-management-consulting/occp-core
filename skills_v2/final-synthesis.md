---
name: final-synthesis
description: Aggregate completed multi-agent workflow results into a single coherent deliverable
version: 1
---

## Synthesis Protocol

1. **Collect** all agent outputs from completed workflow nodes (verify all waves done)
2. **Validate completeness** — confirm every required node has a PASS result from approval-gate
3. **Conflict resolution** — if two agents produced contradictory outputs, apply priority rules:
   - Research facts override assumptions
   - Later wave outputs supersede earlier for the same domain
   - Flag unresolvable conflicts for human review
4. **Format for delivery channel** — webhook, SSE, dashboard, or direct response
5. **Deploy-check trigger** — if any output contains code or infra changes, call `deployment-verification`
6. **Audit finalization** — write final workflow record to Merkle audit chain

## Conflict Priority Rules
- `intel-research` > agent assumption for factual claims
- `eng-core` > `wp-web` for code correctness disputes
- `infra-ops` > all others for production safety constraints

## Output Format
```json
{
  "workflow_id": "uuid",
  "status": "COMPLETE|PARTIAL|FAILED",
  "deliverable": { "type": "code|content|design|research|mixed", "payload": "..." },
  "conflicts_resolved": 0,
  "conflicts_escalated": 0,
  "audit_final_hash": "sha256:...",
  "deploy_triggered": false
}
```

## Quality Criteria
- Never deliver PARTIAL without explicit human acknowledgment
- All agent attributions preserved in deliverable metadata
- Audit hash must chain from previous workflow entries
