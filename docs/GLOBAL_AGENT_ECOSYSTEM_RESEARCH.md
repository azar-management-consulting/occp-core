# OCCP — Globális Agent Control Plane & MCP Ekoszisztéma Kutatás

**Dátum**: 2026-02-26  
**Cél**: Kiemelkedő globális szereplők, fejlesztők, top 10 kapcsolódó oldal / projekt — agent governance, MCP, control plane szinten.

---

## 1. Top 10 kapcsolódó oldal / projekt (globális)

| # | Projekt / oldal | URL | Leírás | Relevancia OCCP-hez |
|---|-----------------|-----|--------|---------------------|
| 1 | **MCP Servers** | https://github.com/modelcontextprotocol/servers | Hivatalos MCP szerver implementációk (GitHub, Filesystem, Memory, stb.) | ⭐⭐⭐ Közvetlen — OCCP MCP-kat használ |
| 2 | **MCP Specification** | https://modelcontextprotocol.io/specification | Protokoll specifikáció, dokumentáció | ⭐⭐⭐ Közvetlen |
| 3 | **MCP Registry** | https://registry.modelcontextprotocol.io | Hivatalos MCP szerver registry (Anthropic, GitHub, Microsoft) | ⭐⭐⭐ Közvetlen |
| 4 | **LangGraph** | https://github.com/langchain-ai/langgraph | Agent orchestration, stateful gráfok (25k+ ⭐) | ⭐⭐ Agent pipeline minták |
| 5 | **Fiddler AI** | https://fiddler.ai | „Control Plane for AI” — telemetry, policy, audit ($30M Series C 2026) | ⭐⭐⭐ Piaci benchmark |
| 6 | **Leash (StrongDM)** | https://github.com/strongdm/leash | MCP auth, Cedar policy, MCP observer, sandbox, audit — teljes governance layer (Apache 2.0) | ⭐⭐⭐ Legközelebbi open-source hasonló |
| 7 | **OpenClaw** | https://github.com/openclaw/openclaw | Multi-channel AI gateway, onboarding, ClawHub skills (230k+ ⭐) | ⭐⭐⭐ UX/orchestration benchmark |
| 8 | **Claude Agent SDK** | https://github.com/anthropics/claude-agent-sdk-python | Anthropic hivatalos agent SDK, MCP support | ⭐⭐ LLM integráció |
| 9 | **FuseGov** | https://fusegov.com | Agentic AI governance, network-layer enforcement, audit | ⭐⭐ Governance benchmark |
| 10 | **Microsoft Foundry Control Plane** | https://learn.microsoft.com/azure/ai-foundry/control-plane | Enterprise AI governance, fleet, observability | ⭐⭐ Enterprise referencia |
| — | **EV** (eevee.build) | eevee.build | Open-source agentic control plane, K8s-style, MCP, audit, policy | ⭐⭐⭐ Konkurens — resource lifecycle |
| — | **Kagent** (CNCF) | github.com/kubeagent | K8s-native agent framework (2776+ ⭐) | ⭐⭐ DevOps fókusz |
| — | **OpenLeash** | openleash.ai | Policy gate, sidecar, local-first | ⭐⭐ Konkurens |
| — | **VeritasChain VAP** | veritaschain.org/vap | Verifiable AI Provenance (kripto, Merkle) — *más jelentés mint OCCP VAP* | ⭐ Névütközés figyelem |

---

## 2. Kiemelkedő globális szereplők

### Cégek / platformok (commercial)

| Cég | Fókusz | Funding / státusz |
|-----|--------|-------------------|
| **Fiddler AI** | AI Control Plane, telemetry, policy, audit | $100M total, Series C $30M (2026) |
| **FuseGov** | Agent governance, network-layer enforcement | Patent-pending tech |
| **StrongDM** | Leash — MCP auth, Cedar policy, MCP observer, sandbox, audit | Open source, enterprise backing |
| **Microsoft** | Foundry Control Plane, Azure AI | Enterprise |
| **Anthropic** | Claude, MCP, Responsible Scaling Policy | Frontier AI |

### Nyílt forrású projektek (GitHub)

| Projekt | Stars | Fork | Leírás |
|---------|-------|------|--------|
| modelcontextprotocol/servers | ~79k | ~9.7k | Hivatalos MCP szerverek |
| openclaw/openclaw | ~230k | ~44k | Multi-channel AI gateway |
| langchain-ai/langgraph | ~25k | — | Agent orchestration |
| anthropics/claude-agent-sdk-python | — | — | Claude agent SDK |
| strongdm/leash | ~424 | — | MCP security, policy |

### Kulcsfejlesztők / közösség

| Név | Szerep | Link |
|-----|--------|------|
| **David Soria Parra** | MCP co-creator | Anthropic |
| **Justin Spahr-Summers** | MCP co-creator | Anthropic |
| **Harrison Chase** | LangChain/LangGraph | langchain.com |
| **OpenClaw org** | openclaw, ClawHub, lobster | github.com/openclaw |

---

## 3. Részletes források

### MCP ekoszisztéma

- **Spec**: https://modelcontextprotocol.io/specification/2025-06-18  
- **Registry**: https://registry.modelcontextprotocol.io  
- **Servers repo**: https://github.com/modelcontextprotocol/servers  
- **Python SDK**: https://github.com/modelcontextprotocol/python-sdk  
- **TypeScript SDK**: https://github.com/modelcontextprotocol/typescript-sdk  

### Agent governance / control plane

- **Fiddler**: https://fiddler.ai — „The Control Plane for AI”  
- **Leash**: https://github.com/strongdm/leash — MCP auth, Cedar policy  
- **FuseGov**: https://fusegov.com — Agentic AI governance  
- **Microsoft Foundry**: https://learn.microsoft.com/azure/ai-foundry/control-plane  

### Orchestration / framework

- **LangGraph**: https://github.com/langchain-ai/langgraph  
- **OpenClaw**: https://docs.openclaw.ai  
- **ClawHub**: https://clawhub.biz — OpenClaw skills registry  

### IDE / integrációk

- **Cursor**: MCP support, `.cursor/mcp.json`  
- **Claude Desktop**: MCP connector  

---

## 4. Kutatási tanulságok OCCP-hez

| Terület | Benchmark | OCCP pozíció |
|---------|-----------|--------------|
| **MCP** | Servers, Registry, SDK-k | OCCP MCP install, config, catalog — illeszkedik |
| **Governance** | Fiddler, Leash, FuseGov | OCCP: RBAC, audit, policy engine — hasonló irány |
| **Orchestration** | LangGraph, OpenClaw | OCCP: OCCP's Verified Autonomy Pipeline (5-stage) — specifikus. *(Ne „VAP" egyedül — VeritasChain VAP = provenance.)* |
| **UX** | OpenClaw onboarding, ClawHub | OCCP: Welcome Panel, MCP/Skills UI — inspiráció |

**Összegzés**: OCCP a nyílt forrású, self-hosted szegmensben van (Leash, EV, OpenClaw közelében). Leash = infra component; OCCP = full-stack platform (dashboard, onboarding). EV/Kagent = K8s-style; OCCP = 5-stage task pipeline. VeritasChain „VAP" = provenance (külön koncepció).

---

*Források: GitHub, modelcontextprotocol.io, Fiddler, StrongDM, Microsoft Learn, OpenClaw docs, CB Insights (2026).*
