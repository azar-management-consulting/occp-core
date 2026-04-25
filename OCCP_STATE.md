# OCCP — Valós állapot-leírás

**Frissítve:** 2026-04-23 · **HEAD:** `a56157b` · **Prod:** `v0.10.1`

> Ez a dokumentum az első blokk egy új session számára. Ha beleillesztődsz, elég ezt elolvasnod, utána tovább tudsz dolgozni. Semmi hallucináció, minden állítás mellé `file:line` vagy URL evidence.

---

## 1. MI AZ OCCP (1 bekezdés)

**OpenCloud Control Plane** — AI agent governance platform. Tulajdonos: **Azar Management Consulting** (Budapest, EU). Küldetés: EU AI Act Art.14-kompatibilis, auditálható, visszavonható, policy-korlátozott autonóm agent-futtatás. Nyílt mag (CE) + tervezett zárt enterprise (EE). Célpiac: EU enterprise AI-governance + US platform teams.

## 2. ARCHITEKTÚRA (5 komponens)

| Komponens | Felelősség | Path |
|---|---|---|
| `orchestrator/` | Verified Autonomy Pipeline (Plan → Gate → Execute → Validate → Ship) | orchestrator/pipeline.py |
| `policy_engine/` | policy-as-code, guards, BudgetPolicy (cost cap) | policy_engine/engine.py, budget_policy.py |
| `adapters/` | MCP bridge (14 built-in + 6 external tool), LLM planner, executors | adapters/mcp_bridge.py |
| `evaluation/` | kill switch (Redis-backed) + evals | evaluation/kill_switch.py |
| `store/` | SQLite (prod) / Postgres (Supabase-ready), audit chain SHA-256 | store/audit_store.py |

**Frontend:** `dash/` (dashboard) · `landing-next/` (marketing) · `docs-next/` (docs, Fumadocs 16) · `cli-create-app/` (CLI) · `templates/hello-agent/` (starter).

## 3. TECH STACK (locked, 2026)

- Backend: Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic
- Frontend: Next.js 16.2, React 19.2, Tailwind v4.1 (OKLCH), Geist font
- i18n: next-intl v4 (landing/docs), 7 locale (en/hu/de/fr/es/it/pt) · dash client-side v1
- UI: shadcn/ui, cmdk, Sonner, Motion 11, Recharts, Lucide
- Docs: Fumadocs 16.8 + Scalar OpenAPI
- Observability: OTEL gen_ai → Phoenix / Langfuse + Prometheus + Grafana
- Infra: Docker compose + Caddy reverse proxy (brain self-host, Cloudflare front)

## 4. PROD INFRASTRUKTÚRA

### Szerverek

| Node | IP | Lokáció | Szerep |
|---|---|---|---|
| hetzner-occp-brain (AZAR) | `195.201.238.144` | Falkenstein fsn1 | OCCP core + MainWP |
| hetzner-openclaw | `95.216.212.174` | Helsinki hel1 | OpenClaw gateway + 8 agent |

### Containerek a brain-en (iter-10 után mind healthy)

```
occp-api-1      healthy  → api.occp.ai
occp-dash-1     healthy  → dash.occp.ai (+ /v2/*)
occp-landing-1  healthy  → v2.occp.ai (Caddy)
occp-docs-1     healthy  → docs.occp.ai (Caddy)
occp-caddy-1    running  → :3300 reverse proxy
```

### Public endpoints (mind live)

| URL | HTTP | Szerep |
|---|---|---|
| `https://api.occp.ai/api/v1/status` | 200 | FastAPI status |
| `https://api.occp.ai/docs` | 200 | Swagger UI |
| `https://api.occp.ai/redoc` | 200 | ReDoc |
| `https://api.occp.ai/openapi.json` | 200 | OpenAPI spec (Scalar source) |
| `https://api.occp.ai/metrics` | 200 | Prometheus 6 SLO metrika |
| `https://dash.occp.ai/` | 200 | Mission Control |
| `https://dash.occp.ai/v2/{pipeline,agents,audit,mcp,settings,admin}` | 200 | v2 dashboard |
| `v2.occp.ai` (DNS wiring várat) | — | landing brain container él |
| `docs.occp.ai` (DNS wiring várat) | — | docs brain container él |

### Telegram

- Bot: `@OccpBrainBot` (id `8682226541`)
- Owner chat: `8400869598`
- Token: `OCCP_VOICE_TELEGRAM_BOT_TOKEN` env (brain `/opt/occp/.env`)
- Régi `@occp_bot` (id `8363737445`) **REVOKED**

## 5. REPO STRUKTÚRA (gyökér)

```
occp-core/
├── api/              FastAPI routes (28 router), middleware, auth, rbac
├── adapters/         MCP bridge, planners, executors (30 file)
├── orchestrator/     Pipeline, brain_flow, autodev
├── policy_engine/    Guards, engine, budget_policy
├── evaluation/       kill_switch, kill_switch_redis, evals
├── store/            Audit, task, conversation, agent, user, cost_calculator
├── observability/    OTEL, metrics_collector, gen_ai_tracer, phoenix_exporter
├── managed_agents/   Claude Managed Agents PoC (beta 2026-04-01)
├── skills_v2/        19 skill anthropics YAML formátumban
├── autodev/          AutoDev orchestrator (self-evolving)
├── cli/              occp CLI parancsok
├── cli-create-app/   npx create-occp-app (scaffolder)
├── templates/hello-agent/  20-LoC starter
├── sdk/              Python + TypeScript kliens
├── tests/            3157 tests (Python), eval/ + smoke/
├── dash/             Next.js 16 dashboard (+ v2/)
├── landing-next/     Next.js 15 marketing (7 locale, self-host)
├── docs-next/        Fumadocs 16 docs (EN full + 6 locale placeholder)
├── docs/             legacy markdown docs
├── landing/          legacy HTML landing (még occp.ai alatt)
├── infra/
│   ├── caddy/        Caddyfile + reverse proxy config
│   ├── grafana/      Grafana + Prometheus + Alertmanager compose
│   ├── observability/  Phoenix + Langfuse compose + DEPLOY.md
│   └── runbook/      telegram-rewire.md
├── supabase/         Postgres migration 23 tables + pgvector HNSW
├── migrations/       Alembic (prod-guard flag)
├── config/           settings, openclaw prompts, MCP tool schemas
├── i18n/             AGENTS.md (team doc)
├── .planning/        22 szintézis + research doc + SESSION_1.md
├── .github/workflows/  ci.yml + deploy.yml + smoke-ci.yml + eval-ci.yml
├── vercel/           README (unused — self-host választva)
├── Dockerfile.api    Python 3.13-slim, non-root occp:1001
├── docker-compose.yml  api + dash + landing + docs + caddy + dash-dev + tests
└── .env.example      env var reference
```

## 6. ITERÁCIÓK (mit szállítottunk, tömören)

| Iter | Dátum | Szállítás | Commit |
|---|---|---|---|
| 1 | 2026-04-20 | Baseline: OTEL, kill switch, budget, cost calc, 19 skills, audit 9 col | `27f6c61..bb8161f` (13) |
| 2 | 2026-04-21 | CLI fix, Geist swap, Brian SSE, Fumadocs scaffold, Vercel prep | `21db81b..ee35a79` |
| 3 | 2026-04-21 | EU AI Act G-6 closure, executor budget, v2 pages, eval CI, Scalar | `21affbb` |
| 4 | 2026-04-21 | Postgres dual-backend, 5 MCP adapter, Managed Agents PoC, skills_v2, Phoenix | `81031ca` |
| 5 | 2026-04-21 | 6 SLO metrika, SSRF+SQLi fix, feature flag, smoke tests | `c836e83` |
| 6 | 2026-04-21 | a11y WCAG 2.2 AA, SEO JSON-LD, WP MCP, hero anim, sparkline | `71992b9` |
| 7 | 2026-04-21 | Deep research + world-class redesign, next-intl v4 i18n 7 locale | `a52b2c8` |
| 8 | 2026-04-22 | Landing components full translation, handoff doc | `566a6eb..c1f73da` |
| 9 | 2026-04-22 | **PROD SYNC** 34 commit, `/metrics` public, dash v2 flag | `ccce380`, `20dddf2` |
| 10 | 2026-04-22 | Brain self-host landing+docs+Caddy, Telegram rewire, sec audit 2 CRITICAL+6 HIGH fix | `d09118a..a56157b` (8) |

## 7. MÉRHETŐ ÁLLAPOT

| Metrika | Érték |
|---|---|
| Python regression | **3157 PASS + 0 real fail** |
| Frontend tesztek | **20/20** (dash 11 + landing 4 + cli 3 + hello 2) |
| Production smoke | **7/7** prod ellen |
| Build exit 0 | dash / landing / docs mind ✅ |
| npm audit | 0 vulnerability |
| Security audit | 0 CRITICAL / 0 HIGH open |
| Skills migrálva | 19/19 skills_v2/ |
| MCP tools | 14 built-in + 6 external adapter (supabase, github, playwright, cloudflare, slack, wordpress) |
| Docs MDX | 16 EN + 6 locale (index + quickstart) |
| i18n locale | 7 (en default, hu/de/fr/es/it/pt) |

## 8. MÉG HENRY-RE VÁRÓ KÉZI FELADATOK

| # | Feladat | Hol | Idő |
|---|---|---|---|
| 1 | Slack bot token + signing secret rotate | api.slack.com/apps | 2' |
| 2 | GitHub PAT `ghp_aUU*` revoke | github.com/settings/tokens | 30" |
| 3 | Cloudflare DNS `v2.occp.ai`, `docs.occp.ai` → brain IP (proxy ON) | CF dashboard | 3' |
| 4 | Cloudflare Origin Rule → HTTP port 3300 | CF dashboard | 1' |
| 5 | Phoenix + Grafana compose up | brain SSH + `infra/observability/DEPLOY.md` | 5' |
| 6 | Supabase EU-Central projekt + alembic migráció | supabase.com + brain SSH | 15' |
| 7 | `occp.ai` cutover legacy HTML → új landing-next | Cloudflare + brain | 5' |
| 8 | 3 design partner outreach (első ügyfél) | LinkedIn/email | 4 hét |

## 9. KÖVETKEZŐ SESSION — HOGY LÉPJ BE

```bash
# 1. Reality Anchor (kötelező első 7 parancs)
cd "/Users/BOSS/Desktop/AI/MUNKA ALL /OCCP ALL/OCCP/occp-core"
git fetch && git log --oneline -3 && git status -sb
curl -sS https://api.occp.ai/api/v1/status | python3 -m json.tool
curl -sS https://api.occp.ai/metrics | head
.venv/bin/pytest tests/ -q -k "not e2e and not loadtest and not smoke" 2>&1 | tail -3
ssh -i ~/.ssh/id_ed25519 root@195.201.238.144 "docker ps --format '{{.Names}} {{.Status}}' | grep occp"

# 2. Cél-doc: ez a fájl (OCCP_STATE.md) + .planning/OCCP_FINAL_DELIVERY_PROMPT_v2.md
# 3. Ha nem egyezik a valóság ezzel a doc-kal → STOP + update OCCP_STATE.md ELŐSZÖR
```

## 10. KÖTELEZŐ SZABÁLYOK (nem alkuképes)

1. **ZERO hallucináció** — minden állításhoz `file:line` vagy URL evidence. `FELT:` prefix minden feltételezésre.
2. **Reality-first** — minden session REALITY ANCHOR-ral kezd.
3. **PROD-SAFE** — prod deploy, force push, credential rotation csak user approval-lel.
4. **Evidence-driven DONE** — 100% csak akkor, ha: pytest pass-szám + build exit 0 + curl 200 + audit-hash citált.
5. **Sub-agent bash DENY** — delegált agentek csak Read/Edit/Write. Bash/git/test mindig main context.

---

**Kapcsolódó docs (read-after-this):**
- `.planning/SESSION_1.md` — teljes iter-1..5 narratív handoff
- `.planning/OCCP_FINAL_DELIVERY_PROMPT_v2.md` — Azar startup vision + done-definíció
- `.planning/OCCP_10_OF_10_ROADMAP.md` — teljes technikai roadmap
- `.planning/EU_AI_ACT_ART14_COMPLIANCE_MAPPING.md` — 12 gap státusz (G-6 closed)
- `CLAUDE.md` — OCCP fejlesztési szabvány
- `README.md` — public repo doc
- `CHANGELOG.md` — per-version changes

**v1.0 · 2026-04-23 · iter-10 zárás · Brian the Brain ready for iter-11**
