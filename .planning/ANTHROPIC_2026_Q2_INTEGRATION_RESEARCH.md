# Anthropic 2026-Q2 Agent Infrastructure — OCCP Integration Research

**Dátum:** 2026-04-20
**Scope:** Claude Managed Agents, `agent_toolset_20260401`, sandbox-runtime, MCP 2025-11-25, Opus 4.7, bidirekcionális tool execution
**Kutató:** Claude Code deep-research agent

---

## Executive Summary

- **Claude Managed Agents** 2026-04-08 óta public beta — Anthropic futtatja a Brain-t + sandbox konténert; SSE stream + REST events; 60 RPM create / 600 RPM read; **$0.08/session-hour + standard token árak**. (CONFIRMED)
- **`agent_toolset_20260401`** = teljes beépített eszközcsomag (Bash, Read/Write/Edit, Glob, Grep, Web Search, Web Fetch, code execution), `anthropic-beta: managed-agents-2026-04-01` header-rel. (CONFIRMED)
- **sandbox-runtime** = OS-szintű sandbox (Linux: bubblewrap + seccomp BPF + HTTP/SOCKS5 proxy; macOS: Seatbelt). `allowWrite`/`denyWrite` policy, deny precedence. Konténer nem szükséges. (CONFIRMED)
- **MCP 2025-11-25** spec hoz `sampling/createMessage` tool-támogatást → MCP szerverek belülről futtathatnak multi-turn agent loopot a kliens LLM-jén keresztül. (CONFIRMED)
- **Opus 4.7** (2026-04-16 release) + 1M context + natív parallel tool use + prompt caching tool schema-kra (90% kedvezmény cache read). (CONFIRMED)

---

## 1. Claude Managed Agents (public beta, 2026-04-08)

Hivatalos docs: https://platform.claude.com/docs/en/managed-agents/overview
Engineering blog: https://www.anthropic.com/engineering/managed-agents
InfoWorld: https://www.infoworld.com/article/4156852/anthropic-rolls-out-claude-managed-agents.html

**Core koncepciók:**
- **Agent** = model + system prompt + tools + MCP servers + skills (versioned, reusable ID)
- **Environment** = konténer template (pre-installed packages, networking rules, mounted files)
- **Session** = futó agent instance egy environment-ben
- **Events** = user.message, agent.message, agent.tool_use, session.status_idle — SSE stream-en érkeznek

**API endpointok (CONFIRMED, quickstart-ból):**
- `POST /v1/agents` — agent definíció
- `POST /v1/environments` — konténer template
- `POST /v1/sessions` — session indítás
- `POST /v1/sessions/{id}/events` — user event küldés
- `GET /v1/sessions/{id}/stream` — SSE (NEM WebSocket)

**Kötelező header:**
```
anthropic-version: 2023-06-01
anthropic-beta: managed-agents-2026-04-01
```

**Pricing / limitek:**
- $0.08 / session-hour (csak `running` státuszban; idle ingyen)
- Standard token pricing (Opus 4.7: $5/M in, $25/M out)
- Web search: $10 / 1000 search
- Prompt cache write: 1.25x base input (5-min TTL), read: 0.1x
- Rate limits: 60 create/min, 600 read/min org szinten
- Context window: **1M token** (Opus 4.7)

**WebSocket:** Nincs. **SSE only** (2026-04-20 állapot).

**OCCP-re kivetítve:**
- Ha Brain-t Anthropic hostolná, a saját `SandboxExecutor` réteg feleslegessé válna managed módban.
- Meglévő `exec` policy (sandbox | gateway | node) kiegészíthető: `managed` (Anthropic-side session).

---

## 2. `agent_toolset_20260401` Beta Tool Bundle

Források: Quickstart + https://dev.to/bean_bean/claude-managed-agents-deep-dive-anthropics-new-ai-agent-infrastructure-2026-3286

Egy hívással aktiválja:
- **Bash** — shell exec konténeren belül
- **File ops** — Read, Write, Edit
- **Search** — Glob, Grep
- **Web** — Web Search, Web Fetch
- **Code execution** — Python/JS (sandboxolt)

Példa Python SDK-val:
```python
client = Anthropic()
agent = client.beta.agents.create(
    name="Coding Assistant",
    model="claude-opus-4-7",
    system="You are a helpful coding assistant.",
    tools=[{"type": "agent_toolset_20260401"}],
)
```

---

## 3. `anthropic-experimental/sandbox-runtime`

Repo: https://github.com/anthropic-experimental/sandbox-runtime
NPM: https://www.npmjs.com/package/@anthropic-ai/sandbox-runtime
Claude Code docs: https://code.claude.com/docs/en/sandboxing

**Tagline:** "A lightweight sandboxing tool for enforcing filesystem and network restrictions on arbitrary processes at the OS level, without requiring a container."

**Policy model:**
```yaml
allowWrite: [".", "/tmp"]         # üres = semmi
denyWrite: [".git/hooks"]         # DENY WINS
allowRead: ["/usr", "/etc"]       # ALLOW WINS a denyRead felett
denyRead: ["/etc/shadow"]
```

**Platform:**
- **Linux:** bubblewrap (namespace isolation, non-root) + seccomp BPF + HTTP/SOCKS5 proxy
- **macOS:** Seatbelt framework (sandbox-exec)
- **Windows:** Nem támogatott (FELT)

**Protected paths always blocked:** `.bashrc`, `.git/hooks/pre-commit` még `allowWrite: ["."]` esetén is.

**Ismert gyengeségek:**
- Issue #97: auto-allow módban Claude maga letilthatja a sandboxot
- Issue #149: `denyRead` könyvtárak írhatók `--tmpfs` mount-tal Linux-on

---

## 4. MCP 2025-11-25 Spec Update

Spec (sampling): https://modelcontextprotocol.io/specification/2025-11-25/client/sampling
Anniversary: https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/

**Kulcs változás — `sampling` + tool-call:**
- MCP szerverek mostantól `sampling/createMessage`-ben küldhetnek `tools` + `toolChoice` paramétert
- Válasz: `stopReason: "toolUse"` → assistant `tool_use` blokkokat ad → kliens user message `tool_result`-okkal → szerver új samplingot indít → loop
- **`toolChoice` modes:** `auto` | `required` | `none`

**tools/call vs sampling/createMessage:**
- **`tools/call`** = kliens hívja meg a MCP szerver tool-ját (egyirányú: Client → Server tool)
- **`sampling/createMessage`** = MCP szerver kér LLM generációt a kliens-en keresztül, opcionálisan tool-okkal → **server-side agent loop**

**Capability deklaráció:**
```json
{"capabilities": {"sampling": {"tools": {}}}}
```

**Egyéb 2025-11-25 újítások:**
- Async Tasks (SEP-1686)
- OAuth javítások
- Extensions mechanism

---

## 5. Claude Opus 4.7 / Sonnet 4.6 Tool Use

Models: https://platform.claude.com/docs/en/about-claude/models/overview
Caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching

- **Opus 4.7** (2026-04-16, step-change agentic coding). Ár változatlan: $5/M in, $25/M out
- **Parallel tool use** natív, aggresszivitás hangolható
- **Prompt caching tool schemas-ra:** cache write 1.25x, read 0.1x (90% kedvezmény) — **tool schemas cache-elhetőek** a system prompt részeként
- **1M context**, extended thinking, streaming tool_use response

---

## 6. Open-Source Alternatívák — Bidirekcionális Tool Execution

Források:
- LangGraph vs CrewAI vs AutoGen 2026: https://medium.com/data-science-collective/langgraph-vs-crewai-vs-autogen-which-agent-framework-should-you-actually-use-in-2026-b8b2c84f1229
- Cloudflare Agents: https://developers.cloudflare.com/agents/api-reference/agents-api/

| Framework | MCP | A2A | Bidirekcionális RPC | WebSocket | Stream |
|---|---|---|---|---|---|
| LangGraph | Deep | No | No (graph) | Nem natív | Yes |
| CrewAI | Tools | Yes | No | Nem natív | Yes |
| AutoGen | Tools | No | No | Nem natív | Yes |
| **Cloudflare Agents** | Yes | FELT | **Yes (@callable + WS)** | **First-class** | Yes |

**Cloudflare Agents SDK — a legmodernebb publikus referencia:**
- `@callable()` decorator → type-safe RPC methods WebSocket-en
- **AgentWorkflow** class: Workflow visszahív Agent metódusokat mid-execution — **valódi bidirectional tool execution**

---

## 3 Integrációs Javaslat OCCP-hez

### A. AZONNAL (1 hét, low-risk) — Opus 4.7 + Prompt Caching Tool Schemas

A létező Brain executor réteghez adj hozzá `ClaudeExecutor` backend-et:
1. `claude-opus-4-7` model messages API-n
2. Tool schemas cache stabil prefix-ként (5-min TTL)
3. `parallel_tool_calls=true`
4. Streaming tool_use response handling

**Várható haszon:** 30-50% input cost csökkenés, 1M context → nagy codebase egyben.
**Evidence:** Ez a kutatás §5 + a jelenlegi `MockExecutor` pattern (`adapters/mock_executor.py`).

### B. 1 HÓNAP — sandbox-runtime Schema Alignment

`SandboxExecutor` policy formátumát igazítsd `anthropic-experimental/sandbox-runtime` YAML sémájához:
- `allowWrite`/`denyWrite` (deny wins)
- `allowRead`/`denyRead` (allow wins)
- HTTP/SOCKS5 proxy filter a gateway-be
- Protected paths list

**Miért most ne:** A jelenlegi saját sandbox már működik; schema-alignment jövőbeli drop-in csere előfeltétele.

### C. HOSSZÚ TÁV (3-6 hónap) — MCP Sampling + Managed Agents Fallback

**C1. MCP Sampling capability** — Brain deklarálja `sampling.tools` capability-t → MCP szerverek (jövőbeli "Claude Code MCP") saját agent loopot futtathatnak a Brain API kulcsával. **Szabványos bidirekcionális** megoldás Commit D helyett.

**C2. Managed Agents mint opt-in backend** — Dashboard választó: "Local (sandbox)" vs "Anthropic cloud (managed)". Managed módban `SandboxExecutor` kikerül → $0.08/hour + token-ek.

**Risk:** Commit D saját bidirekcionális RPC protokollja feleslegessé válhat ha MCP sampling lesz az ipari szabvány. Dönteni kell: saját protokoll vs MCP-compliant.

---

## Források (access: 2026-04-20)

**Hivatalos Anthropic:**
- https://platform.claude.com/docs/en/managed-agents/overview
- https://platform.claude.com/docs/en/managed-agents/quickstart
- https://platform.claude.com/docs/en/about-claude/models/overview
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://www.anthropic.com/engineering/managed-agents
- https://code.claude.com/docs/en/sandboxing

**GitHub:**
- https://github.com/anthropic-experimental/sandbox-runtime
- https://github.com/anthropics/anthropic-quickstarts
- https://github.com/cloudflare/agents

**MCP:**
- https://modelcontextprotocol.io/specification/2025-11-25/client/sampling
- https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/
- https://workos.com/blog/mcp-2025-11-25-spec-update

**Másodlagos:**
- https://www.infoworld.com/article/4156852/anthropic-rolls-out-claude-managed-agents.html
- https://wavespeed.ai/blog/posts/claude-managed-agents-pricing-2026/
- https://medium.com/data-science-collective/langgraph-vs-crewai-vs-autogen-which-agent-framework-should-you-actually-use-in-2026-b8b2c84f1229

---
*v1.0 · 2026-04-20 · deep-research agent output*
