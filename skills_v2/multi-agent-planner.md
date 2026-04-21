---
name: multi-agent-planner
description: Decompose a complex multi-domain task into a DAG workflow with wave-based execution
version: 1
---

## Planning Protocol

1. **Domain extraction** — identify all domains present in the task (max 8)
2. **Dependency mapping** — determine which agents need outputs from others before starting
3. **Wave assignment** — group independent agents into the same wave (parallel execution)
4. **Node specification** — for each node define: agent_id, sub_agent, skill, input_from, timeout
5. **Trust assignment** — assign L0-L5 trust level per node based on risk-check output
6. **Topological sort validation** — verify no circular dependencies exist in DAG

## Wave Rules
- Wave 0: research and content discovery (no dependencies)
- Wave 1: design and copy (depends on research)
- Wave 2: implementation (depends on design/copy)
- Wave 3: QA and optimization (depends on implementation)
- Wave N: deployment (depends on QA pass)
- Final wave: `approval-gate` + `final-synthesis` always last

## Output Format
```json
{
  "workflow_id": "uuid",
  "waves": [
    {
      "wave": 0,
      "nodes": [
        { "node_id": "n1", "agent": "intel-research", "sub_agent": "market-research",
          "skill": "deep-web-research", "depends_on": [], "timeout_s": 120 }
      ]
    }
  ],
  "total_nodes": 6,
  "estimated_duration_s": 480
}
```

## Quality Criteria
- Maximum 50 nodes per workflow (safety cap)
- Maximum 8 agents in parallel per wave
- Every workflow ends with `approval-gate`
