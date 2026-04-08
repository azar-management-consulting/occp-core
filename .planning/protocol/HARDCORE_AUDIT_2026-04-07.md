# OCCP HARDCORE ENTERPRISE AUDIT — 2026-04-07

**Auditor:** Senior AI Systems Architect
**Method:** Real-runtime evidence-based, non-destructive
**Scope:** Lokális MBA + Hetzner Brain + Hetzner OpenClaw + 28 MCP + összes csatlakozó node

---

## EXECUTIVE SUMMARY

Az OCCP egy **mérnökileg erős, governance-first AI execution kernel**, ami a piaci átlagot meghaladó biztonsági réteggel és VAP pipeline-nal rendelkezik. **Production-ready a core funkcióra**, de **NEM enterprise-grade AI operating system** — három kritikus okból:

1. **Két szétválasztott execution surface:** OCCP-runtime és Henry MCP-univerzum NEM kommunikál.
2. **Új persistence layer üres:** brain_conversations / pending_approvals / workflow_executions = 0 sor — a v0.9.0 új modulok deploy-olva, de a forgalom NEM rajtuk megy át.
3. **Implicit operátor-tudás dominál:** kritikus információk Henry fejében + memory KG-ban + egy AES vault-ban — nincs egységes node/auth/path registry (mostantól van: `.planning/protocol/`).

A rendszer ma **L3 — Orchestrated Platform**. **L4** és **L5** konkrét, számszerűsíthető lépésekkel elérhető (lásd Roadmap).

---

## 1. KOMPLETT (✅ verified)

| Komponens | Bizonyíték |
|-----------|------------|
| OCCP API runtime v0.9.0 | curl /api/v1/health → healthy, 7 nap uptime |
| Dashboard v0.9.0 | dash.occp.ai 200 OK |
| Voice pipeline init | "Voice pipeline: started (lang=hu)" log |
| OpenClaw bridge | "OpenClaw bridge: active (url=wss://claw.occp.ai)" + 106 events |
| BrainFlowEngine init | "BrainFlowEngine initialized" log |
| 22 router registered | bridge, voice, brain, cloudcode, dashboard, projects, quality, ... |
| 8 OpenClaw specialista agent | openclaw.json verified |
| Apache vhostok | 85 namevhost, occp.ai/api/dash/news/mail SSL OK |
| DNS | occp.ai → 195.201.238.144, claw.occp.ai → 95.216.212.174 |
| 9 DB tábla + 7 Alembic migráció | sqlite_master verified |
| Audit chain | 261 audit_entries (Merkle hash) |
| Git paritás (md5) | local app.py == server app.py: c505c1aca933... |
| 7 fő security réteg | ChannelAuth + Sanitizer + AgentGuard + PolicyEngine + Gate + Audit + Persistence |

---

## 2. PARTIAL (⚠️)

| Komponens | Probléma |
|-----------|----------|
| ConversationStore | táblá létezik, **0 sor** — soha nem használt valós forgalom |
| ApprovalStore | táblá létezik, **0 sor** — soha nem váltott ki valódi confirmation |
| WorkflowStore | táblá létezik, **0 sor** — DAG workflow soha nem futott éles forgalmon |
| AgentToolGuard | log-only mode aktív, **0 violations** rögzítve a sessionben |
| ChannelAuth Telegram | strict mode aktív, de owner_chat_id=0 → lényegében MINDEN üzenet rejected lenne |
| Tests local | 2612+ teszt PASS lokálisan, **DE** szerveren NEM futnak (Docker rebuild) |
| Brain dispatch HTTP | `queued_for_pipeline` fallback aktív, valós HTTP path nincs |

---

## 3. MISSING (❌)

| Hiányzó | Hatás |
|---------|-------|
| OCCP runtime ↔ MCP integráció | Brian nem tudja használni a 28 MCP-t — csak Henry kliens-oldali |
| OpenTelemetry / Jaeger | nincs distributed tracing |
| Prometheus / Grafana | nincs metrics + dashboard |
| PostgreSQL | csak SQLite (single-writer limit, nem skálázódik 5+ concurrent felett) |
| A2A agent card | `/.well-known/agent-card.json` nincs |
| Circuit breaker per-agent | nincs failover logic |
| Memory pruning | conversation history végtelen |
| Multi-tenant izoláció | egyetlen Henry-account |
| OCCP_VOICE_TELEGRAM_OWNER_CHAT_ID | nincs beállítva — runtime warning aktív |
| Tailscale mesh | nincs telepítve egyik nodeon sem |
| Unified node registry | NINCS volt — most létrejött (`NODE_REGISTRY.yaml`) |
| Backup secret rotation | nincs automated rotation |
| OCCP runtime tudja az iMac/MBP node-okat | egyik sem érhető el |
| iMac 4TB shared folder integration | UNKNOWN — nincs mount, sync, vagy közös FS layer |

---

## 4. WORKING BUT UNDOCUMENTED (📦)

| Mit | Hol | Bizonyíték |
|-----|-----|------------|
| OpenClaw stale-socket auto-restart | gateway hardcoded ~35min | docker logs |
| Mailcow stack | 20 container, 5 hét uptime | docker ps |
| 85 Apache vhost | sok más site is fut a szerveren (mychatsignal.com, news.occp.ai, stb.) | apache2ctl -S |
| OCCP-SECURITY-VAULT.enc | AES-256 vault Henry MBA-n | memory KG |
| WireGuard MatraCOMP | mail server VPN (10.10.40.2/32) | local conf |
| Memory KG | 60+ entitás Henry projektjeiről | mcp__memory__read_graph |
| Brian `[SYSTEM]` prefix workaround | openclaw_executor._build_message() | code grep |
| Streaming `collected[-1]` fix | openclaw_executor.py:454 | code grep |
| Backup script `daily 03:00 14-day retention` | OpenClaw szerveren | memory KG |

---

## 5. CONFIGURED BUT NOT ACTUALLY USED (🪤)

- **n8n MCP** — telepítve, OCCP-vel nincs integráció
- **scheduled-tasks MCP** — konfigurálva, nincs aktív cron OCCP-hez
- **semgrep / snyk / GitGuardianDeveloper MCPs** — nincs CI integráció a /opt/occp/-be
- **postgres MCP** — telepítve, OCCP még SQLite
- **Cloudflare MCP** — telepítve, OCCP DNS most Hostingerben
- **Brain dispatch HTTP route** — kód él, de a flow a WebSocket-en megy
- **8 OCCP API agent_config (mcp-installer, llm-setup, skills-manager, ...)** — registered de soha nem fut le real task

---

## 6. USED BUT NOT SAFELY GOVERNED (⚠️)

- **OCCP_ADMIN_PASSWORD = "changeme"** — production-ban (env: development → bypassed `_reject_default_password_in_prod` validator)
- **mychatsignal.com vhost** — más projekt, ugyanazon a szerveren OCCP mellett
- **Mailcow** — saját admin UI, NEM az OCCP audit chain alatt
- **felnottkepzes.hu** — 12,221 xmlrpc.php hits/day (memory: bot DDoS), nincs OCCP-mediated mitigation
- **MatraCOMP FreeBSD 13.1 EOL + 65 CVE** — kritikus, OCCP NEM tud rajta segíteni jelenleg

---

## 7. HENRY KÉZI TUDÁSÁRA TÁMASZKODÓ ELEMEK (🧠)

| Mit | Hol kellene lennie |
|-----|--------------------|
| Melyik szerver melyik IP-n van | NODE_REGISTRY.yaml ✅ ÚJ |
| Melyik MCP mit csinál | MCP_ROLE_MAP.yaml ✅ ÚJ |
| 8 specialista vs 11 OCCP API agent eltérése | AGENT_ROLE_MAP.yaml ✅ ÚJ |
| Hol vannak credentials | MASTER_PROTOCOL_v1.md ✅ ÚJ |
| Backup aktuális verzió | nincs egységes register |
| Brian `[SYSTEM]` prefix workaround indoka | nincs ADR/decision log |
| OpenClaw stale-socket viselkedés | nincs runbook |
| Magyar projektek (azar.hu, magyarorszag.ai, ...) → melyik agent csinálja | nincs ownership map |

---

## 8. MI TÖRNE 30 NAP HENRY-NÉLKÜL?

**Magas kockázat (3-7 nap alatt):**
- OCCP_ADMIN_PASSWORD nincs változtatva → gyenge auth
- ApprovalGate timeout-ol mert owner_chat_id=0 → semmi nem fut le auto
- felnottkepzes.hu xmlrpc DDoS bot fenyegetés
- Anthropic / OpenAI API token rotáció kézi
- Mailcow disk full risk (20+ container, nincs proaktív monitoring)

**Közepes kockázat (7-30 nap):**
- LE SSL renewal: certbot auto, de figyelmeztetés Henry-hez megy
- MatraCOMP RAID disk PD05 predictive failure → ha tényleg eltörik
- OpenClaw daily 03:00 backup, de visszaállítást Henry tud csinálni
- DB SQLite növekedés → 36KB most, no compaction policy

**Mit bírna kifutni:**
- API + dashboard runtime (auto-restart Docker)
- DNS (Hostinger-en autonóm)
- OpenClaw gateway (auto-restart)

---

## 9. SCALABILITY

| Scale | Limit |
|-------|-------|
| 1 user, 1 chat_id (Henry) | ✅ kibírja |
| 5 concurrent users | ⚠️ SQLite single-writer szűk |
| 10+ concurrent users | ❌ PG migráció kell |
| 100+ tasks/min | ❌ no rate limiting per-agent |
| Multi-tenant | ❌ nincs |
| Multi-region | ❌ nincs |

---

## 10. MATURITY SCORES

| Dimenzió | Pontszám | Indoklás |
|----------|----------|----------|
| **Architektúra** | **8/10** | VAP, governance, sandbox, audit chain — iparági szint felett |
| **Orchestration** | **6/10** | BrainFlow kód kész, de a perzisztencia táblák üresek |
| **Node governance** | **3/10** | Most lett egységes registry, korábban implicit |
| **Security** | **7/10** | 5 réteg + vault, de owner_id=0 + changeme jelszó |
| **Observability** | **3/10** | structlog + audit_chain JÓ; nincs OTel/metrics/traces |
| **Documentation** | **6/10** | bőséges .planning/, de kontradikciók |
| **AI OS readiness** | **4/10** | OCCP runtime ↔ MCP NEM integrált |

**Összesített: 5.3/10 — L3 Orchestrated Platform**

---

## 11. SYSTEM LEVEL CLASSIFICATION

```
L1 Fragmented tools           ← múlt
L2 Connected system           ← múlt
L3 Orchestrated platform      ← ITT VAGYUNK ✅
L4 Autonomous operating system ← elérhető 2-3 hét
L5 Enterprise-grade AI OS     ← elérhető 6-8 hét
```

**Miért L3:**
- ✅ Egy Brain, egy pipeline, egy audit lánc
- ✅ Több specialista agent egységesített route-on át
- ✅ Konzisztens biztonsági lánc (auth → sanitize → gate → audit)
- ✅ Restart-safe persistence (technikailag)
- ❌ De a runtime ↔ MCP gap blokkolja az L4-et
- ❌ A perzisztencia új layer üres → nem "autonomous"
- ❌ Nincs distributed observability

**Mi kell az L4-hez:**
1. brain_flow valódi forgalmon menjen (nem csak teszt)
2. owner_chat_id beállítása + Telegram funkcionálisan elérhető
3. ApprovalGate valódi human-in-the-loop ciklus
4. WorkflowExecutions DAG valós feladatra használva
5. AgentToolGuard enforcement mode (nem log-only)

**Mi kell az L5-höz:**
6. PG cutover
7. OTel + Prometheus
8. A2A agent card + OCCP runtime ↔ MCP bridge
9. Multi-tenant
10. Budget control
11. Circuit breaker per agent
12. Disaster recovery test

---

## 12. PRIORITIZED NEXT ACTIONS

### P0 — 1-2 nap, blokkoló
1. **OCCP_VOICE_TELEGRAM_OWNER_CHAT_ID beállítása** (Henry chat_id) → Telegram működjön valódian
2. **OCCP_ADMIN_PASSWORD csere** "changeme" helyett → security baseline
3. **OCCP_ENV=production** + validator aktiválás → enforcement
4. **Brain flow valódi forgalom** — küldés Telegramról, monitorozás hogy brain_conversations/pending_approvals töltődik-e

### P1 — 3-7 nap, L4 felé
5. **Unified agent registry** — OCCP API 11 + OpenClaw 8 → 1 forrás
6. **AgentToolGuard enforce mode** (log-only → block) selective agentekre
7. **Backup audit + automated rotation** secret-ek
8. **iMac/MBP discovery** — Tailscale telepítés vagy SSH path dokumentálás
9. **Memory KG sync** — node registry-vel

### P2 — 1-2 hét, L5 felé
10. **PostgreSQL cutover** (B1 roadmap, már tervezve)
11. **OpenTelemetry instrumentation** (P1 ULTIMATE_DEV_PROMPT)
12. **A2A agent card** (P2)
13. **Circuit breaker** (P3)
14. **Memory pruning** (P4)

### P3 — 3-4 hét
15. **OCCP runtime ↔ MCP bridge** — vagy MCP client a brain-ben, vagy Claude Code callback channel
16. **Multi-tenant scaffold**
17. **Budget control** per provider

---

## 13. EXPLICIT UNKNOWNS

- iMac OS, IP, Tailscale, SSH state
- MBP OS, IP, Tailscale, SSH state
- iMac 4TB shared folder mount path / sync state
- mychatsignal.com — másik projekt, OCCP-vel kapcsolatban van-e?
- 85 Apache vhost — mind aktív vagy van árva?
- Hetzner OpenClaw account ownership (másik project? másik account?)
- BestWeb hosting jövője (új IP-re kell menni? legacy?)
- MatraCOMP RAID PD05 disk csere ETA

---

## 14. APPENDIX — EVIDENCE BASIS

| Forrás | Mód |
|--------|-----|
| ssh root@195.201.238.144 | docker ps, md5sum, sqlite3, apache2ctl, df, free, uptime, systemctl |
| ssh -i ~/.ssh/openclaw_ed25519 root@95.216.212.174 | docker ps, openclaw.json |
| Local git | git rev-parse, git status, git log |
| Local md5 | md5 -r api/app.py |
| Local file | uname, sw_vers, hostname, which tailscale |
| mcp__hetzner__list_servers | 1 szerver (AZAR) — OpenClaw NEM ebben az accountban |
| mcp__hostinger-mcp__DNS_getDNSRecordsV1 | occp.ai zone — verified |
| mcp__memory__read_graph | 60+ entity, projekt + credential metadata |
| credentials.env grep | KULCSNEVEK ONLY: 7 token (Cloudflare, Exa, Firecrawl, GitHub, Hetzner, Hostinger, Ref) |
| /api/v1/health, /voice/status | curl outputs |
| /api/v1/agents (with admin token) | 11 internal agents listed |
| docker logs | init sequence + WebSocket events |

---

**Audit complete.** All findings evidence-based. No secrets exposed. No destructive action taken. Master Protocol v1 + Node Registry + MCP Role Map + Agent Role Map létrehozva mint új source of truth.
