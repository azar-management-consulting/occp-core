# OCCP Managed Agents PoC

Proof-of-concept integration with Anthropic's **Managed Agents** beta
(header `managed-agents-2026-04-01`). The PoC ships a single agent,
`deep-web-research`, plus the thin HTTP wrapper in
`adapters/managed_agents_client.py`.

## What it does

Given a natural-language `query`, the agent runs up to 20 turns of
web-search + code-execution tool calls and returns a structured JSON
report of the form:

```json
{
  "claims": [ { "claim": "...", "confidence": 0.8, "caveats": "..." } ],
  "sources": [ "https://..." ]
}
```

## Running locally

1. Set your API key — the client will refuse to initialise without it:

   ```bash
   export OCCP_ANTHROPIC_API_KEY=sk-ant-…
   ```

2. Start the OCCP API (`uvicorn api.app:app --reload`) and POST:

   ```bash
   curl -N -X POST http://127.0.0.1:8000/api/v1/managed-agents/research \
     -H 'content-type: application/json' \
     -d '{"query": "state of DORA Act enforcement in Q1 2026", "depth": "deep"}'
   ```

   The response is an SSE stream of partial tokens; the final event is
   the structured JSON report.

3. Check the session state:

   ```bash
   curl http://127.0.0.1:8000/api/v1/managed-agents/status/<session_id>
   ```

## Cost expectation

Opus-4.7 pricing (2026 schedule) combined with 10 web-search uses +
2–3 code-execution calls runs roughly **$0.40–$0.60 per research
task**. The `BudgetPolicy` pre-flight check in the route enforces a
USD ceiling before any session is opened.

## Audit & logs

Every session creation, message, and completion event is appended to
the OCCP `AuditStore` (see `store/audit_store.py`) via the standard
hash-chained audit log. Inspect the trail via:

```bash
curl http://127.0.0.1:8000/api/v1/audit/recent?actor=managed-agents
```

## Safety guards

* Kill-switch check at route entry (`require_kill_switch_inactive()`)
* Per-task USD budget check (`BudgetPolicy.check`) before session open
* API key is never logged in full
* Client raises `NotConfigured` on startup if no key is present
