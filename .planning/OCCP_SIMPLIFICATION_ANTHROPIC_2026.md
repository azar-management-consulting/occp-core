# OCCP Simplification — Anthropic 2026-Q2 Stack

**Dátum:** 2026-04-20 · Scope: OCCP v0.10.0 LIVE vs Anthropic 2026-Q2 infra

---

## §1 Executive — 5 legnagyobb egyszerűsítési lehetőség

1. **Managed Agents (public beta 2026-04-08)** kiválthatja a saját FastAPI brain + SandboxExecutor + state persistence rétegeket. `agent_toolset_20260401` egyetlen flag-gel ad bash/file/web/code execution-t managed sandboxban.
2. **Claude Skills** (`github.com/anthropics/skills`) — a 19 OCCP SKILL.md-t közvetlenül plugin marketplace-re lehet tenni progressive disclosure YAML frontmatter formátumban. Nincs szükség saját skill loader-re.
3. **Memory tool (`memory_20250818`)** + **context editing** kiválthatja a saját AutoDev self-improve "context carry" rétegét **ZDR-kompatibilis** módon, client-side storage-gal.
4. **Code execution tool v3 (`code_execution_20260120`)** REPL state persistence + programmatic tool calling — kiválthatja a saját SandboxExecutor-t ~37% token megtakarítással.
5. **Prompt caching tool schemas-ra** — jelenlegi prompt registry cache-hit rate 30–50%-kal javítható (Tools → System → Messages prefix sorrend).

---

## §2 Managed Agents helyettesítheti

| OCCP komponens | Managed Agents megfelelő | Megjegyzés |
|---|---|---|
| FastAPI brain + agent loop | `POST /v1/agents` + sessions API | Beta header: `managed-agents-2026-04-01` |
| SandboxExecutor proprietary | Environment (cloud container) | Python/Node/Go preinstalled |
| WebSocket executor (OpenClaw) | SSE streaming + event model | Bidirectional `session.events.stream` |
| State persistence (audit) | Server-side event history | Persistent FS per session |
| Tool registry (bash/web/fetch) | `agent_toolset_20260401` | Bash, file ops, grep, glob, web_search, web_fetch beépítve |

**Pricing (beta):** tokens standard + **$0.08/session-hour** + web search $10/1000 call
**Rate limits:** 60 create/min, 600 read/min per org
**Research preview:** outcomes API, multi-agent, managed memory
**OCCP-re:** agent-loop + sandbox ~40% saját kód elhagyható — de proprietary gateway + policy_engine marad (§8).

---

## §3 Skills migration (19 SKILL.md → `.claude/skills/`)

**Jelenlegi:** `config/openclaw/skills/<skill>/SKILL.md`

**Anthropic Skills format:**
```yaml
---
name: deep-web-research
description: Research workflow for multi-source verification with citation.
---

# Deep Web Research
[instructions...]
```

**Migration steps:**
1. Validate YAML frontmatter: csak `name` (lowercase+hyphen) + `description` kötelező. Optional: `version`, `allowed_tools`.
2. Path → `.claude/skills/<name>/SKILL.md`
3. Progressive disclosure — SKILL.md csak metadata + rövid instrukció; nagy referencia (`templates/`, `scripts/`) csak szükség szerint töltődik.
4. Telepítés 3 útvonalon:
   - Claude Code: `/plugin marketplace add <custom-url>` (OCCP private marketplace)
   - Claude.ai: UI upload (paid plan)
   - API: `agent.skills` ref a Managed Agents create call-ban
5. Composability: skill → skill kereszthivatkozás (pl. `deep-web-research` → `final-synthesis`)

**Konkrét akció:** `occp-skills` git repo létrehozás YAML frontmatter + `allowed-tools` (RBAC tier mapping) → Managed Agent session-be injektálható.

---

## §4 Files / Memory / Code Exec integráció

### Files API (`files-api-2025-04-14`)
- `POST /v1/files`, `GET/DELETE /v1/files/{id}`
- Retention: explicit delete-ig, **nem ZDR-kompatibilis**
- Use case: dataset upload egyszer, multiple session hivatkozás
- **OCCP kiválthat:** workspace mount logic SandboxExecutor-ból

### Memory tool (`memory_20250818`, public beta 2025-10)
- **Client-side:** tool calls, OCCP maga tárolja `/memories` directory-t (**ZDR-eligible!**)
- Commands: `view, create, str_replace, insert, delete, rename`
- Context editing: automatic régi tool result cleanup
- Compaction: server-side conversation summarization
- **OCCP kiválthat:** AutoDev session context carry → ZDR-compliant client-side backend a meglévő audit hash chain-be

### Code execution tool
- `code_execution_20250522` — Python-only (legacy)
- `code_execution_20250825` — Bash + file ops (minden modelen)
- `code_execution_20260120` — **REPL state persistence + programmatic tool calling** (Opus 4.5+ / Sonnet 4.5+)
- **Free when combined with `web_search_20260209` / `web_fetch_20260209`** (csak input/output token)
- **Nem ZDR**
- `bash` vs `code_execution` vs `computer_use`: shell wrapper / Python+Bash persistent REPL / teljes desktop UI

---

## §5 Model routing (Haiku 4.5 / Sonnet 4.6 / Opus 4.7)

**Árak ($/1M token, 2026-Q2):**

| Modell | Input | Output | Cache write (5m) | Cache read |
|---|---|---|---|---|
| Haiku 4.5 | $1 | $5 | $1.25 | $0.10 |
| Sonnet 4.6 | $3 | $15 | $3.75 | $0.30 |
| Opus 4.7 | $5 | $25 | $6.25 | $0.50 |

**OCCP agent → modell mapping:**

| Agent feladat | Modell | Indok |
|---|---|---|
| Telegram intake / classify | **Haiku 4.5** | Olcsó prefilter, <500ms |
| RBAC policy check | local (no LLM) | Determinisztikus |
| Deep research, synthesis | **Sonnet 4.6** | 99% Opus 4.6 coding perf @40% cost |
| AutoDev self-improve, architecture | **Opus 4.7** | Legmélyebb agentic coding |
| Prompt registry templates | Sonnet 4.6 + cache | Meta-work |

**Interleaved thinking + tool use** Opus 4.7-nél best practice (extended thinking blocks + tool_use blocks szövögetve Messages API-ban).

---

## §6 Prompt caching maximalizálás

**Cache prefix sorrend (critical!):** `Tools → System → Messages` — tool schema változik = egész rendszer cache invalidálódik.

**OCCP javasolt lépések:**
1. **Tool schema stabilizálás:** `tool_schema.json` verzionált immutable (`tool_schema_v1.json`, `v2.json`) — minden változás új fájl
2. **1-hour cache** (`cache_control: {ttl: "1h"}`) hosszú session-höz — 2x standard input rate cache write
3. **Max 4 cache breakpoint:** system prompt vége + tool def vége + few-shot vége + előző conversation vége
4. **Workspace isolation (2026-02-05 óta):** külön workspace = külön cache
5. **Tool search tool** (`advanced-tool-use-2025-11-20` beta) — >50 tool esetén csak releváns tool tölt

**Várt hatás:** 30–50% total input cost csökkenés tipikus RAG agent requestnél.

---

## §7 10 konkrét akció (most / 1 hó / 3 hó)

### MOST (1 hét)
1. Hozz létre Anthropic API workspace-et Managed Agents beta-hoz
2. Verifikáld `tool_schema.json` immutability-t → verzió suffix = azonnal cache-hit javulás
3. Prompt registry explicit `cache_control` breakpoint system prompt végén

### 1 HÓNAP
4. PoC: 1 OCCP agent (`deep-web-research`) Managed Agent session-be — mérd latency/cost vs saját
5. 19 SKILL.md → `occp-skills` private git repo → `/plugin marketplace add` local URL-ről
6. Memory tool integráció AutoDev-be (6 command handler) OCCP audit hash chain-re
7. Model router: agent → modell mapping brain-ben (Haiku/Sonnet/Opus)

### 3 HÓNAP
8. Code execution tool `20260120` migráció — SandboxExecutor csere ahol nincs saját audit
9. Files API integráció dataset intake-re (retain-until-delete, non-ZDR)
10. Outcomes API + multi-agent research preview access → AutoDev success criteria

---

## §8 Ami NEM megy Anthropic-ra (stay local)

1. **policy_engine 5 guard + 4-tier RBAC** — EU AI Act Art.14 compliance, nem delegálható
2. **Audit hash chain** — immutable, on-premise (Hetzner); Managed Agents event history nem immutable OCCP értelemben
3. **Telegram bot polling auth + session binding** — user identity + chat_id mapping lokális
4. **OpenClaw proprietary gateway** — customer-facing branding, HU domain, saját WS protokol — SSE nem drop-in
5. **Prompt registry immutable path** (`/var/occp/prompts/v*.json`) — SHA-256 chained signed prompts
6. **Hungarian GDPR / NAIH specific data flows** — ZDR-incompatibility Files API / Code Exec esetén; Memory tool ZDR-eligible ✓

---

## Források (access 2026-04-20)

- [Claude Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview)
- [Managed Agents blog](https://claude.com/blog/claude-managed-agents)
- [anthropics/skills GitHub](https://github.com/anthropics/skills)
- [Memory tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Code execution tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
- [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Managed Agents quickstart](https://platform.claude.com/docs/en/managed-agents/quickstart)
- [InfoWorld coverage](https://www.infoworld.com/article/4156852/anthropic-rolls-out-claude-managed-agents.html)
- [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [BenchLM pricing breakdown](https://benchlm.ai/blog/posts/claude-api-pricing)
- [Claude Skills (code.claude.com)](https://code.claude.com/docs/en/skills)
- [Files API](https://platform.claude.com/docs/en/build-with-claude/files)
- [Agent capabilities API news](https://www.anthropic.com/news/agent-capabilities-api)
- [Context management news](https://www.anthropic.com/news/context-management)

---
*v1.0 · 2026-04-20 · deep-research agent output · Anthropic 2026-Q2 scope*
