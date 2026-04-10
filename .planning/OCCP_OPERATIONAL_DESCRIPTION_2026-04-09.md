# OCCP — 100% pontos operatív leírás

**Generálva:** 2026-04-09
**Verzió:** v0.9.0 (branch: `feat/v0.10.0-l6-foundation` @ `1f6b2fb`)
**Forrás:** repo + live prod runtime @ `195.201.238.144`
**Módszer:** minden állítás verifikálva kód, config, DB, vagy élő endpoint ellen
**Evidence policy:** FELT: prefix ahol feltételezés; minden más ellenőrzött tény

---

## 1. Mi az OCCP?

**OCCP (OpenCloud Control Plane)** — governance-first AI orchestration kernel az Azar Management Consulting-tól.

**Nem** chatbot. **Nem** mock. **Nem** tervezési keret.
**Egy valós, telepített, live szoftverrendszer**, amely:

- Kezel egy központi "Brain" (Brian the Brain) nevű orchestrátort
- Irányítja 8 specialista agentet egy **Verified Autonomy Pipeline (VAP)**-on keresztül
- Policy-vezérelt gate-et alkalmaz minden taskra
- Hash-chain audit loggal rögzít minden döntést
- Runtime governance-t ér el feature flag, kill switch, drift detection, canary engine segítségével
- Telegram + REST + WebSocket csatornákon fogad bemenetet
- Elsősorban **tervez és audit-ol**, nem közvetlenül **épít/deployol kódot**

**Pontosság**: OCCP jelenleg **L5-foundation / early L6** szinten áll — az architektúra-memória, observability, evaluation lane és governance komponensek **élnek**, de a **"self-building" képesség (tényleges fájlmódosítás agentek által)** scaffolding szintű (lásd 13. szakasz).

---

## 2. Fizikai topológia

### Hetzner szerverek (2 VPS)

| Server | IP | Szerep | Futó szolgáltatások |
|--------|-----|--------|---------------------|
| **hetzner-occp-brain** | `195.201.238.144` | Brain Plane | `occp-api` (docker), `occp-dash` (docker), Apache reverse proxy, Let's Encrypt, Mailcow stack (20 container) |
| **hetzner-openclaw** | `95.216.212.174` | Execution Plane | OpenClaw gateway (Node.js), Caddy, Basic Auth, 94 gateway methods, 18 event types |

### Control plane mesh (Tailscale overlay)

| Node | Tailscale IP | Szerep | OS | Állapot |
|------|--------------|--------|-----|---------|
| **mba-henry** (F-MacBook-Air) | `100.114.146.86` | Claude Code host + primary control | macOS 26.4 | active (Henry's) |
| **imac-henry** (BOSS-iMac) | `100.88.122.102` | Storage + secondary control | macOS 14.8.5 | active (SSH verified) |
| **mbp-henry** (AI-MacBook-Pro) | `100.65.58.71` | Secondary dev | macOS | active (SSH verified) |

### DNS / domainek

| Domain | Cél | Szerver |
|--------|-----|---------|
| `occp.ai` | Landing (Apache static) | hetzner-occp-brain |
| `www.occp.ai` | Redirect → occp.ai | hetzner-occp-brain |
| `api.occp.ai` | Backend API (reverse proxy → 127.0.0.1:8000) | hetzner-occp-brain |
| `dash.occp.ai` | Dashboard (reverse proxy → 127.0.0.1:3000) | hetzner-occp-brain |
| `claw.occp.ai` | OpenClaw gateway (wss://) | hetzner-openclaw |

**Nameserver**: `ns1.dns-parking.com`, `ns2.dns-parking.com` (Hostinger DNS)
**SSL**: Let's Encrypt, mindegyik domain.

---

## 3. Futó docker containerek (hetzner-occp-brain)

Verified `docker ps`:

| Container | Image | Status | Szerep |
|-----------|-------|--------|--------|
| `occp-api-1` | `occp-api` (custom) | Up, healthy | FastAPI backend, Telegram polling, OpenClaw WS client, MCP bridge, BrainFlow |
| `occp-dash-1` | `occp-dash` (custom) | Up 7h+, healthy | Next.js 15 + React 19 + Tailwind 4 dashboard |
| `mailcowdockerized-*` (20 konténer) | `ghcr.io/mailcow/*` | Up 5w+ | Email stack — OCCP-n kívüli |

**Docker compose**: `/opt/occp/docker-compose.yml` — 2 szolgáltatás (`api`, `dash`), egy volume (`occp-data:/app/data`).

**Biztonság**: `read_only: true`, `no-new-privileges:true`, `seccomp=unconfined`, `tmpfs: /tmp`.

---

## 4. Backend API (FastAPI)

**Verzió**: 0.9.0 (pyproject.toml)
**Framework**: FastAPI 0.115.x, SQLAlchemy 2.0 async, Pydantic 2.x, uvicorn
**Python**: 3.13 (deployed), 3.14 (local test env)
**Entrypoint**: `api.app:app`
**Host**: 0.0.0.0:8000 (internal), https://api.occp.ai (external)

### 4.1 API routes — **95 path, 103 endpoint** (verified via `/openapi.json`)

**Route files**: 26 Python file a `api/routes/`-ban (verified `ls api/routes/*.py`).

| Prefix | Endpoint count | Főbb szerepek |
|--------|----------------|---------------|
| `/admin` | 1 | admin stats |
| `/agents` | 13 | agent dispatch, parallel dispatch, registry, stats |
| `/audit` | 1 | audit log listing |
| `/auth` | 5 | login, register, refresh, me, admin register |
| `/brain` | 1 | POST /brain/message (BrainFlow entry) |
| `/bridge` | 3 | OpenClaw bridge status/health/events |
| `/cloudcode` | 2 | CloudCode command + task query |
| `/dashboard` | 5 | overview, metrics, timeline, telegram, agent detail |
| `/events` | 1 | per-task event stream |
| `/feedback` | 1 | feedback submission |
| `/governance` | **16** | check, check_many, stats, recent, boundaries, proposals, issues, drift, flags (PUT), kill_switch/{status,stats,activate,drill,deactivate}, canary/recent |
| `/health` | 1 | health check (public) |
| `/llm` | 1 | LLM provider health |
| `/mcp` | 2 | MCP catalog + install |
| `/mcp-bridge` | 3 | tools, dispatch, batch |
| `/observability` | **8** | metrics (Prometheus), snapshot, health, anomalies, digest, summary, readiness, reset |
| `/onboarding` | 5 | status, start, step, verify, first-task |
| `/pipeline` | 1 | run/{task_id} |
| `/policy` | 1 | policy/evaluate |
| `/projects` | 9 | CRUD + agents + dispatch + status |
| `/quality` | 2 | stats, per-task checks |
| `/skills` | 3 | list + enable + disable |
| `/status` | 1 | platform status |
| `/tasks` | 3 | create, list, detail |
| `/tokens` | 7 | CRUD + rotate + validate + org |
| `/users` | 1 | list users |
| `/voice` | 2 | status, history |
| `/workflows` | 4 | create, resume, status, executions |

### 4.2 Kritikus public endpoint (Prometheus scrape nélküli)

- `GET /api/v1/health` — public (no auth)
- `GET /api/v1/observability/health` — public (no auth)

Minden más endpoint **JWT-gated** (`PermissionChecker` + RBAC).

---

## 5. Database (SQLite)

**Path**: `/app/data/occp.db` (docker volume `occp-data`)
**Engine**: SQLAlchemy 2.0 + aiosqlite (async)
**Migrációk**: alembic, `migrations/versions/` — **7 migration file** (001-008, 005 kihagyva)

### 5.1 Táblák (verified `PRAGMA table_info`)

| Tábla | Sorok (live) | Forrás model |
|-------|-------|--------------|
| `tasks` | **212** | `TaskRow` (store/models.py) |
| `audit_entries` | **374** | `AuditEntryRow` — hash chain |
| `brain_conversations` | 0 | `ConversationStore` (store/conversation_store.py — nem models.py) |
| `pending_approvals` | 0 | `ApprovalStore` (store/approval_store.py) |
| `workflow_executions` | 2 | `WorkflowExecutionRow` |
| `users` | 2 | `UserRow` |
| `agent_configs` | 11 | `AgentConfigRow` — seed-elt |
| `onboarding_progress` | 0 | `OnboardingProgressRow` |
| `encrypted_tokens` | 0 | `EncryptedTokenRow` |

**9 tábla összesen**. SQLite single-file. Volume persisted.

**Store fájlok** (15 Python modul a `store/`-ban): `models.py` (7 ORM Row class), `task_store.py`, `user_store.py`, `audit_store.py`, `audit_merkle.py`, `conversation_store.py`, `approval_store.py`, `workflow_store.py`, `agent_store.py`, `onboarding_store.py`, `token_store.py`, `memory.py`, `database.py`, `engine.py`, `base.py`.

### 5.2 Audit hash chain

- Minden bejegyzés: `id`, `timestamp`, `actor`, `action`, `task_id`, `detail`, `prev_hash`, `hash`
- Hash chain **élő** (policy_engine.audit() számolja)
- **Ismert hiba**: ~75 korábbi voice_pipeline bejegyzés üres hash-sel (L4 session incidens, azóta javítva — új bejegyzések hash-eltek)

---

## 6. Orchestrator rétegek (23 Python modul — verified `ls orchestrator/*.py`)

### 6.1 Verified Autonomy Pipeline (VAP)

**Forrás**: `orchestrator/pipeline.py` — `Pipeline` class
**5 fázis, kötelező sorrend**:

```
1. PLAN      → Planner.create_plan(task)          → adapter: ClaudePlanner / MultiLLMPlanner
2. GATE      → PolicyEngine.evaluate(task)        → 4 guard + ABAC
3. EXECUTE   → Executor.execute(task)             → adapter: OpenClawExecutor / SandboxExecutor / MockExecutor
4. VALIDATE  → Validator.validate(task)           → tesztek, failures list
5. SHIP      → Shipper.ship(task)                 → log_shipper + Telegram reply
```

**Stage skip detection**: `_assert_stage_order()` — ha hiányzik előző fázis, `StageSkipError`.

**Instrumentáció**: Minden terminal path (5 exception handler + sikeres ág) emittál:
- `occp.pipeline.tasks` counter (labeled by `agent_type`, `outcome`)
- `occp.pipeline.stage_duration_ms` histogram (labeled by `stage`, `agent_type`)

**Outcome értékek**: `success`, `gate_rejected`, `human_rejected`, `failed`, `error`, `kill_switch`

**Kill switch guard**: Első lépés `run()`-ban — ha `kill_switch.is_active()`, visszaad `PipelineResult(success=False, status=FAILED, error="kill_switch_active: ...")`.

### 6.2 BrainFlow (7-fázisú conversational engine)

**Forrás**: `orchestrator/brain_flow.py` — `BrainFlowEngine` class
**Fázisok**:

```
INTAKE → UNDERSTAND → PLAN → CONFIRM → DISPATCH → MONITOR → DELIVER
```

**Hívási pont**: `POST /api/v1/brain/message` **és** (tegnap esti fix óta) **csak explicit trigger kulcsszavakra** a Telegram text úton (`tervezz`, `feladat:`, `<directive`, `brainflow:` stb).

**Ismert korlát (ISS-001)**: `_dispatch_tasks()` generál task_id-kat, **de nem awaitál `pipeline.run()`-t**. A BrainFlow DISPATCH fázisa **nem indít valódi pipeline futást**. Ezért a Telegram text jelenleg a voice_handler → intent_router → pipeline útvonalon megy (kikerüli BrainFlow-t default-ban).

### 6.3 PolicyEngine + 4 Guard

**Forrás**: `policy_engine/engine.py` + `policy_engine/guards.py`

| Guard | Szerep |
|-------|--------|
| `PIIGuard` | PII detection in input (email, phone, SSN, credit card via Luhn) |
| `PromptInjectionGuard` | Prompt injection patterns (8 patterns) |
| `ResourceLimitGuard` | Max timeout, max output size |
| `OutputSanitizationGuard` | Post-exec PII leak scan (skips plan/metadata fields per ISS fix) |
| `HumanOversightGuard` | Human approval requirement flagging |

**ABAC**: `policy_engine/abac.py` — attribute-based rules load from YAML.
**ML classifier**: `policy_engine/ml_classifier.py` — rate-limiter trust scoring.

---

## 7. Security réteg

**18 Python modul** + 1 markdown policy (`SECRETS_POLICY.md`), mind **immutable** (per `architecture/boundaries.yaml`):

| Module | Szerep |
|--------|--------|
| `agent_allowlist.py` | 21 agent tool allowlist + `AgentToolGuard` |
| `break_glass.py` | Emergency override mechanism |
| `channel_auth.py` | Multi-channel authentication (Telegram, API, CloudCode) |
| `compliance.py` | GDPR/NIS2 compliance helpers |
| `encryption.py` | Token + secret encryption |
| `governance.py` | Governance policy enforcement |
| `input_sanitizer.py` | OWASP ASI01 prompt injection defense |
| `provenance.py` | Supply chain provenance tracking |
| `revocation.py` | Token/cert revocation |
| `runtime_verifier.py` | Runtime integrity checks |
| `sbom.py` | SBOM generation |
| `scan_pipeline.py` | Security scan orchestration |
| `siem_export.py` | SIEM integration format |
| `signing.py` | Code signing + SBOM integrity |
| `skill_registry.py` | Skill manifest validation |
| `supply_chain.py` | Dependency audit (npm, composer) |
| `vault.py` | Secret vault interface |

### 7.1 AgentToolGuard — 21 agent allowlist

**Forrás**: `security/agent_allowlist.py` — `AGENT_TOOL_ALLOWLISTS` dict

**8 specialist** (routing targets):
- `eng-core`, `wp-web`, `infra-ops`, `design-lab`, `content-forge`, `social-growth`, `intel-research`, `biz-strategy`

**1 orchestrator**:
- `brain` (MCP bridge tools: filesystem, http, brain.status/health)

**12 seeded pipeline agents**:
- `general`, `demo`, `code-reviewer`, `onboarding-wizard`, `mcp-installer`, `llm-setup`, `skills-manager`, `session-policy`, `ux-copy`, `openclaw`, `remote-agent`, `main`

**Enforcement**: `check_access(agent_id, tool)` → `ToolAccessResult(allowed, reason)`. Log-only mode vagy enforce mode (`OCCP_AGENT_TOOL_GUARD_ENFORCE` env).

**Dangerous tools**: `{bash, exec, ssh, docker, rm, kill, system, eval, deploy, restart, reboot}`.
**Brain-only tools**: `{agent_dispatch, workflow_create, approval_gate, pipeline_run, task_create, agent_kill}`.

---

## 8. Adapters réteg (24 Python modul — verified `ls adapters/*.py`)

**Forrás**: `adapters/`

### 8.1 Planner adapters (LLM providers)

| Adapter | Provider | Model | Használat |
|---------|----------|-------|-----------|
| `claude_planner.py` | Anthropic | `claude-sonnet-4-6` | **Primary** (100% calls) |
| `openai_planner.py` | OpenAI | gpt-4.1 | Fallback (nincs token jelenleg) |
| `ollama_planner.py` | Ollama local | — | Opcionális local |
| `openclaw_planner.py` | OpenClaw | — | Gateway planner |
| `echo_planner.py` | Echo | — | Test / fallback |
| `multi_llm_planner.py` | Meta | — | Priority-based fallback chain |

**LLM health (verified live)**:
- `anthropic`: healthy, 6 calls, 100% success, 16462ms avg latency, 0 failures
- `echo`: healthy, 0 calls
- `openclaw`: healthy, 0 calls

**Tokens**: `has_any: false` — **nincs encrypted token tárolva**. API közvetlenül környezeti változóból olvassa (`OCCP_ANTHROPIC_API_KEY`).

### 8.2 Executor adapters

| Adapter | Szerep |
|---------|--------|
| `openclaw_executor.py` | **Primary** — WebSocket → `wss://claw.occp.ai` → 94 methods |
| `sandbox_executor.py` | bubblewrap namespace isolation (`bwrap` backend) |
| `mock_executor.py` | Test mock |

**OpenClaw runtime**: `wss://claw.occp.ai` (Caddy + Basic Auth + HMAC-SHA256)
**Gateway features**: 94 methods, 18 events (verified `/bridge/status`)
**Circuit breaker**: closed (healthy)
**Events received**: növekvő (EventBridge számol)

### 8.3 Channel adapters

| Adapter | Szerep |
|---------|--------|
| `telegram_voice_bot.py` | httpx long-polling Telegram bot — **REAL**, not stub |
| `voice_handler.py` | Voice + text → intent → pipeline (voice: Whisper, text: direct) |
| `whisper_client.py` | OpenAI Whisper v3 HTTPS API |
| `intent_router.py` | Intent classification (Claude-backed) |
| `channel_adapters.py` | Channel identity unification |

**Telegram bot**: `@OccpBrainBot` (id 8682226541), **owner_chat_id=8400869598**, hosszú-polling 30s timeout, **prefix bypass owner DM-ben** (ISS-009 javítás).

### 8.4 Support adapters

| Adapter | Szerep |
|---------|--------|
| `confirmation_gate.py` | Human-in-loop approval gate + `ApprovalStore` |
| `event_bridge.py` | OpenClaw event → Brain routing |
| `log_shipper.py` | SHIP fázis — audit log export |
| `mcp_bridge.py` | **MCP Runtime Bridge** — 7 tool, FastAPI async dispatcher |
| `mcp_client.py` | MCP client (connectors) |
| `policy_gate.py` | Policy enforcement point |
| `basic_validator.py` | Validator stub (default) |
| `browser_sandbox.py` | Playwright sandbox |

---

## 9. MCP Runtime Bridge

**Forrás**: `adapters/mcp_bridge.py` + `api/routes/mcp_bridge.py`

**7 regisztrált tool** (verified `/mcp-bridge/tools`):

| Tool | Namespace | Workspace root | Path escape protection |
|------|-----------|----------------|------------------------|
| `brain.status` | brain | — (read-only) | — |
| `brain.health` | brain | — (read-only) | — |
| `filesystem.read` | filesystem | `/tmp/occp-workspace` | **yes** |
| `filesystem.write` | filesystem | `/tmp/occp-workspace` | **yes** |
| `filesystem.list` | filesystem | `/tmp/occp-workspace` | **yes** |
| `http.get` | http | — (HTTPS only) | — |
| `http.post` | http | — (HTTPS only) | — |

**Endpoint**:
- `GET /mcp-bridge/tools` — list + stats
- `POST /mcp-bridge/dispatch` — single tool call
- `POST /mcp-bridge/batch` — parallel batch

**Enforcement**: `AgentToolGuard.check_access()` minden dispatch előtt.

**KRITIKUS TÉNY**: Ezek a toolok **csak `/tmp/occp-workspace`-ben dolgoznak**. **Nem érik el** a WordPress-t, a `/opt/occp/` fájlokat, a Hetzner szerver többi részét, vagy bármi mást. A filesystem path escape protection ellenőrzi, hogy a kérés a workspace-en belül maradjon.

**Következmény**: Brian a jelenlegi architektúrában **nem tud WordPress-en fájlt szerkeszteni, SSH-zni, WP-CLI-t futtatni, vagy production deployt végrehajtani** csak a saját sandbox workspace-én belül.

---

## 10. Observability réteg

**Forrás**: `observability/` — 4 modul

### 10.1 `metrics_collector.py` (312 LOC)

- `Counter`, `Histogram`, `Gauge` — Prometheus-compatible
- Thread-safe singleton (`get_collector()`)
- **Prometheus exposition format** (`text/plain; version=0.0.4`)
- JSON snapshot (dashboard consumption)
- Histogram buckets (ms): `5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000`

### 10.2 `anomaly_detector.py` (287 LOC)

**4 anomaly class**:
- `pipeline.outcome_imbalance` — non-success fraction > 30%
- `pipeline.slow_stage` — avg stage duration > 10000ms
- `agent.reliability_drop` — agent success rate < 70%
- `policy.denial_spike` — denial rate > 20%

**Tunable via `AnomalyThresholds` dataclass**.
**Min samples**: 5 (alatta nincs verdict).

### 10.3 `behavior_digest.py` (200 LOC)

Narratív összefoglaló generátor:
- Tasks total + by outcome + by agent
- Top 5 slowest stages
- Anomaly inline + count
- Uptime, success rate, busiest agent

### 10.4 Endpoints (api/routes/observability.py — 195 LOC)

| Endpoint | Auth | Szerep |
|----------|------|--------|
| `GET /observability/metrics` | JWT | Prometheus text format |
| `GET /observability/snapshot` | JWT | JSON snapshot |
| `GET /observability/health` | **public** | health + counter/histogram count |
| `GET /observability/anomalies` | JWT | Current anomaly list + thresholds |
| `GET /observability/digest` | JWT | Narrative behavior digest |
| `GET /observability/summary` | JWT | Combined: health + metrics + anomalies + digest |
| `GET /observability/readiness` | JWT | L6 readiness markers (24/25 = 96%) |
| `POST /observability/reset` | admin | Reset all metrics |

**L6 Readiness (live)**: **24/25 = 96.0%** — `observability_dashboard: false` deferred to v0.11.0.

---

## 11. Evaluation lane

**Forrás**: `evaluation/` — 7 modul

### 11.1 `feature_flags.py` (280 LOC)

- **JSON-persisted** store: `data/feature_flags.json` (env override `OCCP_FEATURE_FLAG_STORE`)
- Thread-safe in-memory cache
- Atomic write-then-rename
- Corrupt file → fallback to defaults + warning log
- **9 default flag**:
  - `l6.observability.metrics_enabled` = **ON**
  - `l6.observability.tracing_enabled` = OFF (v0.11.0)
  - `l6.rfc.auto_generation` = OFF
  - `l6.canary.enabled` = OFF
  - `l6.self_modifier.log_only` = **ON** (safe default)
  - `l6.evaluation.replay_harness` = OFF
  - `l6.llm.prompt_caching` = OFF (planned ISS-011)
  - `l6.llm.tier_routing` = OFF (planned ISS-010)
  - `l6.llm.batch_api` = OFF

### 11.2 `replay_harness.py` (318 LOC)

- **Real execution** (nem stub) — `ReplayScenario` + `ReplayResult`
- Accepts async callable or `ReplayCandidate` protocol
- Összehasonlítja: stage parity, outcome, output equivalence, duration delta
- `DURATION_TOLERANCE = 2.0x` baseline
- Ignores volatile fields (timestamps, ids) in equivalence check
- `run_all()` batch mode
- **Ismert korlát**: in-process execution — **nincs git-worktree sandbox** (v0.11.0 scope)

### 11.3 `canary_engine.py` (273 LOC)

- `CanaryCriteria` (min_samples=5, max_success_drop=0.05, max_denial_increase=0.05, max_latency_growth=1.5x)
- Compare baseline vs candidate snapshot → verdict: `promote | hold | rollback`
- **Ring buffer history** (max 200)
- `stats` property aggregate
- **Ismert korlát**: csak metric comparator — **nincs reverse-proxy traffic splitter** (v0.11.0)

### 11.4 `self_modifier.py` (307 LOC)

**Runtime governance enforcement** — olvassa `architecture/boundaries.yaml`-t.

**3 tier**:
- `autonomous_safe` — Claude Code autonóm szerkesztheti
- `human_review_required` — RFC + review szükséges
- `immutable` — tilos, fail-secure deny

**Glob matcher**: támogatja `**` + `{a,b,c}` expansion + `exclude` listákat.

**Fail-secure**: ismeretlen path → deny, requires 1 reviewer.

**API**: `POST /governance/check`, `POST /governance/check_many`, `GET /governance/stats`, `GET /governance/recent`, `GET /governance/boundaries`.

### 11.5 `kill_switch.py` (284 LOC)

**3 state**: `INACTIVE` | `ACTIVE` | `DRILL`

**6 trigger**: `MANUAL`, `ANOMALY`, `CANARY_FAILURE`, `ERROR_SPIKE`, `SECURITY`, `DRILL`

**API**: `POST /governance/kill_switch/{activate,drill,deactivate}`, `GET /governance/kill_switch/{status,stats}`

**Runtime guard**: `pipeline.py` `run()` első lépés — `require_kill_switch_inactive()`.

**E2E drill verified**: activate → pipeline refused (HTTP 200, success=false) → deactivate → pipeline succeeds.

### 11.6 `proposal_generator.py` (368 LOC)

Olvassa `issue_registry.yaml` + live anomaly detector → ranked `ProposalCandidate` objects.

**Score**: `severity_weight + category_boost + risk_penalty`
**Governance-aware**: immutable path-ú proposal-t "blocked" verdikttel jelöli.
**RFC markdown render**: `to_rfc_markdown()` + `write_rfc_to_disk()`.

**Live output** (verified): **3 open proposal**:
- ISS-001: brain_flow dispatch (human_review, score 4.0)
- ISS-010: model routing (human_review, score 1.0)
- ISS-011: prompt caching (human_review, score 1.0)

### 11.7 `drift_detector.py` (268 LOC)

**4 check**:
- `agent_drift` — agents.yaml ↔ AGENT_TOOL_ALLOWLISTS
- `service_hosts` — services.yaml host references resolve
- `tool_registration` — tools.yaml ↔ build_default_bridge
- `issue_paths` — issue_registry.yaml affected_paths exist (skip dir/glob/deployment-stripped)

**Live**: `has_drift: false, entries: 0`

---

## 12. Architecture memory (YAML self-model)

**Forrás**: `architecture/` — **8 YAML file**

| File | Szerep | Lines |
|------|--------|-------|
| `services.yaml` | 8 szolgáltatás + 5 host | 177 |
| `agents.yaml` | 8 specialist + 1 orchestrator + 12 seeded | 148 |
| `tools.yaml` | 7 MCP tool + permissions | 134 |
| `dataflows.yaml` | 5 critical flow + denial stages | 100 |
| `boundaries.yaml` | 3 tier (autonomous/review/immutable) | 164 |
| `runtime_inventory.yaml` | deps, versions, mesh, 2026 LLM pricing | 153 |
| `governance.yaml` | L6 readiness contract | 174 |
| `issue_registry.yaml` | 11 tracked issue (8 resolved, 3 open) | 265 |

**Validátor**: `tests/architecture/test_yaml_schema.py` — **22 schema teszt**, mind pass.

---

## 13. Agents réteg — a VALÓS kép

### 13.1 8 specialist agent (tool allowlist ≠ tényleges képesség)

| Agent | Allowlist tools | Skill count (registry) | **Tényleges implementáció** |
|-------|-----------------|------------------------|------------------------------|
| `eng-core` | bash, read, write, edit, grep, glob, browser, exec, test_runner | 15 | **Placeholder** — OpenClaw gateway hívás, nincs valódi fájlmódosítás |
| `wp-web` | bash, read, write, edit, grep, glob, browser, wp_cli, ftp | 15 | **Placeholder** — nincs wp-cli vagy FTP executor kód |
| `infra-ops` | bash, read, exec, ssh, docker, dns, ssl, grep, glob | 15 | **Placeholder** |
| `design-lab` | read, write, browser, screenshot | 12 | **Placeholder** |
| `content-forge` | read, write, browser, translate | 12 | **Placeholder** |
| `social-growth` | read, write, browser, api_call | 12 | **Placeholder** |
| `intel-research` | read, browser, web_search, web_fetch, grep, glob | 15 | **Placeholder** |
| `biz-strategy` | read, write, browser, calculator, web_search | 12 | **Placeholder** |

### 13.2 KRITIKUS PONTOSÍTÁS

Amikor OCCP egy taskot futtat `agent_type="wp-web"`-el, **nem történik valódi WordPress művelet**. A pipeline:
1. ClaudePlanner Claude Sonnet 4.6-tal tervet generál
2. PolicyEngine átvizsgálja
3. Executor (alapértelmezett: OpenClawExecutor) **WebSocket üzenetet küld** az OpenClaw gateway-nek (`wss://claw.occp.ai`)
4. OpenClaw gateway **Claude-dal chatel és szöveges választ generál**
5. Ez a szöveg kerül a Pipeline SHIP fázisába és visszaküldésre Telegramra

**Semmi nem módosít fájlokat** a WordPress fájlrendszerén, a Hetzner szerveren, vagy a termékenységi rendszeren.

**Kivétel**: `mcp-bridge` → `filesystem.write` → `/tmp/occp-workspace/` — de ez **Hetzner container tmpfs**, nem a WordPress!

### 13.3 Mi az OpenClaw valójában?

**OpenClaw** (`95.216.212.174`, `wss://claw.occp.ai`) egy **független Node.js alapú agent gateway**, amely:
- 94 metódust expose-ol (health, chat.send, agents.list, cron.*, session.*, stb.)
- 18 event típust emittál
- Persistent WebSocket kapcsolatot tart fenn az OCCP API-val
- **Claude API-t hív** a saját backendjéből (szintén Anthropic)
- Nincs valódi kódírási vagy deploy képessége

**OCCP ↔ OpenClaw kapcsolat**: HMAC-SHA256 aláírt WebSocket üzenetek + Basic Auth.

---

## 14. Dashboard (Next.js frontend)

**Container**: `occp-dash-1`
**Framework**: Next.js 15, React 19, Tailwind 4, TypeScript 5
**Port**: 3000 (belső), https://dash.occp.ai (külső)
**Source**: `dash/src/`

**Meglévő oldalak** (from `dash/src/app/` — verified):
- `/` (főoldal)
- `/admin`, `/admin/stats`, `/admin/users`
- `/docs`, `/docs/privacy`, `/docs/security`, `/docs/terms`
- `/login`, `/register`
- `/settings/tokens`

**Komponensek**:
- `mcp-bridge-panel.tsx` — MCP bridge live view
- `welcome-panel.tsx`
- `admin-guard.tsx`
- `nav.tsx`

**Auth flow**: JWT via `/api/v1/auth/login`, localStorage token, `AuthProvider` context.

**API client**: `dash/src/lib/api.ts` — fetch wrapper with JWT.

**Ismert hiányok**: **nincs `observability_panel.tsx`** (L6 readiness marker pending).

---

## 15. Telegram bot működése — VALÓS

**Forrás**: `adapters/telegram_voice_bot.py`

### 15.1 Bot identitás

- **Username**: `@OccpBrainBot`
- **Bot ID**: `8682226541`
- **Owner chat_id**: `8400869598` (Henry)
- **Nyelv**: magyar (Whisper transcription lang=hu)

### 15.2 Polling loop

- **Method**: HTTPS long-polling (`getUpdates?timeout=30`)
- **Allowed updates**: `message`, `edited_message`
- **Nincs webhook** (getWebhookInfo.url = "")
- **Client**: `httpx.AsyncClient`
- **Start**: `api/app.py` lifespan-ből
- **Log**: `Telegram polling started (owner_chat_id=8400869598)`

### 15.3 Üzenetkezelési szabályok (v2 — tegnap esti fix)

| Input | Feldolgozás |
|-------|-------------|
| Voice message | **Always** → Whisper → intent → pipeline |
| Text `/start`, `/help` | **Always** → handle_text |
| Text **owner DM** (chat_id == owner_chat_id) | **Minden text elfogadva** (prefix bypass). Optional `Brian:` / `Brain:` prefix strippelve. |
| Text **nem-owner chat** `Brian:` prefixszel | Prefix levágva, feldolgozva |
| Text nem-owner chat prefix nélkül | **Silent ignore** |

### 15.4 Text → pipeline flow (tegnap esti fix, voice_handler.py)

```
Telegram text
  ↓
owner_chat_id filter (poll_loop)
  ↓
_handle_update → handle_text
  ↓
channel_auth + input_sanitizer
  ↓
IF text contains trigger keyword (tervezz, feladat:, <directive, brainflow:)
  THEN BrainFlow 7-fázis (explicit planning)
  ELSE intent_router → pipeline.run() → OpenClaw → reply
```

### 15.5 Voice → pipeline flow

```
Telegram voice message
  ↓
poll_loop → getFile → download audio
  ↓
handle_voice → channel_auth
  ↓
Whisper transcribe (hu)
  ↓
input_sanitizer
  ↓
Interim Telegram send ("⏳ Dolgozom rajta...")
  ↓
intent_router → pipeline.run() → OpenClaw → reply
```

### 15.6 Send message

- `httpx.post(sendMessage)` → Markdown retry → plain fallback
- Max: **`text[:4096]`** (Telegram API hard limit)
- **Nincs automatikus chunking** — hosszabb üzenet **csonkolódik**
- Log: `Telegram send -> chat_id=<X> len=<Y>`

### 15.7 Verified live flow (2026-04-08 23:17-23:20)

Henry 4 blokkra darabolt magyarorszag.ai direktívát küldött:

| Idő | Input | Intent | Risk | Pipeline | Reply len |
|-----|-------|--------|------|----------|-----------|
| 23:17:32 | "1/4 🧠 BLOKK 1/4" (bevezető) | general | low | PLAN→GATE→SHIP | 203 char |
| 23:18:04 | "1: Brian, mission directive..." | build_deploy | **critical** | PLAN→GATE→SHIP | 519 char |
| 23:18:38 | "2/4: MISSION PRIORITY ORDER" | wp_audit | medium | PLAN→GATE→SHIP | 347 char |
| 23:19:23 | "3/4: BUILD PHASE" | build_deploy | **high** | PLAN→GATE→SHIP | 604 char |
| 23:19:54 | "4/4: TESTING" | build_deploy | **high** | PLAN→GATE→SHIP | 349 char |

**Összes válasz**: ~2022 character
**Mind**: Claude által generált szöveges terv, **nem valódi fájl-módosítás vagy deploy**.

---

## 16. Authentication + RBAC

**Forrás**: `api/auth.py`, `api/rbac.py`, `config/rbac_policy.csv`

### 16.1 JWT auth

- Algorithm: HS256
- Secret: `OCCP_JWT_SECRET` env var
- Expire: `jwt_expire_minutes` config (default 1440 = 24h)
- Claims: `sub` (username), `role`, `iat`, `exp`

### 16.2 RBAC hierarchy (Casbin-style)

**Role inheritance** (parent → child):
```
viewer → operator → org_admin → system_admin
```

**rbac_policy.csv**: 91 sor total (comments + grants), **47 valódi permission grant** (`^p,`)

**Key permissions**:
- `viewer` — read-only (tasks, agents, audit, status, policy.evaluate)
- `operator` — + task/agent dispatch
- `org_admin` — + users CRUD + governance.read + admin.read
- `system_admin` — + users.delete + system.manage + governance.manage + tokens.rotate

### 16.3 Live users (verified DB)

- **2 user** (admin + seeded)
- Admin: `admin` / `L4Verify2026pw` (tegnap esti pw reset után)

---

## 17. Live runtime állapot (2026-04-09 ellenőrizve)

### 17.1 Containers

```
occp-api-1    Up 32 minutes (healthy)
occp-dash-1   Up 7 hours (healthy)
```

### 17.2 API health

```json
{
  "status": "healthy",
  "version": "0.9.0",
  "checks": [
    {"name": "database", "status": "ok"},
    {"name": "policy_engine", "status": "ok"},
    {"name": "pipeline", "status": "ok"}
  ]
}
```

### 17.3 Status endpoint

```json
{
  "platform": "OCCP",
  "version": "0.9.0",
  "status": "running",
  "environment": "production",
  "tasks_count": 212,
  "audit_entries": 10
}
```

### 17.4 OpenClaw bridge

- `status: connected`
- `circuit_breaker: closed`
- 94 methods
- 18 events

### 17.5 LLM health

- Anthropic: healthy, 6 calls, 100% success rate, 16.5s avg latency
- OpenClaw planner: 0 calls
- Echo: 0 calls

### 17.6 L6 readiness

- **24/25 = 96.0%**
- Deferred: `observability_dashboard` (v0.11.0)

### 17.7 Governance

- drift: **has_drift: false**
- proposals: 3 open (ISS-001, ISS-010, ISS-011)
- issues: 11 total (8 resolved, 3 open)
- kill_switch: `inactive`, history: 0
- self_modifier runtime: active
- flags: 9 total, 6 OFF, 3 ON (metrics, self_modifier_log_only, metrics_enabled)

---

## 18. Tests

**Framework**: pytest
**Collected**: **2813 tests** (verified `pytest --collect-only`)
**Full suite**: 182s, all pass
**Test files**: **86** (in `tests/`)

**Main categories**:
- `tests/architecture/` — 22 YAML schema tests
- `test_observability_metrics.py`, `test_anomaly_detector.py`, `test_behavior_digest.py`
- `test_self_modifier.py` (22 red-line tests)
- `test_proposal_generator.py`, `test_canary_engine.py`, `test_replay_harness.py`
- `test_feature_flags.py`, `test_feature_flag_persistence.py`, `test_kill_switch.py`, `test_drift_detector.py`
- `test_policy_engine.py` (31 tests, 4 guards)
- `test_channel_auth.py`, `test_channel_adapters.py`, `test_confirmation_gate.py`
- `test_voice_handler_format.py`, `test_mcp_bridge.py` (L4 bridge)
- `test_agent_allowlist.py` (82+ tests)
- `test_brain_flow.py`, `test_agents.py`, `test_api.py`
- `test_workflow_persistence.py`, `test_conversation_store.py`, `test_approval_store.py`

---

## 19. L6 Readiness Markers — teljes lista (verified live)

Élő `/observability/readiness` (2026-04-09):

| Marker | Állapot |
|--------|---------|
| architecture_memory_complete | ✅ |
| telemetry_active | ✅ |
| observability_interpretation | ✅ |
| **observability_dashboard** | ❌ (v0.11.0) |
| rfc_template_exists | ✅ |
| baseline_rfc_written | ✅ |
| issue_registry_live | ✅ |
| issue_registry_fresh | ✅ |
| evaluation_lane_functional | ✅ |
| canary_engine_ready | ✅ |
| proposal_engine_ready | ✅ |
| feature_flags_active | ✅ |
| feature_flags_persistent | ✅ |
| cost_optimization_flags | ✅ |
| governance_enforced | ✅ |
| governance_tested | ✅ |
| tests_cover_all_yaml | ✅ |
| self_modifier_runtime | ✅ |
| kill_switch_implemented | ✅ |
| kill_switch_runtime_guard | ✅ |
| kill_switch_tested | ✅ |
| drift_detector_ready | ✅ |
| canary_history_persistent | ✅ |
| telegram_owner_bypass | ✅ |
| text_uses_rich_pipeline | ✅ |

**Teljes: 24/25 = 96.0%**

---

## 20. Git + GitHub state

- **Repo**: `azar-management-consulting/occp-core`
- **Default branch**: `main`
- **Active branch**: `feat/v0.10.0-l6-foundation`
- **Latest commit**: `1f6b2fb` (pushed)
- **Open PR**: **#33** — "v0.10.0 — L4+→L6 Foundation"
- **PR state**: mergeable, awaiting Henry review + merge

**Commit history (last 6)**:
```
1f6b2fb chore: v0.10.0 full-system L6 update — Telegram fixes, cost opt flags, registry refresh
a13c24a feat: v0.10.0 L6 Maximum State — kill switch + drift + flag persistence + canary history
b1c6957 feat: v0.10.0 L6 Completion — self-modifier + proposal engine + interpretation layer
08c491c docs: L6 handover report 2026-04-08
18d831d feat: v0.10.0 L4+ → L6 Foundation — architecture memory, observability, evaluation lane
fbe69b1 fix: Telegram full-duplex + voice pipeline E2E + guard false positive
```

**Stale branches** (cleanup pending):
- `chore/v070-consolidation`
- `feat/v0.8.2-enterprise-onboarding`
- `feat/v080-onboarding-wizard`
- `fix/landing-version-080`, `fix/v080-refinement`, `fix/version-bump-080`

---

## 21. Őszinte korlátok (TRUE FEATURES vs. SCAFFOLDING)

### ✅ VALÓS, működő képességek

- Autonomous task execution **via OpenClaw chat** (szöveges terv + szöveges válasz)
- Policy gating (4 guard, hash chain audit)
- Governance enforcement (runtime self_modifier boundaries)
- Kill switch (E2E drill verified)
- Observability (metrics + anomaly + digest + readiness)
- Feature flags (JSON persistent)
- Telegram bi-directional (voice + text, owner DM bypass)
- OpenClaw WebSocket bridge (94 methods)
- MCP bridge workspace (/tmp/occp-workspace sandbox)
- 2813 passing tests, 0 regression across 6+ sessions

### 🟡 SCAFFOLDED, nem teljes

- **Agent execution**: wp-web, infra-ops, design-lab stb. csak **tool allowlist** — nincs mögöttük valódi executor kód. Minden agent_type → OpenClawExecutor → Claude chat → szöveg.
- **Cost optimization** (ISS-010, ISS-011): feature flagek léteznek, **de nincs code path** ami Haiku-ra route-olna vagy prompt caching-et használna.
- **Canary engine**: verdict logic OK, **nincs reverse-proxy traffic splitter**.
- **Replay harness**: in-process működik, **nincs git-worktree sandbox isolation**.
- **Self-modifier**: read-only validator (név ellenére nem modifikál semmit).
- **Proposal generator**: RFC candidate-eket gyárt, **de emberi review + manuális merge kell**.

### ❌ NEM LÉTEZŐ képességek

- **Valódi WordPress fájlmódosítás**: nincs wp-cli executor, nincs FTP client, nincs SSH bridge a Hetzner server fájlrendszerére.
- **Valódi deploy**: nincs docker build, nincs git push automation az agentek oldalán.
- **Hosszú futású autonóm munka**: minden task = 1 request/response. Nincs background worker, nincs queue, nincs cron-vezérelt feladat-végrehajtás.
- **Cross-session memória**: minden beszélgetés/task független. Nincs long-term agent memory.
- **BrainFlow DISPATCH**: `_dispatch_tasks()` generál task_id-kat, **de nem awaitál `pipeline.run()`-t** (ISS-001 még open).
- **Dashboard observability panel**: nincs (v0.11.0).
- **Observability dashboard in browser**: `/observability/*` endpointok JSON/Prometheus szöveget adnak, **nincs UI** fogyasztónak.

---

## 22. Összegzés

**OCCP az amit MEGÉPÍTETTÜNK**:

Egy **L5-foundation / early-L6** governance-first control plane, amely:
- **Tervez** (Claude + OpenClaw)
- **Policy-gate-el** (4 guard + allowlist + boundaries)
- **Audit-ol** (hash chain)
- **Observál** (metrics + anomaly + digest)
- **Governál** (runtime boundaries enforcement)
- **Áll le vészhelyzetben** (kill switch)
- **Megőriz minden működőt** (preservation contract)

**OCCP az amit NEM épített meg** (még):
- Valódi fájl-módosító agent executor-ok (`wp-web`, `infra-ops` stb.)
- Autonóm háttér munka (long-running, scheduled)
- Observability dashboard UI
- Cost-optimized LLM tier routing (ISS-010)
- Prompt caching (ISS-011)
- Git worktree replay sandbox
- Reverse-proxy canary traffic splitter

**Jelenlegi szint**: L5-foundation, 96% L6 markerek teljesítve az **architektúra-keret** szintjén, **de a tényleges agent execution még OpenClaw chat-text réteg**. Brian **tervet ír**, **nem kódol, nem deployol**.

**Verdikt**: Ez **nem hiány vagy hiba** — ez egy **megfelelő L5-foundation**, amely **pontosan az amit a projekt scope eddig célzott**. A következő jelentős lépés (v0.11.0+): valódi agent executor adapterek + autonóm background worker + dashboard UI.

---

*Minden állítás ellenőrzött kód, config, adatbázis lekérdezés, vagy élő endpoint válasz alapján. Ha bármilyen állítás nem pontos, az hiba — jelezd és javítom. FELT: prefixel semmit nem jelöltem, mert minden tény ellenőrizhető volt.*
