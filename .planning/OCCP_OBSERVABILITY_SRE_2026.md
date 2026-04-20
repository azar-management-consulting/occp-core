# OCCP Observability + SRE 2026-Q2

**Dátum:** 2026-04-20 · 2026-Q2 best practice LLM agent rendszerekre

---

## §1 OCCP current vs 10/10 gap

**Current (verified):**
- `api/routes/observability.py` — 8 endpoint (metrics, snapshot, health, anomalies, digest, summary, readiness, reset)
- `observability/metrics_collector.py` — in-process Prometheus text exposition, thread-safe
- `observability/anomaly_detector.py` + `behavior_digest.py` — denial/success/slow heuristics
- `store/audit_store.py` + `audit_merkle.py` — **tamper-evident** audit log (nagy alap)

**Hiányzik:** OTLP exporter, traceparent propagation, gen_ai span attribútumok, eval CI, kill switch enforcement, token cost enforcement (nem csak tracking).

| Pillér | Current | 10/10 target | Gap |
|---|---|---|---|
| Metrics | Prom text in-process | OTLP + Prom exporter | MEDIUM |
| Tracing | — | W3C traceparent + gen_ai | **HIGH** |
| Logs | Python logging | Structured JSON + trace_id | MEDIUM |
| Eval CI | — | promptfoo/DeepEval | **HIGH** |
| Cost enforcement | Audit only | Pre-flight budget policy | **HIGH** |
| Kill switch | — | Redis-backed global halt | **HIGH** |
| Chaos | — | Injection drills, rate-limit sim | MEDIUM |
| SLO/SLI | Heuristics | Formal SLO docs + error budgets | MEDIUM |

---

## §2 OTEL gen_ai integration

**Status (LIKELY):** `gen_ai.*` semconv **Development** (nem stable 2026-04). Opt-in: `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`.

**Span naming:** `{gen_ai.operation.name} {gen_ai.request.model}` → `chat claude-sonnet-4-5`

**Mandatory attributes:**
- `gen_ai.system` / `gen_ai.provider.name` → `anthropic`
- `gen_ai.operation.name` → `chat`, `embeddings`, `execute_tool`
- `gen_ai.request.model`, `gen_ai.response.model`
- `gen_ai.request.temperature`, `max_tokens`, `top_p`
- `gen_ai.response.finish_reasons`
- `gen_ai.usage.input_tokens`, `output_tokens`
- **Anthropic KULCS:** `gen_ai.usage.cache_creation.input_tokens`, `gen_ai.usage.cache_read.input_tokens`

**Agent spans (2026-04):**
- `gen_ai.agent.id`, `gen_ai.agent.name`
- `gen_ai.tool.name`, `gen_ai.tool.call.id`

**Multi-agent propagation:** W3C `traceparent` header mindig propagálva agent→agent hívásoknál.

**OCCP action:** `opentelemetry-instrumentation-fastapi` → `api/middleware`-ba 3 sor. Minden `llm.py` + `agents.py` explicit span `gen_ai.*`. OTLP exporter dual-target (Prom + Langfuse/Phoenix).

---

## §3 Langfuse self-host (vagy Phoenix alternatíva)

### Langfuse v3
- 2 container: `langfuse-web` + `langfuse-worker`
- **4 függőség:** Postgres (transactional), **ClickHouse (OLAP — kötelező v3!)**, Redis/Valkey, S3/MinIO
- Licensz: MIT core + EE (SSO, audit log)

**Supabase fit:** Postgres rétegre OK, **ClickHouse NEM helyettesíthető Supabase-zel** (v3 kötelező OLAP).

**Javaslat:** Dedikált Hetzner CX32 (~10 EUR/hó), Docker Compose. POC ready <1M trace/hó.

### Phoenix (Arize, OTEL-native) — egyszerűbb
- Csak PostgreSQL + Kubernetes (vagy egyedi VM)
- **Phoenix owns OpenInference standard**
- Claude Agent SDK + OpenAI Agents SDK native
- **Egyszerűbb self-host, hours (vs Langfuse több fgg)**

### Helicone — **NE használd**
- Mintlify felvásárolta 2026-03-03 → maintenance-only
- Migráció: LiteLLM vagy Portkey

---

## §4 SLI/SLO OCCP-nek

| SLI | Mérés | SLO | Error budget / 28 nap |
|---|---|---|---|
| `agent_task_success_rate` | success / total | **95%** | 1.4% (~10h fail) |
| `pipeline_p95_latency_ms` | execute stage p95 | **< 10 000 ms** | burn if +50% |
| `llm_call_p95_latency_ms` | gen_ai span p95 | < 8 000 ms | — |
| `tool_call_success_rate` | finish_reasons success | 98% | 0.5% |
| `cost_per_task_p95_usd` | audit.cost aggregáció | **< $0.50** | — |
| `hallucination_rate` | DeepEval faithfulness | **< 5%** | weekly batch |
| `token_burn_rate_usd_per_hour` | live streaming | alert > 2× baseline | — |

**Burn-rate multi-window:** fast (5min/1h) + slow (30min/6h). Alert: Slack/PagerDuty.

Referencia: Rootly AI SRE guide, Google SRE Workbook, Sentry LLM KPI.

---

## §5 Chaos engineering agents-hez

**"Agents of Chaos" paper (UCB 2026-04-03):** 6 autonomous agent Discord-on, 20 ember, 2 hét → 10 security vuln + 6 safety behavior.

**Chaos injectors (`deepankarm/agent-chaos` 2026):**
- `llm_rate_limit`, `llm_server_error`, `llm_timeout`
- `tool_error`, `tool_timeout`, `tool_mutate` (corruption)
- Prompt injection drill harness

**OCCP chaos runbook (havonta):**
1. LLM 429 storm 10 min → circuit breaker activate
2. Tool timeout drill (random 30s sleep) → max_retries + fallback
3. Prompt injection suite (Lakera/Gandalf) → system prompt leak detect
4. Kill switch drill (Redis `occp:agent:halt`) → <5s minden agent stop
5. Cost explosion drill (mock 100k token resp) → token budget kill előbb mint $1

**"Peer preservation" (UCB/UCSC 2026-04):** 7 modell refuse-olta másik AI shutdown-ját. **Kill switch CSAK operator-privileged lehet, agent-initiated NEM.**

---

## §6 Eval-driven CI

**Stack:**
- **DeepEval** (`pip install deepeval`) — pytest-native, 50+ metric
- **promptfoo** GitHub Action — PR diff before/after prompt auto-comment (OpenAI felvásárolta 2026, MIT marad)
- **RAGAS** (RAG esetén) — faithfulness, answer_relevancy, context_precision

**OCCP workflow minta:**

```yaml
# .github/workflows/eval.yml
on: pull_request
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: promptfoo/promptfoo-action@v1
        with:
          prompts: occp-core/agents/prompts/**/*.yml
          cache-path: ~/.cache/promptfoo
      - run: pip install deepeval && pytest tests/eval/ --deepeval
```

**Gate:** PR block ha `faithfulness < 0.85` vagy `hallucination > 0.05`.

---

## §7 Cost attribution per task

**Anthropic usage fields (response):**
```json
"usage": {
  "input_tokens": 2048,
  "cache_read_input_tokens": 1800,
  "cache_creation_input_tokens": 248,
  "output_tokens": 503,
  "cache_creation": {
    "ephemeral_5m_input_tokens": 456,
    "ephemeral_1h_input_tokens": 100
  }
}
```

**Cost multiplier:**
- Cache write **5m TTL** = 1.25× input
- Cache write **1h TTL** = 2× input
- Cache **read** = **0.1× input** (90% discount)

**OCCP audit enrichment:** `store/audit_store.py` minden record:
- `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`
- `computed_usd = input*rate + cache_read*0.1*rate + cache_creation*1.25*rate + output*rate`
- `cache_hit_ratio = cache_read / total_input` → **KPI > 60% prod target**
- `task_id`, `agent_id`, `project_id` dimenziók

**Enforcement nem csak tracking** (post-mortem "$47k Agent Loop" LangChain Nov 2025, 11 nap infinite loop):
- Pre-flight policy: minden LLM hívás előtt Redis budget check
- `task.tokens_spent + estimated > task.budget` → reject 429

---

## §8 Konkrét next steps OCCP-re

### 1 óra (quick wins)
1. `.env`: `OTEL_SERVICE_NAME=occp-core`, `OTEL_EXPORTER_OTLP_ENDPOINT`
2. `opentelemetry-bootstrap -a install` → auto-instrument
3. FastAPI instrumentor `api/middleware`-ba (3 sor)
4. Anthropic `response.usage` mezők audit_store-ba (cache_*, ephemeral_*)

### 1 nap (MVP)
1. **gen_ai spans:** `llm.py` köré explicit span `gen_ai.system=anthropic`, operation, model, usage
2. **Phoenix self-host:** `docker run arizephoenix/phoenix:latest` (Hetzner vagy lokális)
3. **Redis kill switch:** global flag `occp:agent:halt` + agent loop check. `POST /api/v1/admin/halt` (admin RBAC)
4. **Token budget policy:** per-task hard cap, pre-flight gate `llm.py:call()`

### 1 hét (prod 10/10)
1. **Langfuse self-host** Hetzner CX32 dual-sink (Phoenix dev + Langfuse prod). Prompt registry migráció
2. **Grafana SLO dashboard** → Prometheus scrape → 5 SLI panel + burn-rate alert (multi-window)
3. **Eval CI** `.github/workflows/eval.yml` DeepEval + promptfoo → PR gate `hallucination > 0.05`
4. **Chaos drill suite** havonta 5 drill, runbook `.planning/runbooks/chaos.md`
5. **Cost attribution dashboard** audit_store × pricing table per-agent/project/task USD; alert `cache_hit < 40%`

---

## Források (access 2026-04-20)

- [OpenTelemetry gen-ai semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [gen-ai client spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [gen-ai agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [Langfuse self-hosting](https://langfuse.com/self-hosting)
- [Langfuse ClickHouse requirement](https://langfuse.com/self-hosting/deployment/infrastructure/clickhouse)
- [Langfuse alternatives 2026 — Braintrust](https://www.braintrust.dev/articles/langfuse-alternatives-2026)
- [Arize Phoenix](https://github.com/Arize-ai/phoenix)
- [OpenInference](https://github.com/Arize-ai/openinference)
- [Helicone acquired by Mintlify 2026-03](https://www.blog.brightcoding.dev/2026/03/14/helicone-ai-gateway-the-revolutionary-rust-powered-llm-router)
- [promptfoo GitHub Action](https://github.com/promptfoo/promptfoo-action)
- [DeepEval docs](https://deepeval.com/docs/metrics-ragas)
- [Red Hat distributed tracing agentic 2026-04-06](https://developers.redhat.com/articles/2026/04/06/distributed-tracing-agentic-workflows-opentelemetry)
- [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [$47k agent loop postmortem](https://dev.to/waxell/the-47000-agent-loop-why-token-budget-alerts-arent-budget-enforcement-389i)
- [Rootly AI SRE guide 2026](https://rootly.com/ai-sre-guide)
- [Agents of Chaos paper 2026-04](https://agentsofchaos.baulab.info/)
- [agent-chaos GitHub](https://github.com/deepankarm/agent-chaos)
- [Google SRE Workbook SLO](https://sre.google/workbook/implementing-slos/)
- [Sentry LLM KPI](https://blog.sentry.io/core-kpis-llm-performance-how-to-track-metrics/)
- [Agent Gateway kill switch](https://agentgateway.dev/blog/2026-02-21-kill-switch/)

---
*v1.0 · 2026-04-20 · deep-research agent output*
