# OCCP — End-to-End Integration Test Prompt

> **Használat:** másold az első üzenetnek egy friss session-be. Az AI végigfuttatja a 14 teszt-kategóriát, összes szerepkör/agent/MCP/skill-lel, és ad egy hibátlan-működés bizonyító scorecard-ot.

---

## IDENTITÁS + 5 NEM ALKUKÉPES SZABÁLY

Te Claude Opus 4.7 vagy (Brian the Brain), **QA governance mode**-ban. Cél: bizonyítani, hogy az OCCP minden rétege hibátlan.

1. **READ-ONLY** — nem módosíthatsz kódot, configot, secret-et. Csak Read/Grep/Bash-query/curl/SSH-query.
2. **ZERO hallucináció** — minden PASS/FAIL állítás mellé evidence (`file:line`, parancskimenet, HTTP status).
3. **Reality-first** — session-kezdés kötelezően REALITY ANCHOR. Ha nem egyezik `OCCP_STATE.md`-vel → STOP + report.
4. **Evidence scorecard** — a futás végén gép-olvasható státusz-tábla kötelező (ld. §16).
5. **Sub-agent bash DENY** — delegált agent csak Read/Edit/Write kapott. Bash/curl/ssh a main context futtatja.

---

## 0. REALITY ANCHOR (kötelező első 7 parancs)

```bash
cd "/Users/BOSS/Desktop/AI/MUNKA ALL /OCCP ALL/OCCP/occp-core"
git fetch && git log --oneline -3 && git status -sb
cat OCCP_STATE.md | head -10
curl -sS https://api.occp.ai/api/v1/status | python3 -m json.tool
ssh -i ~/.ssh/id_ed25519 root@195.201.238.144 "docker ps --format '{{.Names}} {{.Status}}' | grep occp"
.venv/bin/pytest tests/ -q -k "not e2e and not loadtest and not smoke" --collect-only 2>&1 | tail -2
ls .planning/SESSION_1.md .planning/OCCP_FINAL_DELIVERY_PROMPT_v2.md
```

Elvárás: HEAD sync, prod v0.10.1, 5 container healthy, ~3157 test collect. Ha nem → STOP + report delta-t.

---

## TESZT-KATEGÓRIÁK (14 db, párhuzamosítható 3-6 agent-vágással)

### §1. Pipeline full cycle (VAP — Plan → Gate → Execute → Validate → Ship)

- **Cél:** egy triviális task (`echo hello`) végigmegy minden 5 szakaszon.
- **Parancs:** `.venv/bin/pytest tests/test_pipeline*.py -v --tb=line 2>&1 | tail -10`
- **PASS ha:** minden pipeline test zöld + `record_pipeline_run{result="pass"}` metrika nő egy valós POST után (curl `POST /api/v1/tasks` + /metrics delta).

### §2. Kill switch — minden entry point blokkol

- **Parancs:** `.venv/bin/pytest tests/test_eu_ai_act_compliance.py::test_halt_enforced_across_all_entry_points -v`
- **Evidence:** `__kill_switch_guarded__ = True` attribute a BrainFlow + MCPBridge + AutoDevOrchestrator osztályokon (grep).
- **PASS ha:** test PASS (nem xfail) + grep megtalálja mind a 3-at.

### §3. BudgetPolicy — pre-flight check + record_spend

- **Parancs:** `.venv/bin/pytest tests/test_executor_budget_integration.py tests/test_observability_metrics.py::TestMetricsCollector::test_record_spend* -v`
- **PASS ha:** 3 executor integration + spend-counter mind PASS.

### §4. MCP Bridge — 14 built-in + 6 external adapter

- **Parancs:** `.venv/bin/pytest tests/test_mcp_adapters.py tests/test_mcp_wordpress.py -v`
- **Extra:** `curl -sS https://api.occp.ai/api/v1/mcp/tools -H "Authorization: Bearer $OCCP_API_KEY"` → JSON lista (tool count ≥ 20).
- **PASS ha:** 20+ tool, env-gate működik (Supabase/GitHub/Slack nélkül → {"error": "...-not-configured"}).

### §5. Managed Agents PoC (Anthropic beta `managed-agents-2026-04-01`)

- **Parancs:** `.venv/bin/pytest tests/test_managed_agents_client.py -v`
- **RBAC teszt:** `curl -sS -o /dev/null -w "%{http_code}" https://api.occp.ai/api/v1/managed-agents/status/xxx` → **401** (anon).
- **PASS ha:** 9 unit test PASS + RBAC 401 guard.

### §6. SQL injection / SSRF hardening

- **Parancs:** `.venv/bin/pytest tests/test_mcp_adapters.py::test_supabase_query_blocks_writes tests/test_mcp_adapters.py::test_playwright_extract_text_blocks_ssrf -v`
- **PASS ha:** CTE bypass + multi-statement + comment-bypass mind blokkolt; 127.0.0.1, 169.254.169.254, `metadata.google.internal`, RFC1918 IPs mind `status: error`.

### §7. Observability — 6 SLO metrika live

- **Parancs:** `curl -sS https://api.occp.ai/metrics | grep -E "^# TYPE occp_(http_requests|http_request_duration|llm_cost_usd|kill_switch|pipeline_runs)"` — 6 sor.
- **Unit:** `.venv/bin/pytest tests/test_metrics_exposition.py -v`
- **PASS ha:** 8/8 + 6 metric TYPE szerepel prod `/metrics`-ben.

### §8. Skills v2 — 19 skill canonical formátum

- **Parancs:** `.venv/bin/pytest tests/test_skills_migration.py -v`
- **Manifest:** `python3 -c "import json; d=json.load(open('skills_v2/MANIFEST.json')); print(len(d['skills']))"` → **19**
- **PASS ha:** 24/24 parametrized + manifest == 19.

### §9. Eval CI — golden plans + snapshot + audit shape

- **Parancs:** `.venv/bin/pytest tests/eval/ -v`
- **PASS ha:** 17+ parametrized item mind PASS.

### §10. Landing — 7 locale SSG + middleware redirect

- **Lokál:** `cd landing-next && npm run build 2>&1 | tail -3` → exit 0
- **Public (brain via Caddy):** `ssh root@195.201.238.144 'for L in en hu de fr es it pt; do curl -sS -o /dev/null -w "  /$L → %{http_code}\n" http://127.0.0.1:3100/$L; done'`
- **PASS ha:** mind a 7 locale 200 + `/` → 302 `/en`.

### §11. Docs — Fumadocs i18n routing (16 EN + 6 locale)

- **Public:** `ssh root@195.201.238.144 'for P in /en /en/docs /en/docs/quickstart /hu /de /fr /es /it /pt; do curl -sSL -o /dev/null -w "  $P → %{http_code}\n" http://127.0.0.1:3200$P; done'`
- **PASS ha:** mind 200. Bonus: `/api-reference` → 200 (Scalar route handler).

### §12. Dashboard — v2 middleware flag + Brian drawer

- **Public:** `for R in / /v2 /v2/pipeline /v2/agents /v2/audit /v2/mcp /v2/settings /v2/admin; do curl -sS -o /dev/null -w "  $R → %{http_code}\n" https://dash.occp.ai${R}; done`
- **Vitest:** `cd dash && npm test 2>&1 | tail -4` → 11/11
- **PASS ha:** 7 route mind 200 + vitest 11/11.

### §13. CLI scaffolder — `npx create-occp-app`

- **Parancs:** `cd cli-create-app && npm test 2>&1 | tail -4` (3/3)
- **Smoke:** `cd /tmp && node /Users/BOSS/.../cli-create-app/src/index.js test-agent --template hello-agent --yes && ls test-agent/package.json && rm -rf test-agent`
- **PASS ha:** 3/3 + scaffold produkál package.json-t.

### §14. Telegram notify — @OccpBrainBot live

- **SSH:**
```bash
ssh root@195.201.238.144 'bash -s' <<'R'
T=$(docker inspect occp-api-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^OCCP_VOICE_TELEGRAM_BOT_TOKEN=' | cut -d= -f2-)
curl -s https://api.telegram.org/bot${T}/getMe | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',{}); print('OK' if d.get('ok') else 'FAIL', r.get('username'), r.get('id'))"
R
```
- **PASS ha:** `OK OccpBrainBot 8682226541`.

### §15. Full Python regression (baseline)

- **Parancs:** `.venv/bin/pytest tests/ -q -k "not e2e and not loadtest and not smoke" 2>&1 | tail -3`
- **PASS ha:** **3157 passed + 0 real fail** (1 flaky `test_memory` perf megengedett, ha standalone re-run zöld).

---

## §16. SCORECARD (kötelező végső output)

```
OCCP E2E TEST — <ISO8601 timestamp>
================================

§1  Pipeline full cycle .................... [PASS|FAIL] evidence=<...>
§2  Kill switch entry points ............... [PASS|FAIL] evidence=<...>
§3  Budget policy integration .............. [PASS|FAIL] evidence=<...>
§4  MCP bridge (14+6) ...................... [PASS|FAIL] evidence=<...>
§5  Managed Agents PoC + RBAC .............. [PASS|FAIL] evidence=<...>
§6  SQL injection + SSRF hardening ......... [PASS|FAIL] evidence=<...>
§7  /metrics 6 SLO ......................... [PASS|FAIL] evidence=<...>
§8  Skills v2 (19 skills) .................. [PASS|FAIL] evidence=<...>
§9  Eval CI (17+ cases) .................... [PASS|FAIL] evidence=<...>
§10 Landing 7 locale SSG ................... [PASS|FAIL] evidence=<...>
§11 Docs Fumadocs i18n ..................... [PASS|FAIL] evidence=<...>
§12 Dashboard v2 + Brian drawer ............ [PASS|FAIL] evidence=<...>
§13 CLI scaffolder ......................... [PASS|FAIL] evidence=<...>
§14 Telegram @OccpBrainBot ................. [PASS|FAIL] evidence=<...>
§15 Full pytest regression ................. [PASS|FAIL] evidence=<...>

TOTAL: <n>/15 PASS
VERDICT: [GREEN (15/15) | YELLOW (12-14) | RED (<12)]
BLOCKERS: <list of FAIL items with FELT: or next-action>
```

---

## KIEGÉSZÍTŐ — párhuzamos agent-terhelés

Ha bizonyítani akarod, hogy a multi-agent orchestration is hibátlan, spawn 3 sub-agent párhuzamosan (ne sorosan):

- `general-purpose` A: §1-5 futtatás + scorecard részleges
- `general-purpose` B: §6-10 futtatás + scorecard részleges
- `general-purpose` C: §11-15 futtatás + scorecard részleges

Főkontextus aggregál → végső 15-soros scorecard. PASS ha 3 agent független jelentése nem mond ellent egymásnak (meta-supervisor cross-check).

---

## ÖNTANULÁS / SELF-IMPROVEMENT bizonyítás

- **AutoDev orchestrator:** `.venv/bin/pytest tests/test_autodev*.py -v` → verification gate szakaszok PASS.
- **Kill-switch + eval-driven proposal:** ha AutoDev javaslatot tesz, az AutoDev.propose() `require_kill_switch_inactive()`-vel kezdődik (§2-ben lefedve).
- **Skill evolúció:** `skills_v2/MANIFEST.json` version field növelhető — igazolja, hogy a rendszer támogat skill frissítést.

---

## VÉGSŐ ELVÁRÁS

**GREEN (15/15)** esetén:
- Telegram notify `@OccpBrainBot` (msg ID-t a scorecard-hoz).
- Commit szándék: `docs(qa): e2e test run <date> — 15/15 GREEN` (csak ha a scorecard fájlba mentődik).

**RED / YELLOW** esetén:
- STOP.
- FELT: a valós okra (nem tipp).
- Javaslat: melyik iter-X commit vonja vissza / melyik service restart / melyik config fix.

---

**Verzió:** v1.0 · source commit `a56157b` · iter-10 után · teljes 15-kategória fedés
