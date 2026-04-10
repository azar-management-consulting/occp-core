# OCCP Master Protocol v1

**Version:** 1.0.0
**Generated:** 2026-04-07
**Owner:** Henry (Fülöp Henrik)
**Status:** FORMALIZED — replaces all prior implicit operator knowledge

---

## 1. CORE DEFINITION

OCCP (OpenCloud Control Plane) is a **governance-first AI execution kernel** with these immutable properties:

- Single Brain (Brian the Brain) is the only authorized orchestrator.
- All execution flows through the Verified Autonomy Pipeline (VAP):
  `Plan → Gate → Execute → Validate → Ship`
- All inputs are authenticated, sanitized, guarded, gated, audited, persisted.
- All sensitive operations are approval-gated.
- All events are correlation-ID tracked and auditable.

OCCP is **NOT** a chatbot. It is a controlled AI operating system foundation.

---

## 2. NODE MODEL

| Plane | Node | Role | Status |
|-------|------|------|--------|
| Control (mobile) | mba-henry | Henry's primary control + Claude Code MCP host | ACTIVE |
| Control (desktop) | imac-henry | Storage + secondary control | UNKNOWN |
| Control (laptop) | mbp-henry | Secondary dev | UNKNOWN |
| OCCP Brain | hetzner-occp-brain (195.201.238.144) | API + dashboard + Mailcow + Apache reverse proxy | ACTIVE |
| OCCP Execution | hetzner-openclaw (95.216.212.174) | OpenClaw 8 specialist agents + Telegram bot @occp_bot | ACTIVE |
| Legacy Hosting | bestweb-shared (185.217.74.211) | azar.hu + felnottkepzes.hu | ACTIVE (independent) |
| Legacy Mail | matracomp-mail (192.168.6.193) | felnottkepzes.hu mail (FreeBSD EOL) | ACTIVE-WITH-RISK |
| Shared Hosting | hostinger-shared | magyarorszag.ai + tanfolyam.ai | ACTIVE (independent) |

Full registry: `.planning/protocol/NODE_REGISTRY.yaml`

---

## 3. PATH REGISTRY (canonical sources of truth)

| Type | Canonical Path |
|------|---------------|
| OCCP source (local) | `/Users/air/Desktop/PROJECTEK/OCCP/occp-core/` |
| OCCP source (server) | `root@195.201.238.144:/opt/occp/` |
| OCCP DB | `/opt/occp/data/occp.db` (SQLite, 9 tables) |
| OpenClaw config | `root@95.216.212.174:/home/openclawadmin/.openclaw/openclaw.json` |
| OpenClaw workspace | `root@95.216.212.174:/home/openclawadmin/.openclaw/workspace/` |
| OpenClaw deploy | `root@95.216.212.174:/home/openclawadmin/openclaw-deploy/` |
| Credentials index | `/Users/air/Desktop/PROJECTEK/Rendszer/secrets/credentials.env` |
| OCCP Vault (encrypted) | `/Users/air/Desktop/PROJECTEK/OCCP/OPENCLAW/OCCP-SECURITY-VAULT.enc` |
| Memory KG | mcp__memory (60+ entities) |
| WireGuard config | `/Users/air/Desktop/MatraCOMP-Wireguard-VPS-WG-Henrik.conf` |

---

## 4. EXECUTION ROUTING POLICY

```
INPUT (Telegram | API | CloudCode)
  │
  ▼
[1] ChannelAuth        ←  reject if no identity
  │
  ▼
[2] InputSanitizer     ←  block if injection (8 patterns + Luhn)
  │
  ▼
[3] BrainFlow / Pipeline.run()
  │
  ▼
[4] PolicyEngine.evaluate (4 guards)
  │     pii_guard, prompt_injection_guard,
  │     resource_limit_guard, output_sanitization_guard
  │
  ▼
[5] AgentToolGuard (log-only mode for now)
  │
  ▼
[6] AdapterRegistry → Executor selection
  │     openclaw → wss://claw.occp.ai
  │     general/code-reviewer/main → openclaw
  │     demo → mock
  │     others → sandbox
  │
  ▼
[7] EXECUTE (specialist agent runs the task)
  │
  ▼
[8] VALIDATOR (basic_validator)
  │
  ▼
[9] SHIPPER (log_shipper → audit_store)
  │
  ▼
[10] Persistence (tasks, audit_entries, [conversations, approvals — currently empty])
  │
  ▼
OUTPUT
```

---

## 5. AUTONOMY BOUNDARY POLICY

| Risk Level | Action |
|-----------|--------|
| LOW | Auto-approve, execute immediately |
| MEDIUM | Brian sends plan to Henry → wait approval (5 min timeout) |
| HIGH | Brian sends plan + risk note → wait approval |
| CRITICAL | Multi-party approval (break-glass) |
| Production deploy / destructive | Always require explicit confirmation |

---

## 6. AUTH SURFACE POLICY (no secrets in this doc)

| Surface | Purpose | Owner |
|---------|---------|-------|
| `OCCP_ADMIN_PASSWORD` | API admin login | server `.env` |
| `OCCP_OPENAI_API_KEY` | Whisper + LLM fallback | server `.env`, container env |
| `OCCP_ANTHROPIC_API_KEY` | Primary LLM | server `.env`, container env |
| `OCCP_VOICE_TELEGRAM_BOT_TOKEN` | @OccpBrainBot | server `.env` |
| `OCCP_VOICE_TELEGRAM_OWNER_CHAT_ID` | Henry's Telegram chat_id | **MISSING/0 — TODO** |
| `OCCP_OPENCLAW_GATEWAY_TOKEN` | claw.occp.ai auth | server `.env` |
| `OCCP_WEBHOOK_SECRET` | CloudCode HMAC | server `.env` |
| `HETZNER_API_TOKEN` | Hetzner Cloud MCP | local `credentials.env` |
| `HOSTINGER_API_TOKEN` | DNS/domain MCP | local `credentials.env` |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub MCP | local `credentials.env` |
| `CLOUDFLARE_API_TOKEN` | Cloudflare MCP | local `credentials.env` |
| `EXA_API_KEY` | Web search MCP | local `credentials.env` |
| `FIRECRAWL_API_KEY` | Web scrape MCP | local `credentials.env` |
| `REF_API_KEY` | Doc search MCP | local `credentials.env` |

**Hidden vault:** `OCCP-SECURITY-VAULT.enc` AES-256-CBC, contains 15 sections (server infra, SSH, DNS, OpenClaw config, AI providers, channels, etc.)

---

## 7. DASHBOARD / CONTROL-PLANE MODEL

| Surface | URL | Purpose |
|---------|-----|---------|
| OCCP API | https://api.occp.ai | REST + 22 routes |
| OCCP Dashboard | https://dash.occp.ai | Next.js Mission Control |
| OCCP Landing | https://occp.ai | Public landing |
| OpenClaw Gateway | https://claw.occp.ai | Caddy + Basic Auth |
| OCCP News | https://news.occp.ai | Static news |
| Mailcow Admin | https://mail.magyarorszag.ai | Mail UI |
| Telegram Brain | @OccpBrainBot | OCCP voice/text input |
| Telegram OpenClaw | @occp_bot | Direct OpenClaw input |

---

## 8. OBSERVABILITY MODEL

| Layer | Tool | Status |
|-------|------|--------|
| Logs | structlog JSON in docker logs | ACTIVE |
| Audit | Merkle hash chain in `audit_entries` (261 rows) | ACTIVE |
| Health | `/api/v1/health`, `/api/v1/voice/status` | ACTIVE |
| Tracing | OpenTelemetry | NOT DEPLOYED |
| Metrics | Prometheus / Grafana | NOT DEPLOYED |
| Alert channel | Telegram (Brian) | PARTIAL |

---

## 9. PROVIDER / MODEL / BUDGET POLICY

| Tier | Provider | Model | Use |
|------|----------|-------|-----|
| Primary | Anthropic | claude-sonnet-4-6 | OpenClaw default |
| Fallback 1 | OpenAI | gpt-4.1 | OpenClaw fallback |
| Fallback 2 | OpenAI | gpt-4.1-mini | Last resort |
| OCCP planner | Anthropic | claude-sonnet-4-6 | OCCP pipeline plan stage |
| OCCP planner fallback | OpenAI | gpt-4o | If Anthropic fails |
| Voice STT | OpenAI | whisper-1 | Telegram voice |
| Echo | local | n/a | Final fallback |

Budget control: **NOT IMPLEMENTED** — known gap.

---

## 10. CHANGE-CONTROL / APPROVAL POLICY

- All `MEDIUM`/`HIGH`/`CRITICAL` tasks → ConfirmationGate → Telegram approval.
- All git commits to OCCP must reference task_id when triggered by Brian.
- All deploys: backup `/opt/occp-backup-*.tar.gz` + Docker compose rebuild + health check.
- All env var changes require server restart.
- All migration: alembic upgrade head + downgrade test.

---

## 11. HARD RULES (NON-NEGOTIABLE)

1. Brian NEVER executes directly — only delegates to specialists.
2. No execution without VAP gate.
3. No bypass of policy_engine.evaluate().
4. No execution without audit log entry.
5. No deployment without backup.
6. No DNS / billing / destructive op without explicit Henry confirmation.
7. No secret in any logs/output/git history.
8. No use of OCCP_ADMIN_PASSWORD = "changeme" in production.
9. No mixed environments — `feat/v0.8.2-enterprise-onboarding` is the active branch until merged to main.
10. All new modules MUST have a corresponding test file.
