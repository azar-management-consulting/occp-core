# OCCP 100% CONTROL PLANE ACCEPTANCE CHECKLIST

**Dátum:** 2026-04-20
**Cél:** OCCP Brain → OpenClaw agent control plane **100%-os, end-to-end működő** állapotba hozása, mielőtt az OM (Országos Média) build indul.
**Alap:** `OCCP_SYSTEM_MANUAL.md` v0.10.0 §11 + §13 + agent-diagnosis 2026-04-20
**Scope:** hetzner-brain (195.201.238.144) + hetzner-openclaw (95.216.212.174) + Mesh (iMac/MBP/MBA Tailscale)
**Out of scope:** ISPConfig (külön projekt)

---

## 0. ACCEPTANCE GATE — NINCS HALADÁS AMÍG NEM ZÖLD

Production READY-nek csak akkor nevezzük, ha **mind a 12 pont PASS** + 3 egymás utáni sikeres e2e round-trip (Telegram → Brain → OpenClaw → valós WP módosítás → Telegram visszajelzés).

---

## 1. API v0.10.0 DEPLOY (jelenleg v0.9.0)

**Bizonyíték célértéke:** `curl -s https://api.occp.ai/api/v1/status | jq .version` → `"0.10.0"`

Alátámasztó lépések:
- `pyproject.toml` bump: `version = "0.9.0"` → `"0.10.0"` (+ `[project]` Python min verzió 3.12 marad)
- `Dockerfile.api` base image érintetlen (3.12-slim)
- Local: `.venv/bin/pytest -q tests/` 3205/3205 PASS
- Deploy: `scp pyproject.toml + .env.sample root@brain:/opt/occp/ && docker compose build api && docker compose up -d api`
- Verify: `docker compose logs api --tail 50` → `Uvicorn running on http://0.0.0.0:8000`

**Teszt-kritérium:** `/api/v1/status` `version=0.10.0 && environment=production && status=running`.

---

## 2. DASHBOARD HEALTHY (jelenleg unhealthy)

**Bizonyíték célértéke:** `docker ps --filter name=occp-dash --format '{{.Status}}'` → `Up X minutes (healthy)`

- Rebuild: `ssh brain 'cd /opt/occp && docker compose build dash --no-cache && docker compose up -d dash'`
- Healthcheck fix (manual §11.1 #3): wget→curl váltás vagy Node fetch (`/api/health` próbál)
- Verify: `curl -sI https://dash.occp.ai/` → `HTTP/2 200` + `X-Powered-By: Next.js` (vagy equivalent)
- Playwright snapshot: `/login` oldal render, "OCCP – Mission Control" cím

---

## 3. OPENCLAW EXECUTOR — VALÓS VÉGREHAJTÁS (ARCH LIMIT FELOLDVA)

**Bizonyíték célértéke:** egy tesztbench e2e futtatás:
1. Brain `POST /api/v1/brain/message` — "Írj `/tmp/occp-e2e-test.txt`-be: `OCCP_E2E_PASS_<timestamp>`"
2. Ellenőrzés: `ssh openclaw 'cat /tmp/occp-e2e-test.txt'` → tartalmazza `OCCP_E2E_PASS_`
3. Audit log entry `action=filesystem.write, success=true`

Implementációs lépések (diagnózis §C alapján):
- **Commit A:** `adapters/openclaw_executor.py::_extract_output()` (lines 959-995) — detektáld a JSON code block-ot az agent textben (`^```(json)?\n\{.*"exec_type":.*\}\n```$` regex), parse `execution_directives[]` listába.
- **Commit B:** `adapters/openclaw_executor.py::execute()` return dict (795-803) — új field `execution_directives` + visszaküldés a Brain dispatch logikához.
- **Commit C:** `adapters/openclaw_planner.py` — Brain prompt inject-el `{"available_tools": [...], "response_schema": {...}}` az agent-nek.
- **Commit D (opcionális):** `mcp/bridge.py` — új RPC method `agent.invoke_tool` — gateway → Brain callback.

**NE nyúlj:** `policy_engine/guards.py`, `security/agent_allowlist.py`, `orchestrator/pipeline.py` protocol.

**Teszt-kritérium:** 3 különböző tool (filesystem.write, node.exec, http.get) sikeresen végrehajtva 3 különböző task-ban, audit log-ban rögzítve.

---

## 4. WP VALÓDI MÓDOSÍTÁS (Application Password hiányzik)

**Bizonyíték célértéke:** `curl -X POST /api/v1/brain/message -d '{"message":"Módosítsd a magyarorszag.ai `Hello World` post címét `OCCP E2E Test <ts>` értékre"}'` → WP REST API sikeres update + audit log `wordpress.update_post action=update,success=true,post_id=X`.

- magyarorszag.ai `wp-admin` → Users → admin → Application Passwords → új jelszó generálás
- Brain `.env`-be: `OCCP_WORDPRESS_MAGYARORSZAG_URL=https://magyarorszag.ai`, `OCCP_WORDPRESS_MAGYARORSZAG_USER=<user>`, `OCCP_WORDPRESS_MAGYARORSZAG_APP_PW=<generált>`
- `adapters/wordpress_client.py` (v0.9.0-ben létezik `get_posts`) — auth header Basic `user:app_pw` encode
- MCP tool `wordpress.update_post` — jelenleg olvashatóan létezik (manual §6), írás teszt
- Rollback-safe: csak test post-on (draft status, nem publikus)

**Teszt-kritérium:** 1 dummy post cím változtatása + visszaállítása, 2 egymás utáni sikeres round-trip.

---

## 5. BRAIN ↔ OPENCLAW WEBSOCKET STABIL

**Bizonyíték célértéke:**
- `circuit breaker state = CLOSED` (manual §11: `circuit=closed`)
- `wss://claw.occp.ai` handshake OK (Basic Auth + OpenClaw gateway token)
- 50 egymás utáni `POST /brain/message` hívás → 50/50 sikeres gateway forward
- Reconnect teszt: openclaw container restart → brain auto-reconnect max 30s

Implementációs lépések:
- `adapters/openclaw_executor.py::OpenClawConnection._receive_loop` exponential backoff verify (lines 441-455)
- Load teszt: `k6 run scripts/loadtest-brain.js` 50 req, 0 fail
- Metrika: `/api/v1/observability/readiness` → `brain_openclaw_ws_uptime_pct >= 99.5`

---

## 6. TELEGRAM BOT ROUND-TRIP

**Bizonyíték célértéke:** 3 egymás utáni e2e:
1. Henry Telegramon: "Vizsgáld meg a magyarorszag.ai title tag-ját"
2. Bot reply < 30s, valós adat (nem chat hallucináció)
3. Audit entry pipeline_id + action chain log-olva

- `adapters/telegram_voice_bot.py` polling active (manual §9)
- Owner bypass: `OCCP_VOICE_TELEGRAM_OWNER_CHAT_ID=8400869598` verify
- BrainFlow triggerek: explicit kulcsszavak ("tervezz", "feladat:", stb.) → 7-fázis flow
- Telegram 4096-char split: ha > 4096, több chunk-ban (manual §9.2)

**Teszt-kritérium:** 5 különböző prompt (text + voice), mind < 30s full-round, audit chain integrity.

---

## 7. KILL SWITCH VALÓS BLOKK

**Bizonyíték célértéke:** aktív állapotban **SEMMI** task nem fut.

- `POST /governance/kill_switch/activate {"trigger":"test","reason":"acceptance"}`
- Majd: `POST /brain/message {"message":"tetszőleges"}` → response: `{"error":"kill_switch_active"}`
- `POST /governance/kill_switch/deactivate` után: task elfogadódik
- Verify: `Pipeline.run()` első lépésben `require_kill_switch_inactive()` — látható a kódban, teszt logból is

**Teszt-kritérium:** 5 task aktív kill switch alatt → 5/5 REJECTED; deaktiválás után 5/5 PROCESSED.

---

## 8. 5 POLICY GUARD E2E

Mind az 5 guard PASS + FAIL esetén:
- PIIGuard: beadott email/phone/SSN/credit card → REJECTED + audit
- PromptInjectionGuard: 20+ injection pattern → BLOCK, `brain_dispatched` metadata skip működik
- ResourceLimitGuard: timeout > limit → task cancelled
- OutputSanitizationGuard: output PII → sanitized, `skip plan fields` helyes
- HumanOversightGuard: high-risk task → HITL queue

**Teszt-kritérium:** `tests/test_policy_guards_e2e.py` — mind az 5-re 2 test case (PASS + FAIL), 10/10 zöld.

---

## 9. 14 MCP BRIDGE TOOL SMOKE

Manual §6 14 tool, mindegyikre 1-1 smoke teszt:

| Tool | Smoke teszt |
|---|---|
| brain.status | assert version/env |
| brain.health | 200 OK |
| filesystem.read | fájl olvasás /tmp/occp-workspace/ |
| filesystem.write | fájl írás ua. workspace |
| filesystem.list | dir lista |
| http.get | 200 egy publikus URL-re |
| http.post | echo szerverre |
| wordpress.get_site_info | magyarorszag.ai name + description |
| wordpress.get_posts | 1+ post |
| wordpress.get_pages | 14 page (manual § 10.1) |
| wordpress.update_post | #4 fedi |
| node.list | 4 node visszaadva |
| node.status | mindegyik reachable |
| node.exec | `hostname` parancs futtat + return |

**Teszt-kritérium:** `pytest tests/test_mcp_bridge_smoke.py -v` 14/14 PASS.

---

## 10. AUDIT CHAIN HASH INTEGRITY

- `GET /api/v1/audit?limit=100` → lista
- Minden entry `prev_hash = sha256(prev_entry_serialized)` konzisztens
- Tamper teszt: egy sor manuális módosítása → chain broken észlelés
- `migrations/versions/` érintetlen (immutable path)

**Teszt-kritérium:** `pytest tests/test_audit_chain.py::test_hash_chain_integrity` PASS, 100+ entry-n is.

---

## 11. AUTODEV LOW-RISK SIKERES CIKLUS

Minimum 1 auto-approve ciklus:
- `POST /autodev/propose` — trivialis diff (pl. docstring javítás)
- Feature flag `l6.autodev.enabled=true`, kill switch inactive, `runs_started < 20/day`
- Git worktree `/tmp/occp-autodev/<run_id>/`
- `git apply` + lint + targeted test + regression
- Risk score 0-10 → LOW (<3) auto-approve
- Branch kept → **NEM merge** main-be (manual §10.3)

**Teszt-kritérium:** `tests/test_autodev_low_risk_cycle.py` PASS.

---

## 12. L6 READINESS 100% (jelenleg 96% = 24/25)

- `GET /api/v1/observability/readiness` → `score = 25 / 25`
- Hiányzó marker: `observability_dashboard` (manual §13 hint) — verify
- Minden egyéb L6 criteria zöld

**Teszt-kritérium:** readiness endpoint 25/25 + 0 anomaly.

---

## E2E ROUND-TRIP ACCEPTANCE (3/3)

**Task sablon:**
1. Telegram @OccpBrainBot-nak: "Listázd a magyarorszag.ai top 3 legfrissebb post címét"
2. Bot: text válasz < 30s, 3 valós cím (WP REST-ből, nem hallucináció)
3. Audit: `pipeline_id`, `action=wordpress.get_posts`, `policy_result=PASS`, `execution_directives=[...]`

**Kritérium:** 3 egymás utáni (min 10 perc szünettel) → 3/3 PASS, 0 hallucináció, 0 policy violation.

---

## CLEANUP & DOCUMENTATION

- `OCCP_SYSTEM_MANUAL.md` credential redact → `See: .env` stílus (OCCP_PROJECT_SUMMARY minta)
- `.gitignore` + `OCCP_SYSTEM_MANUAL.md`, `*.planning/*OPERATIONAL*`, `news/articles/settings-architecture.html`
- Git repo sérülés fix: `rm .git/refs/heads/main\ 2 .git/refs/remotes/origin/main\ 2` (safe, iCloud artifact)
- 12+ iCloud " 2" duplikátum törlés `architecture/*.yaml`, `dash/src/app/**/page 2.tsx`
- 18 deleted SKILL.md commit (ha szándékos volt) VAGY restore
- Secret rotáció: GitHub PAT, Telegram bot token, API admin pw
- `pyproject.toml` bump verzió
- Tailscale IP refresh a manual §2.2-ben (100.88.122.102 → valós, dynamic)

---

## TIMELINE BECSLÉS

| Fázis | Idő | Függőség |
|---|---|---|
| Wave A (local, no SSH) | 2-3h | — |
| Wave B (SSH unban) | 30 perc | Hetzner console |
| Wave C (deploy + test) | 4-6h | Wave A+B |
| Wave D (e2e acceptance) | 2h | Wave C |
| **Összes** | **8-12h** | kontrollált |

---

## REFERENCIA

- `OCCP_SYSTEM_MANUAL.md` — v0.10.0 kézikönyv
- `.planning/BRAIN_AGENT_ARCHITECTURE.md` — ideal state
- `.planning/OPENCLAW-GAP-ANALYSIS.md` — korábbi gap-ek
- `.planning/L6_COMPLETION_2026-04-08.md` — 96% readiness forrás
- Diagnózis: 2026-04-20 Claude Code Explore agent (architectural limit §C)

---
*Dokumentum v1.0 · 2026-04-20 · agent-drafted · Henry (Fülöp Henrik) review előtt*
