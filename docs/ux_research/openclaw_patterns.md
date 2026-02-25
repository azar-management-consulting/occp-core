# OpenClaw UX Patterns — Kutatás és OCCP Adaptáció

> **Források**: OpenClaw docs (2025), integrations page, session management, skills, exec, sandbox/tool policy.  
> **Cél**: OCCP v0.8.0 onboarding, MCP, skills, session policy — evidence-based UX minták.

---

## 1. Integrations oldal mintázata

### OpenClaw szerkezet
- [openclaw.ai/integrations](https://openclaw.ai/integrations)
- Kategóriák: Chat Providers, AI Models, Productivity, Music & Audio, Smart Home, Tools & Automation, Media & Creative, Social, Platforms, Community Showcase
- Egy kártya = név + 1–2 soros benefit (nem technikai) + link (ClawHub/docs)
- CTA: "Install OpenClaw and connect your first provider in minutes"
- "Want More Skills?" → ClawHub

### OCCP adaptáció
| Elem | OpenClaw | OCCP |
|------|----------|------|
| Narratíva | "Multi-channel", "same AI, different interfaces" | "Multi-agent / Multi-connector", "same governance, more sources" |
| Kártya copy | Benefit-first (pl. "Workspace messaging") | Benefit-first (pl. "Issue tracking, PR management") |
| Install flow | CLI `openclaw onboard` | Dashboard MCP Install Start → agent, Skills Install |
| Hub | Integrations page | Dashboard: /mcp, /skills, /settings/llm |

---

## 2. Session koncepció (persisztencia + biztonság)

### OpenClaw session docs
- [docs.openclaw.ai/concepts/session](https://docs.openclaw.ai/concepts/session)
- `session.dmScope`: `main` | `per-peer` | `per-channel-peer` | `per-account-channel-peer`
- **Secure DM mode**: Ha multi-user DM, `dmScope` nem `main` → külön session/user, különben context leakage
- Figyelmeztetés: "If your agent can receive DMs from **multiple people**, you should strongly consider enabling secure DM mode."

### OCCP adaptáció
- OCCP nincs DM/csatorna, de **multi-user workspace** = hasonló kockázat
- **Session scope**: single-user (continuity) vs org/multi-user (per-user/per-channel isolation)
- UI: Session panel + "Secure mode recommended" banner ha multi-user
- DB: `onboarding_session_scope` (single | per_user | per_channel)

---

## 3. Tool groups (policy UI)

### OpenClaw
- [docs.openclaw.ai/gateway/sandbox-vs-tool-policy-vs-elevated](https://docs.openclaw.ai/gateway/sandbox-vs-tool-policy-vs-elevated)
- `group:runtime` = exec, bash, process
- `group:fs` = read, write, edit, apply_patch
- `group:ui` = browser, canvas
- `group:sessions` = sessions_list, sessions_history, sessions_send, sessions_spawn, session_status
- `group:memory` = memory_search, memory_get
- `group:nodes`, `group:messaging`, `group:automation`, `group:openclaw`

### OCCP adaptáció
- OCCP tool policy: exec (sandbox/gateway), policy engine gates
- UI: "Tool groups" selector: runtime | fs | web | ui
- Role-based: viewer = read-only, operator = exec sandbox, admin = full
- Landing: "Controlled System Access" (nem "Full System Access")

---

## 4. Exec + Sandbox + Elevated

### OpenClaw exec
- [docs.openclaw.ai/tools/exec](https://docs.openclaw.ai/tools/exec)
- `host`: sandbox | gateway | node
- `security`: deny | allowlist | full
- `ask`: off | on-miss | always (approvals)
- Elevated = exec-only "run on host" when sandboxed

### OCCP adaptáció
- SandboxExecutor már van (nsjail/bubblewrap/process)
- UI: Host vs Sandbox jelölés, "elevated" csak admin + explicit consent
- Exec approvals: allowlist, safe bins, per-session `/exec` override

---

## 5. Skills modell

### OpenClaw skills
- [docs.openclaw.ai/tools/skills](https://docs.openclaw.ai/tools/skills)
- SKILL.md + YAML frontmatter, AgentSkills-compatible
- **Env injection**: per agent run, `skills.entries.<name>.env` / `apiKey`
- **Watcher**: `skills.load.watch`, `watchDebounceMs` → hot reload
- **Token impact** formula: `total = 195 + Σ(97 + len(name_escaped) + len(description_escaped) + len(location_escaped))` chars
- ClawHub: install, update, sync

### OCCP adaptáció
- Skills oldal: baseline allowlisted skills, Install/Enable/Refresh
- Token impact: karakterek + approx tokens (~4 chars/token)
- Security: trusted skills only (allowlist/signature)
- Env: `skills.entries.<name>.apiKey` — titkosított tárolás

---

## 6. Onboarding wizard (CLI)

### OpenClaw
- [docs.openclaw.ai/start/wizard](https://docs.openclaw.ai/start/wizard)
- `openclaw onboard` — Model/Auth, Gateway, Channels, Skills, Workspace, Daemon, Health
- QuickStart vs Advanced
- Local vs Remote mode

### OCCP adaptáció
- Web-based wizard a dashboard-on
- Lépések: LLM token → MCP install → Skills → Tool policies → Session scope → Verify
- Terminal-style Welcome Panel, villogó kurzor
- Tokenless: demo mode (MockExecutor) — pipeline működik, LLM nélkül

---

## 7. Token impact formula (Skills)

OpenClaw: `total = 195 + Σ(97 + len(name_escaped) + len(description_escaped) + len(location_escaped))` characters.

- XML escaping: `& < > " '` → entities
- ~4 chars/token (OpenAI-style) → `total / 4` ≈ tokens
- OCCP UI: show chars + approx tokens per skill, aggregate for inventory

## 8. Citációk és linkek

| Téma | Link |
|------|------|
| Integrations | https://openclaw.ai/integrations |
| Session Management | https://docs.openclaw.ai/concepts/session |
| Sandbox vs Tool Policy | https://docs.openclaw.ai/gateway/sandbox-vs-tool-policy-vs-elevated |
| Exec Tool | https://docs.openclaw.ai/tools/exec |
| Skills | https://docs.openclaw.ai/tools/skills |
| Onboarding Wizard | https://docs.openclaw.ai/start/wizard |
| Onboarding Overview | https://docs.openclaw.ai/start/onboarding-overview |
| ClawHub | https://clawhub.com |
