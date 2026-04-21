# `tests/eval/` — eval-driven CI foundation

Two-tier evaluation strategy for OCCP.

## Suites

| Suite     | Runs on       | Budget   | External calls | Files                        |
|-----------|---------------|----------|----------------|------------------------------|
| `offline` | every PR      | < 2 s    | none           | `test_*_offline.py`, snapshot, schema |
| `online`  | nightly only  | minutes  | real LLMs      | *future* (`test_*_online.py`) |

The `offline` suite is the only thing the PR gate depends on. It uses an
in-memory `MockPlanner` plus deterministic fixture files so reruns are bit-
identical.

## Add a golden fixture

1. Append a JSON line to `fixtures/golden_plans.jsonl`:
   ```json
   {"id": "eval-006", "input": "…", "expected": {"task_count_min": 1, "task_count_max": 5, "must_contain_any": ["…"], "risk_level": "low"}}
   ```
2. Re-run `pytest tests/eval/test_plan_eval_offline.py -q` locally.
3. If the `MockPlanner` heuristic rejects a realistic scenario, tune
   `_RISK_KEYWORDS_*` rather than loosening expectations.

## Regenerate snapshots

```bash
pytest tests/eval/test_prompt_snapshot.py --update-snapshot
```

This rewrites `snapshots/prompts.sha256` from whatever is currently in
`config/openclaw/prompts/`. Commit the updated snapshot alongside the prompt
change so the PR diff tells the full story.
