# OCCP 10/10 ROADMAP — Végső szintézis

**Dátum:** 2026-04-20 · v1.0
**Forrás:** 5 párhuzamos deep-research (Anthropic Q2 / Frameworks / Observability / MCP / Python)
**Scope:** OCCP v0.10.0 LIVE → 10/10 rendszer 2026-Q4-ig

---

## Executive summary

**Jelenlegi érettség: 8.5/10** (v0.10.0 deploy, 2890 teszt, 96% L6, production stable).

**A 10/10-hez 5 kulcsváltozás:**

1. **Token economy 2026-Q2** — Managed Agents + prompt caching + model routing (Haiku/Sonnet/Opus) → **30-50% költség csökkenés** azonnal
2. **Enforcement, nem csak tracking** — Kill switch + budget policy pre-flight → `$47k loop` incident kategóriásan elkerülve
3. **OTEL + MCP standard** — 220 sor custom bridge kód elhagyható, industry-standard gen_ai spanok
4. **Simplify surgically** — LangGraph VAP-hoz (88% fit), Pydantic AI structured output-hoz; NE big-bang framework swap
5. **Postgres + distroless** — SQLite bottleneck feloldása, `<100MB` container image

**A 10/10 NEM új feature-ökről szól** — meglévő architektúra letisztítása, 2026-Q2 industry standardokra ráhúzása, enforcement réteg hozzáadása.

---

## Top 3 erősség megőrzendő

1. **Governance scaffold** (policy_engine, 5 guard, audit hash chain) — egyetlen framework sem fedi natívan
2. **2-szerveres jump host deploy** (Hetzner brain + openclaw) — blast-radius separation
3. **Scaffold → executor upgrade megtörtént** — directive parser mostantól valós execution (architectural limit feloldva)

---

## 30 akció 4 időhorizonton

### 🚀 NOW — 1 hét (quick wins, low risk, high ROI)

**Token economy:**
1. `tool_schema.json` **verziózás** (`tool_schema_v1.json`) → azonnal cache-hit rate javulás
2. Prompt registry explicit `cache_control: {type: "ephemeral", ttl: "1h"}` breakpoint system prompt végén
3. Model router minimális: intake → Haiku 4.5, research → Sonnet 4.6, architect → Opus 4.7

**Observability quick:**
4. `opentelemetry-instrumentation-fastapi` telepítés + `api/middleware` 3 sor → auto traceparent propagáció
5. Anthropic `response.usage` mezők (cache_read, cache_creation, ephemeral_5m/1h) rögzítése `audit_store`-ba
6. `.env` + `OTEL_EXPORTER_OTLP_ENDPOINT` (Langfuse/Phoenix)

**Python quick:**
7. `UV_COMPILE_BYTECODE=1` Dockerfile → -30% cold start
8. `asyncio.gather` → `TaskGroup` orchestrator.py → structured cancellation
9. `asyncio_mode = "auto"` pyproject → remove `@pytest.mark.asyncio` boilerplate
10. structlog `JSONRenderer` prod / `ConsoleRenderer` dev via `LOG_FORMAT` env

### 📅 SHORT — 1 hónap (MVP)

**Enforcement (NEM csak tracking):**
11. **Redis kill switch** global flag `occp:agent:halt` + agent loop check (1s interval). `POST /api/v1/admin/halt` RBAC admin
12. **Pre-flight token budget policy** `llm.py:call()`-ban. Ha `spent + estimate > budget` → 429 `X-OCCP-Budget-Exceeded`
13. **gen_ai spans** minden Anthropic hívás köré (`system=anthropic, operation=chat, model, usage.*`)
14. **Phoenix self-host** (Hetzner vagy container) dual OTLP sink

**MCP ecosystem adoption:**
15. `@modelcontextprotocol/server-filesystem` + `-fetch` bekötés → `adapters/mcp_bridge.py` 220 sor delete (34% redukció)
16. **Supabase MCP** bekötés (P0 — OM projekt DB management)
17. **Playwright MCP** (Microsoft official, replace Puppeteer)
18. **GitHub MCP** hivatalos bekötés

**Anthropic 2026-Q2 PoC:**
19. **Managed Agents PoC**: 1 OCCP agent (pl. `deep-web-research`) átírás session-be. Mérd latency/cost vs saját executor
20. **19 SKILL.md → `occp-skills` private repo** progressive disclosure YAML-lel → `/plugin marketplace add`
21. **Memory tool integráció** AutoDev-be (6 command handler, ZDR-compliant client-side)

### 📆 MEDIUM — 3 hónap (production 10/10)

**Observability 10/10:**
22. **Langfuse self-host** Hetzner CX32 (~10 EUR/hó), prompt registry migráció `langfuse.prompts` (audit trail, A/B)
23. **Grafana SLO dashboard**: 5 SLI panel + burn-rate alert multi-window (5m/1h + 30m/6h). Slack/PagerDuty
24. **Eval-driven CI** `.github/workflows/eval.yml`: DeepEval (`faithfulness > 0.85`, `hallucination < 0.05`) + promptfoo PR comment
25. **Chaos drill suite** havonta 5 drill (rate_limit storm, tool timeout, prompt injection, kill switch, cost explosion). Runbook `.planning/runbooks/chaos.md`

**Python modernization:**
26. **SQLite → Postgres (Supabase) migráció**: `aiosqlite` → `asyncpg`, `alembic init -t async`. **Critical:** port 5432 direct VAGY `statement_cache_size=0`
27. **Distroless container**: multi-stage `uv:0.11.7-python3.13-slim` builder → `distroless/cc-debian12` runtime. Target <100MB
28. **pyrefly dev-loop** (pre-commit) + mypy CI (conformance). Progressive strict: `security/` → `adapters/` → `orchestrator/`

**Framework adoption (targeted):**
29. **Pydantic AI** mint `structured_output` layer — policy_engine response → Pydantic model (alacsony risk, 1.84 production-stable)
30. **LangGraph pilot** VAP pipeline-ra (egy fázisban, nem big-bang). `AsyncPostgresSaver` checkpoint → OCCP audit_log mirror

### 🏁 LONG — 6 hónap (stratégiai)

- **Code Execution tool v3** (`code_execution_20260120`) → SandboxExecutor csere ahol nincs saját audit
- **Files API** dataset intake-re (retain-until-delete, non-ZDR)
- **Outcomes API** + multi-agent research preview → AutoDev success criteria
- **`brain-mcp` saját MCP server** — OCCP tools expose-olása más klienseknek (Claude Desktop, Cursor)
- **`mainwp-mcp` build** — 139 site OM projekthez
- **Cloudflare Code Mode MCP** vagy Managed Agents — költségoptimalizálás cost-hungry workflow-khoz

---

## Mit NE csinálj (anti-patterns + lock-in)

### Frameworks
- ❌ **Claude Agent SDK v0.1.x production** — 15 release Q1-Q2, breaking changes hetente. Várj v1.0-ra (2026-Q4 FELT)
- ❌ **Cloudflare Agents teljes rewrite** — Python→TypeScript 6+ hónap, edge lock-in
- ❌ **CrewAI** — role-metaphor ütközik OCCP policy-centric modelljével
- ❌ **Helicone** — Mintlify felvásárolta 2026-03, maintenance-only

### Architecture
- ❌ **Saját `wp-mcp`** — `WordPress/mcp-adapter` core WP 6.9+ óta
- ❌ **SQLite production multi-writer** — global write lock, 20+ connection → 20/22 fail
- ❌ **stdio MCP >20 concurrent** — Streamable HTTP kötelező scale-hez
- ❌ **Big-bang framework swap** — regresszió-risk kritikus governance réteggel

### Code
- ❌ `requirements.txt` + `pip freeze` → `uv.lock`
- ❌ `global` pool → lifespan + DI
- ❌ `print()` prod → structlog + OTel
- ❌ `asyncio.create_task` TaskGroup nélkül → orphaned tasks
- ❌ `Depends(get_db)` sync SQLA → event loop block
- ❌ Single Dockerfile → multi-stage builder+runtime

---

## Költség-becslés

| Intézkedés | LoC -/+ | Idő | Közvetlen megtakarítás |
|---|---|---|---|
| Prompt caching verzió + 1h TTL | +20 / 0 | 2 óra | **30-50% input token cost** |
| Model router (Haiku/Sonnet/Opus) | +100 / 0 | 4 óra | 40-60% cost ha intake nagy volumenű |
| MCP bridge consolidation | -220 / +50 | 2 nap | karbantartás -80h/év |
| Kill switch + budget policy | +150 / 0 | 1 nap | **$47k incident kategóriásan elkerülve** |
| Distroless container | 0 | 2 óra | image -70%, cold start -30% |
| Postgres migráció | +100 / 0 | 3 nap | concurrency unlock |
| OTEL gen_ai instrumentation | +200 / 0 | 2 nap | observability 10/10 |
| Langfuse self-host | 0 | 1 nap | prompt mgmt + tracing |
| Eval-driven CI | +300 / 0 | 2 nap | regression catch >80% |
| Managed Agents PoC | +200 / -400 | 1 hét | tovább-tervezhető (session cost $0.08/h) |

**Összesen (30 akció):** ~+1500 LoC új kód, ~-800 LoC delete, net +700 LoC. **Karbantartás -200h/év** (FELT). **Token cost -30-50% azonnal.**

---

## 5 SLO amit mérünk onnantól

| SLI | Target | Alert |
|---|---|---|
| `agent_task_success_rate` | 95% (28 nap) | burn rate > 2× baseline |
| `pipeline_p95_latency_ms` | < 10 000 ms | +50% növekedés |
| `cost_per_task_p95_usd` | < $0.50 | budget policy reject |
| `hallucination_rate` | < 5% (DeepEval) | weekly batch |
| `cache_hit_ratio` | > 60% | < 40% alert |

---

## Stratégiai döntés mátrix

| Opció | Ha... | Akkor |
|---|---|---|
| Managed Agents teljes adoption | Rövid-táv cost optimization fő cél | 2026-Q4 migráció |
| LangGraph VAP teljes | Crash recovery fájdalom élő prod-ban | 2026-Q3 migráció |
| Cloudflare edge | Globális <50ms latency stratégiai | Csak 2027 |
| Status quo + targeted upgrades | EU AI Act compliance + stability prioritás | **Ez a roadmap** ✓ |

---

## Kapcsolódó dokumentumok

- `.planning/OCCP_SIMPLIFICATION_ANTHROPIC_2026.md` — Managed Agents, Skills, Memory, Code Exec, model routing
- `.planning/OCCP_FRAMEWORK_SIMPLIFICATION_2026.md` — LangGraph/Pydantic AI/Temporal vs alternatívák
- `.planning/OCCP_OBSERVABILITY_SRE_2026.md` — OTEL gen_ai, Langfuse, Phoenix, SLO, chaos
- `.planning/OCCP_MCP_ECOSYSTEM_2026.md` — 10 bevezetendő MCP server, spec 2025-11-25
- `.planning/OCCP_PYTHON_MODERNIZATION_2026.md` — FastAPI, SQLA 2.1, uv, distroless, pyrefly
- `.planning/OCCP_100_PERCENT_CHECKLIST_2026-04-20.md` — eredeti 12-pontos gate
- `.planning/EU_AI_ACT_ART14_COMPLIANCE_MAPPING.md` — Art.14 12 gap + P0 sprint
- `.planning/OWASP_AGENTIC_TOP10_AUDIT_2026-04-20.md` — 10 risk (3 MITIGATED + 7 PARTIAL)

---

## Hazárd pontok

**`FELT:` (nem verifikált):**
- Pydantic v3 release 2026-Q3/Q4
- Claude Agent SDK v1.0 release 2026-Q4
- Managed Agents GA dátum
- Langfuse Supabase partial fit (Postgres OK, ClickHouse kötelező)
- Pytest 9.0 release timing
- Outcomes API public access

**Confirmed risk:**
- Supabase pooler port 6543 = **TÖR asyncpg prepared statements** — use 5432 OR `statement_cache_size=0`
- stdio MCP >20 concurrent = 20/22 fail → Streamable HTTP kötelező 139 site-hoz
- Claude Agent SDK v0.1.x = 15 release Q1-Q2 → **NE adoptálj pre-1.0 prod-ra**
- Helicone Mintlify acquisition = maintenance-only → NE új integráció

---

## Záró verdikt

**A 10/10 OCCP nem ambícióból, hanem higiéniából áll össze:**

1. **Token economy** (caching + model routing) — 1 hét, **biztos win**
2. **Enforcement** (kill switch + budget) — 1 hét, **biztos win** + `$47k incident` védelem
3. **Standard protokoll** (OTEL + MCP) — 1 hónap, **iparági standardra ráhúzás**
4. **Targeted simplification** (LangGraph + Pydantic AI pilotok) — 3 hónap, low risk
5. **Cloud-native** (Postgres + distroless + CI matrix) — 3 hónap, infra readiness

**NEM szükséges:**
- Big-bang framework swap
- Teljes rewrite Cloudflare-re
- Claude Agent SDK v0.1.x erőltetett adoption
- Custom observability saját Prometheus/Grafana fork

**Ami már 10/10 szintű:**
- Governance (VAP, 5 guard, immutable paths, audit hash chain)
- Tamper-evident audit log
- Scaffold→executor átmenet (2026-04-20 deployed)
- 2-szerveres topológia + jump host pattern
- 2890 zöld teszt

---

## 🎯 Next konkrét lépés

**Ajánlott első fél nap (4-6 óra fókuszált munka, 0 downtime):**

1. `tool_schema.json` verziózás → `tool_schema_v1.json`
2. `cache_control: {ttl: "1h"}` breakpoint system prompt végén
3. `audit_store` enrich — `cache_read_input_tokens`, `cache_creation_input_tokens`, `ephemeral_5m/1h`, `computed_usd`
4. OTEL auto-instrument FastAPI (3 sor)
5. `asyncio_mode = "auto"` pyproject
6. `UV_COMPILE_BYTECODE=1` Dockerfile
7. Deploy `scp` → brain `/opt/occp/` + `docker compose build api --no-cache && up -d`
8. Telegram notify: "OCCP v0.10.1 token-economy + OTEL deployed"

**Eredmény:** azonnali ~30% input cost csökkenés + full-stack traceparent propagáció. Nulla új framework.

**Ez a fél nap hozza a legnagyobb megtérülést a teljes 30-akciós roadmap-ből.**

---
*v1.0 · 2026-04-20 · 5 deep-research szintézis · Brian the Brain operational*
