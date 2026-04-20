# OCCP Framework Simplification Research — 2026-Q2

**Dátum:** 2026-04-20 · 10 framework összehasonlítva GitHub + hivatalos docs alapján

---

## §1 Executive

- **Döntés: HIBRID.** A saját FastAPI+policy_engine+AutoDev stack EU AI Act Art.14 HITL + 5-guard audit szempontból egyedi. Teljes csere = regresszió-kockázat.
- **Célzott adoptálás:** LangGraph VAP-hoz, Pydantic AI structured output-hoz, Temporal durable execution-höz.
- **Top 3 jelölt:** LangGraph 1.1.8, Pydantic AI 1.84.1, Temporal Python SDK.
- **Elkerülendő:** CrewAI (role-metaphor ütközik), OpenAI Swarm (archivált), teljes AutoGen/MAF (.NET-first).
- **ROI (FELT):** -30-40% LoC a VAP orchestration-ben (~800 → ~450 LoC), de LangChain ecosystem függőség.
- **Érintetlen marad:** policy_engine, 5-guard, audit hash chain — egyik framework sem fedi le natívan.

---

## §2 Összehasonlító mátrix (10 framework × 8 OCCP követelmény)

Jelmagyarázat: `+` natív | `~` részleges/adapter | `-` nincs | `?` FELT

| # | Framework | Verzió / Stars | VAP | Guard | Audit | HITL | Subagent | MCP | Obs | HA |
|---|-----------|----------------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 1 | **LangGraph** | 1.1.8 / 29.7k | + | ~ | + | + | + | ~ | + | + |
| 2 | **CrewAI** | 1.14.2a1 / 47.8k | ~ | - | ~ | ~ | + | + | + | - |
| 3 | **AutoGen / MAF 1.0** | MAF 1.0 / 56.8k | + | - | ~ | ~ | + | + | + | ~ |
| 4 | **OpenAI Agents SDK** | (Swarm archivált) | ~ | - | ~ | - | + | ~ | ~ | -(+Temporal) |
| 5 | **Cloudflare Agents / Think** | 2026-04-17 | + | - | ~ | + | + | + | + | + |
| 6 | **Claude Agent SDK** | v0.1.63 / 6.5k | ~ | - | ~ | + | + | + | ~ | - |
| 7 | **Pydantic AI** | 1.84.1 / 16.5k | ~ | ~ | ~ | + | + | + | + | +(Temporal) |
| 8 | **smolagents** | 1.24.0 / 26.5k | - | - | - | - | ~ | ~ | - | - |
| 9 | **Temporal Python SDK** | GA 2026-03-23 | + | - | + | + | ~ | - | + | + |
| 10 | **BAML** | Rust compiler | - | - | - | - | - | - | ~ | - |

**OCCP-coverage score (+=1, ~=0.5, -=0):**
1. LangGraph: **7.0/8 (88%)**
2. Cloudflare Agents: 6.5/8 (81%)
3. Pydantic AI: 6.5/8 (81%)
4. AutoGen/MAF: 5.5/8 (69%)
5. Temporal: 5.5/8 (69%)
6. CrewAI, Claude Agent SDK: 5.0/8 (63%)
7. OpenAI Swarm: 3.5/8 (44%)
8. smolagents: 1.5/8 (19%)
9. BAML: 1.0/8 (13%) — structured-output tool, nem agent framework

**Kritikus:** 5-guard + policy-centric audit OCCP-specifikus — egyik framework sem fedi natívan. Minden opció megtartja a policy_engine-t.

---

## §3 Három migrációs szcenárió

### Opció A — "Minimal invasive": FastAPI + LangGraph (csak VAP)

**Cserél:** VAP pipeline (Plan→Gate→Execute→Validate→Ship) állapotgép
**Megtart:** FastAPI endpoints, WebSocket, policy_engine, 5 guard, audit_log, AutoDev

**Terv:**
- Minden VAP fázis = LangGraph node (5 node + conditional edges)
- `AsyncPostgresSaver` checkpoint → OCCP audit_log mirror
- HITL: LangGraph `interrupt()` → WebSocket → frontend
- policy_engine mint LangGraph `tool` a `gate` node-ból

**Előny:** bevált state machine (29.7k stars), natív checkpoint+resume, LangSmith opcionális.
**Hátrány:** LangChain transitive függőségek (~50+ package), LangGraph Platform pricing enterprise-nál.

**LoC:** -600 net -450. **Risk:** közepes. **Timeline:** 2-3 sprint.

### Opció B — "Anthropic-native": Claude Agent SDK

**Cserél:** agent loop, subagent delegation, tool exec, skills
**Megtart:** policy_engine (hook), audit_log (Claude hooks)

**Terv:**
- Runtime = Claude Agent SDK (ugyanaz mint Claude Code)
- Subagent = SDK Task tool natív parallel
- FastAPI = HTTP ingress + WS passthrough
- Policy = SDK `pre_tool_use` / `post_tool_use` hook
- MCP szerverek natívan

**Előny:** -1500 LoC (FELT), Anthropic roadmap ingyen, skills/slash/hooks free.
**Hátrány:** **Vendor lock-in** (Anthropic), durable nincs natívan (Temporal kell), v0.1.x API **INSTABILITÁS** (v0.1.48→v0.1.63 közt 15 release Q1-Q2-ben!).

**Risk:** magas. **Timeline:** 4-6 sprint. **Ne most** — várj v1.0-ra (~2026-Q4 FELT).

### Opció C — "Radikális": Cloudflare Agents (edge)

**Cserél:** MINDENT (FastAPI, WebSocket, session state)
**Megtart:** logika (policy_engine TypeScript portolva)

**Terv:**
- Agent = Durable Object per session
- WebSocket natív: `webSocketMessage(ws, message)`
- MCP natív: `McpAgent` hibernation-nal
- Project Think: durable + sub-agents + sandboxed code exec
- Deploy: Cloudflare Workers edge, globális <50ms

**Előny:** op cost -90%, HA out-of-the-box, session state Durable Object-ben.
**Hátrány:** **Python → TypeScript teljes rewrite**, Cloudflare lock-in (128MB memory, 30s CPU), EU AI Act region config külön audit, ~2000 LoC port.

**Risk:** nagyon magas. **Timeline:** 6+ hónap.

---

## §4 ROI becslés

| Opció | LoC -/+ | Új dep | Karbantartás -/év | Új komplexitás | Vendor lock |
|---|---|---|---|---|---|
| A LangGraph | -600 / +150 | ~50 pip | -80h | közepes | LangChain |
| B Claude SDK | -1500 / +300 | +1 SDK | -150h | alacsony | **Anthropic** |
| C Cloudflare | -3000 (rewrite) | +Workers | -250h op | nagyon magas | **Cloudflare** |
| Status quo | 0 | 0 | 0 | 0 | 0 |

**Break-even (FELT):**
- A: **~6 hó → érdemes**
- B: ~12 hó, de v0.1.x instabilitás → várj
- C: >24 hó → csak ha edge-deploy stratégiai

---

## §5 Decision tree

```
Production-ben? 
├── IGEN → ne big-bang
│   ├── Fő fájdalom: VAP state? → LangGraph
│   ├── Fő fájdalom: crash recovery? → Temporal
│   ├── Fő fájdalom: structured LLM output? → BAML / Pydantic AI
│   └── Fő fájdalom: MCP server írás? → Cloudflare McpAgent (edge)
│
└── Greenfield →
    ├── Python + stateful orchestration → LangGraph
    ├── Durable long-running → Temporal + Pydantic AI
    ├── Anthropic-native → Claude Agent SDK (v1.0-ra várj)
    ├── .NET shop → Microsoft Agent Framework
    ├── Multi-agent role metaphor → CrewAI
    ├── Edge + WS-first → Cloudflare Agents
    └── Edu / <1000 LoC demo → smolagents
```

---

## §6 Anti-patterns 2026-Q2

1. **Infinite agent loop** — ugyanaz tool+args. Fix: dedup, max 8 iter, exit-condition
2. **Invisible state** — LLM-re bízott emlékezés. Fix: explicit state machine
3. **All-or-nothing autonomy** — Fix: fokozatos bővülés, HITL gate (OCCP 5-guard már OK)
4. **"Agent = loop" mítosz** — nem a loop a probléma, a progress-detection. Fix: observable progress-signal minden iterációban
5. **Chasing research papers** — exotic topológiák before bevált simple patterns
6. **Multi-agent trap** — több agent ≠ automatikusan jobb; coordination overhead gyakran >előny. 8 specialist csak ha mindegyik mérhető
7. **Passing as-is through model** — LLM átírja verbatim contentet. Fix: structured pass-through
8. **LLM-as-router trap** — drága + bizonytalan. Fix: determinisztikus routing, LLM csak ambiguity-re
9. **v0.x SDK lock-in** — Claude Agent SDK 15 release Q1-Q2. Fix: ne adoptálj pre-1.0 SDK-t production-re
10. **Framework mint maintenance-csökkentés** — valójában átadja a ritmust vendor-nak

---

## §7 Záró javaslat OCCP-re

**2026-Q2 időkeret:**

1. **Most (Q2):** **Pydantic AI** mint `structured_output` layer — alacsony risk, 1.84.1 production-stable, 8 hó breaking-change mentes. policy_engine response → Pydantic modell.
2. **Q3:** **LangGraph pilot** VAP pipeline-ra (egy fázisban). Checkpoint → OCCP audit_log mirror.
3. **Q4:** Ha sikeres → teljes VAP port. Ha nem → vissza saját state machine-re.
4. **Ne most:** Claude Agent SDK (v0.1 instabil), Cloudflare (nyelv-váltás), AutoGen/MAF (.NET-first), smolagents (méret), BAML (nem framework).

**FELT:** 4-6 hónap alatt hibrid út, -40% LoC VAP+orchestration layer. policy_engine/5-guard/audit érintetlen. EU AI Act Art.14 compliance nem változik.

---

## Források (access 2026-04-20)

- [LangGraph 1.0 GA](https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available) · [GitHub](https://github.com/langchain-ai/langgraph) 29.7k stars v1.1.8
- [LangGraph HITL Docs](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [CrewAI GitHub](https://github.com/crewaiinc/crewai) 47.8k stars
- [AutoGen Swarm Docs](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/swarm.html)
- [Microsoft Agent Framework 1.0 (2026-04-03)](https://dev.to/jangwook_kim_e31e7291ad98/microsoft-agent-framework-10-build-ai-agents-in-net-and-python-kka)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [Cloudflare Agents GitHub](https://github.com/cloudflare/agents)
- [Cloudflare Agent class docs](https://developers.cloudflare.com/agents/concepts/agent-class/)
- [Project Think](https://blog.cloudflare.com/project-think/)
- [Claude Agent SDK Python](https://github.com/anthropics/claude-agent-sdk-python) 6.5k v0.1.63
- [Pydantic AI GitHub](https://github.com/pydantic/pydantic-ai) 16.5k v1.84.1 · [Docs](https://ai.pydantic.dev/)
- [Pydantic AI Temporal integration](https://ai.pydantic.dev/durable_execution/temporal/)
- [smolagents](https://github.com/huggingface/smolagents) 26.5k v1.24.0
- [Temporal + OpenAI Agents SDK GA (2026-03-23)](https://temporal.io/blog/announcing-openai-agents-sdk-integration)
- [BAML GitHub](https://github.com/BoundaryML/baml)
- [AI Agent Anti-Patterns (Allen Chan, 2026-03)](https://achan2013.medium.com/ai-agent-anti-patterns-part-1-architectural-pitfalls-that-break-enterprise-agents-before-they-32d211dded43)
- [Multi-Agent Trap](https://towardsdatascience.com/the-multi-agent-trap/)
- [Agent Deployment Gap — ZenML](https://www.zenml.io/blog/the-agent-deployment-gap-why-your-llm-loop-isnt-production-ready-and-what-to-do-about-it)

---
*v1.0 · 2026-04-20 · deep-research agent output*
