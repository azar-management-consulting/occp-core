# OCCP Brain + OpenClaw Agent Architecture v1.0

> **Dátum:** 2026-03-26
> **Státusz:** TERV — jóváhagyásra vár
> **Alapja:** OpenClaw v2026.3.24 + OCCP v0.9.0 multi_agent.py DAG engine

---

## Összefoglaló

Az OCCP a **Brain** (irányítás, policy, audit, minőségellenőrzés), az OpenClaw az **agent runtime** (végrehajtás, tool dispatch, session persistence). A Brain nem dolgozik — kiosztja, ellenőrzi, visszadobja vagy jóváhagyja a munkát.

```
┌─────────────────────────────────────────────────────────┐
│                    OCCP BRAIN (Control Plane)            │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │ Router   │ │ Policy   │ │ Audit   │ │ Learning   │  │
│  │ (DAG)    │ │ Engine   │ │ Merkle  │ │ Loop       │  │
│  └────┬─────┘ └────┬─────┘ └────┬────┘ └─────┬──────┘  │
│       │             │            │             │         │
│  ┌────▼─────────────▼────────────▼─────────────▼──────┐  │
│  │              Webhook Gateway (HMAC-SHA256)          │  │
│  └────────────────────────┬───────────────────────────┘  │
└───────────────────────────┼──────────────────────────────┘
                            │ A2A/Webhook
┌───────────────────────────▼──────────────────────────────┐
│              OpenClaw Runtime (Agent Execution)           │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │eng   │ │wp    │ │infra │ │design│ │content│ │social│  │
│  │-core │ │-web  │ │-ops  │ │-lab  │ │-forge│ │-grow │  │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘  │
│     │sub     │sub     │sub     │sub     │sub     │sub    │
│  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  │
│  │front│  │elem │  │dock │  │ui-  │  │seo- │  │fb-  │  │
│  │back │  │seo  │  │ssl  │  │brand│  │sales│  │ig-  │  │
│  │qa   │  │conv │  │live │  │ad   │  │exec │  │lead │  │
│  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  │
│  ┌──────┐ ┌──────┐                                       │
│  │intel │ │biz   │  + ACP Sessions (Claude/Codex/Gemini) │
│  │-res  │ │-strat│                                       │
│  └──┬───┘ └──┬───┘                                       │
│     │sub     │sub                                        │
│  ┌──▼──┐  ┌──▼──┐                                       │
│  │mkt  │  │prop │                                       │
│  │comp │  │price│                                       │
│  │tech │  │pitch│                                       │
│  └─────┘  └─────┘                                       │
└──────────────────────────────────────────────────────────┘
```

---

## 1. BRAIN — OCCP Orchestrator

**Név:** `henry-brain`
**Nem dolgozik** — csak irányít.

### Brain funkciók (OCCP modulokra mapelve)

| Funkció | OCCP Modul | Fájl |
|---------|-----------|------|
| Task routing (DAG) | `orchestrator/multi_agent.py` | AgentNode → WorkflowDefinition → wave execution |
| Policy gate | `policy_engine/engine.py` | PII/injection/resource guard minden agent output-ra |
| Audit trail | `store/audit_merkle.py` | SHA-256 hash chain, tamper-evident |
| Session management | `orchestrator/sessions.py` | Tier-based (MAIN/DM/GROUP) |
| Quality check | `orchestrator/learning_loop.py` | Degradation detection, feedback scoring |
| Skill dispatch | `orchestrator/skill_executor.py` | Policy-gated skill invocation |
| Scheduling | `orchestrator/cron_scheduler.py` | Cron-based recurring tasks |
| Channel routing | `adapters/channel_adapters.py` | Webhook/SSE/WebSocket dispatch |

### Brain skilljei (OCCP skill manifests)

```yaml
# skills/task-router/SKILL.md
---
name: task-router
description: Classify incoming task and route to specialist agent
command-dispatch: tool
command-tool: workflow_dispatch
---
Analyzes task type → selects primary agent → spawns DAG workflow.
Rules: webdev→wp-web, code→eng-core, deploy→infra-ops, design→design-lab,
       copy→content-forge, social→social-growth, research→intel-research,
       business→biz-strategy. Multi-domain → parallel wave.

# skills/approval-gate/SKILL.md
---
name: approval-gate
description: Validate agent output before delivery or next stage
disable-model-invocation: true
command-dispatch: tool
command-tool: policy_evaluate
---
Runs PolicyEngine.evaluate() on agent output.
Checks: PII leak, injection attempt, resource bounds, quality score.
PASS → next stage. FAIL → return to agent with feedback.

# skills/multi-agent-planner/SKILL.md
---
name: multi-agent-planner
description: Build DAG workflow from complex multi-domain task
---
Decomposes task into AgentNodes with depends_on edges.
Generates WorkflowDefinition with topological sort validation.
Assigns trust levels per node. Sets timeout and retry policy.

# skills/final-synthesis/SKILL.md
---
name: final-synthesis
description: Aggregate results from multiple agents into deliverable
---
Collects all agent outputs from completed workflow.
Resolves conflicts. Formats for delivery channel.
Triggers deploy-check if output includes code/infra changes.

# skills/risk-check/SKILL.md
---
name: risk-check
description: Evaluate task risk level before execution
command-dispatch: tool
command-tool: policy_evaluate
---
Maps task to risk tier: LOW (auto-execute), MEDIUM (review), HIGH (manual approve).
Production deploy, force push, credential ops → always HIGH.
```

---

## 2. OpenClaw Agent Registry — 8 Specialist Agent

### Konfiguráció: `openclaw.json`

```jsonc
{
  "agents": {
    "defaults": {
      "model": "claude-sonnet-4-6",
      "thinking": "medium",
      "subagents": {
        "model": "claude-haiku-4-5-20251001",
        "maxSpawnDepth": 2,
        "maxChildrenPerAgent": 5
      }
    },
    "list": [
      {
        "id": "eng-core",
        "name": "Engineering Agent",
        "model": "claude-sonnet-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:engineering" }],
        "workspace": "~/.openclaw/workspace-eng-core",
        "subagents": { "model": "claude-haiku-4-5-20251001" }
      },
      {
        "id": "wp-web",
        "name": "Web/WordPress Agent",
        "model": "claude-sonnet-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:wordpress" }]
      },
      {
        "id": "infra-ops",
        "name": "Infra/Deploy Agent",
        "model": "claude-sonnet-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:infrastructure" }]
      },
      {
        "id": "design-lab",
        "name": "Design/UI Agent",
        "model": "claude-sonnet-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:design" }]
      },
      {
        "id": "content-forge",
        "name": "Content/Copy Agent",
        "model": "claude-sonnet-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:content" }]
      },
      {
        "id": "social-growth",
        "name": "Social Media Agent",
        "model": "claude-sonnet-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:social" }]
      },
      {
        "id": "intel-research",
        "name": "Research/Intelligence Agent",
        "model": "claude-opus-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:research" }]
      },
      {
        "id": "biz-strategy",
        "name": "Business/Proposal Agent",
        "model": "claude-opus-4-6",
        "bindings": [{ "sessionKey": "pipeline:*:business" }]
      }
    ]
  }
}
```

---

## 3. Agent → Sub-Agent → Skill Mátrix

### AGENT 1: `eng-core` — Engineering

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `frontend-ui` | React/Next.js/CSS feladat | `nextjs-build`, `react-component`, `tailwind-layout` |
| `backend-api` | FastAPI/Python/API feladat | `fastapi-build`, `api-contract-design`, `pydantic-model` |
| `database-data` | SQL/migration/schema feladat | `alembic-migration`, `query-optimize`, `schema-design` |
| `qa-test` | Teszt írás/futtatás | `pytest-generate`, `coverage-check`, `e2e-playwright` |
| `code-review` | PR review/refactor | `refactor-safe`, `security-scan`, `code-smell-detect` |

### AGENT 2: `wp-web` — WordPress/Elementor

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `elementor-builder` | Elementor section/widget | `elementor-section-build`, `container-layout`, `responsive-check` |
| `wp-plugin-dev` | Plugin fejlesztés | `wordpress-plugin-architecture`, `hook-filter-design`, `wp-rest-endpoint` |
| `seo-page-optimizer` | SEO feladat | `yoast-optimize`, `schema-markup`, `meta-tag-audit` |
| `conversion-page-builder` | Landing/sales page | `landing-page-conversion`, `cta-placement`, `ab-test-setup` |
| `wp-debugger` | WP hiba/conflict | `wp-debug-log`, `plugin-conflict-isolate`, `query-monitor` |

### AGENT 3: `infra-ops` — Infrastructure

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `server-provision` | Új szerver/VPS | `hetzner-vps-setup`, `ssh-hardening`, `firewall-config` |
| `docker-stack` | Docker/compose | `docker-compose-prod`, `multi-stage-build`, `volume-strategy` |
| `apache-nginx-proxy` | Reverse proxy/vhost | `apache-reverse-proxy`, `nginx-config`, `proxy-pass-websocket` |
| `ssl-dns-mail` | SSL/DNS/email | `ssl-letsencrypt`, `dns-cutover`, `mailcow-config`, `spf-dkim-dmarc` |
| `live-verifier` | Deploy ellenőrzés | `deployment-verification`, `health-check`, `rollback-plan` |

### AGENT 4: `design-lab` — Design/UI

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `ui-layout` | UI wireframe/layout | `premium-ui-system`, `landing-wireframe`, `grid-system` |
| `brand-visual` | Brand/vizuális identitás | `monochrome-executive-style`, `color-system`, `typography-scale` |
| `ad-creative` | Hirdetés vizuál | `ad-visual-brief`, `social-banner`, `video-thumbnail` |
| `presentation-visual` | Prezentáció/pitch | `slide-layout`, `data-visualization`, `executive-deck` |

### AGENT 5: `content-forge` — Content/Copy

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `seo-copy` | SEO tartalom | `hungarian-seo-copy`, `keyword-density`, `internal-linking` |
| `sales-copy` | Sales/CTA szöveg | `sales-copy-framework`, `urgency-scarcity`, `benefit-stack` |
| `executive-copy` | B2B/formal szöveg | `authority-positioning`, `trust-building-copy`, `case-study` |
| `email-copy` | Email kampány | `email-sequence`, `subject-line-test`, `drip-campaign` |

### AGENT 6: `social-growth` — Social Media

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `facebook-ads` | FB hirdetés | `fb-ad-copy`, `audience-targeting`, `pixel-event` |
| `instagram-ads` | IG kampány | `ig-carousel`, `reel-script`, `story-template` |
| `tiktok-script` | TikTok/short video | `short-video-script`, `hook-first-3sec`, `trend-adapt` |
| `lead-magnet-social` | Lead gen poszt | `engagement-post-design`, `cta-optimizer`, `lead-form` |

### AGENT 7: `intel-research` — Research/Intelligence

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `market-research` | Piackutatás | `deep-web-research`, `citation-first-analysis`, `market-sizing` |
| `competitor-scan` | Versenytárs elemzés | `competitor-mapping`, `feature-matrix`, `pricing-compare` |
| `tech-radar` | Tech kutatás | `trend-watch`, `framework-evaluate`, `migration-risk` |
| `fact-check` | Tényellenőrzés | `source-verify`, `claim-validate`, `bias-detect` |
| `procurement-scan` | Közbeszerzés/pályázat | `procurement-scan`, `tender-match`, `deadline-track` |

### AGENT 8: `biz-strategy` — Business/Proposal

| Sub-Agent | Spawn Trigger | Skill-ök |
|-----------|--------------|----------|
| `proposal-writer` | Ajánlat írás | `b2b-offer-design`, `scope-define`, `deliverable-matrix` |
| `pricing-architect` | Árazás | `premium-pricing`, `tier-structure`, `roi-framing` |
| `pitch-structurer` | Pitch/prezentáció | `executive-deck-logic`, `problem-solution-fit`, `investor-narrative` |
| `partnership-mapper` | Partner keresés | `partnership-fit-analysis`, `synergy-map`, `deal-structure` |

---

## 4. Routing & Együttműködési Logika

### 4.1 Task Classification → Agent Selection

```
User Input
    │
    ▼
┌─────────────────────┐
│  BRAIN: task-router  │
│  ────────────────── │
│  1. NLP classify     │
│  2. Keyword match    │
│  3. Context history  │
└─────────┬───────────┘
          │
    ┌─────▼─────────────────────────────────────────┐
    │  Classification Rules (deterministic first)    │
    ├───────────────────────────────────────────────-─┤
    │  wordpress|elementor|wp-|plugin  → wp-web      │
    │  react|nextjs|fastapi|python|api → eng-core    │
    │  hetzner|docker|deploy|ssl|dns   → infra-ops   │
    │  design|ui|wireframe|visual|logo → design-lab   │
    │  szöveg|copy|cikk|content|seo    → content-forge│
    │  facebook|instagram|social|ad    → social-growth│
    │  kutatás|research|competitor     → intel-research│
    │  ajánlat|proposal|pricing|pitch  → biz-strategy │
    │  MULTI-DOMAIN detected           → DAG workflow │
    └───────────────────────────────────────────────-─┘
```

### 4.2 Wave-Based DAG Execution (OCCP multi_agent.py)

```
Példa: "Kell egy AI landing oldal SEO-val és deploy-al"

Brain decomposes → WorkflowDefinition:

  Wave 0 (parallel):
    ├── intel-research: "AI landing page best practices 2026"
    └── content-forge/seo-copy: "SEO keyword research + copy"

  Wave 1 (depends on Wave 0):
    ├── design-lab/ui-layout: "Landing wireframe (research alapján)"
    └── wp-web/elementor-builder: "Elementor build (copy + design)"

  Wave 2 (depends on Wave 1):
    └── infra-ops/live-verifier: "Deploy + health check"

  Wave 3 (depends on Wave 2):
    └── BRAIN/approval-gate: "Final QA + policy check"
```

### 4.3 Agent Együttműködés (Inter-Agent Communication)

**OpenClaw natív mechanizmusok:**

| Mód | Használat | OpenClaw Tool |
|-----|-----------|--------------|
| Sub-agent spawn | Szakértő sub-agent indítás | `sessions_spawn` (depth 0→1→2) |
| Session send | Üzenet másik agentnek | `sessions_send` (cross-agent message) |
| Shared workspace | Fájl megosztás agentek közt | Workspace mount (read-only cross-ref) |
| Webhook callback | OCCP Brain értesítés | `POST /hooks/agent` (HMAC signed) |
| ACP session | Külső coding agent (Claude Code/Codex) | `acpx` plugin, persistent session |

**Együttműködési minták:**

```
1. REVIEW CHAIN (szekvenciális):
   content-forge → design-lab → wp-web
   "Copy kész → Design ellenőriz → WP implementál"

2. PARALLEL SCATTER-GATHER:
   Brain spawns [intel-research, content-forge, design-lab] parallel
   Brain gathers results → final-synthesis skill → deliverable

3. ESCALATION:
   wp-web/wp-debugger nem tud megoldani →
   sessions_send → eng-core/backend-api átveszi →
   megoldás → sessions_send → wp-web folytatja

4. CROSS-REVIEW:
   eng-core kódot ír → biz-strategy/code-review ellenőriz →
   design-lab/ux-clarity-check vizuális QA →
   Brain/approval-gate final check
```

### 4.4 Quality Control Pipeline

```
Agent Output
    │
    ▼
┌───────────────────────┐
│ 1. Policy Engine Gate │ ← PII guard, injection guard, resource guard
├───────────────────────┤
│ 2. Audit Merkle Log   │ ← SHA-256 hash chain entry
├───────────────────────┤
│ 3. Learning Loop      │ ← Quality score, degradation detect
├───────────────────────┤
│ 4. Trust Level Check  │ ← L0-L5 trust threshold
├───────────────────────┤
│ 5. Human Gate         │ ← HIGH risk → manual approval
└───────────┬───────────┘
            │
     PASS ──▼── FAIL → return to agent with feedback
            │
     Next Stage / Delivery
```

---

## 5. OCCP ↔ OpenClaw Integráció (Technikai)

### 5.1 Kommunikációs Protokoll

```
OCCP Brain (Python/FastAPI)
    │
    │  POST /hooks/agent  (OpenClaw webhook endpoint)
    │  Headers:
    │    X-OCCP-Signature: HMAC-SHA256(body, shared_secret)
    │    X-OCCP-Task-ID: uuid
    │    X-OCCP-Agent-ID: eng-core
    │    X-OCCP-Workflow-ID: uuid
    │    Content-Type: application/json
    │
    ▼
OpenClaw Gateway (Node.js/WebSocket)
    │
    │  Response webhook → OCCP callback URL
    │  POST /api/v1/pipeline/{task_id}/result
    │  Headers:
    │    X-OpenClaw-Agent-ID: eng-core
    │    X-OpenClaw-Session-Key: agent:eng-core:subagent:uuid
    │
    ▼
OCCP Brain validates → policy gate → audit log → next wave
```

### 5.2 OCCP API Bővítés (Szükséges)

```python
# api/routes/agents.py — új endpoint-ok

@router.post("/api/v1/agents/{agent_id}/dispatch")
async def dispatch_to_agent(agent_id: str, task: TaskDispatch):
    """Send task to OpenClaw agent via webhook."""
    # 1. Policy gate
    # 2. Build webhook payload
    # 3. HMAC sign
    # 4. POST to OpenClaw /hooks/agent
    # 5. Store task_id → agent mapping
    # 6. Return accepted + task_id

@router.post("/api/v1/agents/{agent_id}/callback")
async def agent_callback(agent_id: str, result: AgentResult):
    """Receive completed result from OpenClaw agent."""
    # 1. Verify HMAC signature
    # 2. Policy gate on output
    # 3. Audit log entry
    # 4. Update workflow state
    # 5. Trigger next wave if all deps complete

@router.get("/api/v1/agents/registry")
async def list_agents():
    """Return all registered OpenClaw agents + status."""

@router.post("/api/v1/workflows")
async def create_workflow(definition: WorkflowCreate):
    """Create multi-agent DAG workflow."""

@router.get("/api/v1/workflows/{workflow_id}/status")
async def workflow_status(workflow_id: str):
    """Real-time workflow progress with per-node status."""
```

### 5.3 OpenClaw Workspace Struktúra

```
~/.openclaw/
├── openclaw.json                          # Global config (8 agents)
├── skills/                                # Managed skills (shared)
│   ├── task-router/SKILL.md
│   ├── approval-gate/SKILL.md
│   └── risk-check/SKILL.md
├── workspace-eng-core/
│   ├── AGENTS.md                          # Engineering constraints
│   ├── TOOLS.md                           # Allowed: bash, edit, grep
│   ├── skills/
│   │   ├── fastapi-build/SKILL.md
│   │   ├── nextjs-build/SKILL.md
│   │   ├── pytest-generate/SKILL.md
│   │   └── refactor-safe/SKILL.md
│   └── sessions/                          # JSONL transcripts
├── workspace-wp-web/
│   ├── AGENTS.md                          # WordPress constraints
│   ├── TOOLS.md                           # Allowed: wp-cli, elementor
│   ├── skills/
│   │   ├── elementor-section-build/SKILL.md
│   │   ├── wordpress-plugin-architecture/SKILL.md
│   │   └── landing-page-conversion/SKILL.md
│   └── sessions/
├── workspace-infra-ops/
│   ├── AGENTS.md                          # Infra constraints (PROD-SAFE)
│   ├── TOOLS.md                           # Allowed: ssh, docker, curl
│   ├── skills/
│   │   ├── hetzner-vps-setup/SKILL.md
│   │   ├── docker-compose-prod/SKILL.md
│   │   └── ssl-letsencrypt/SKILL.md
│   └── sessions/
├── workspace-design-lab/
├── workspace-content-forge/
├── workspace-social-growth/
├── workspace-intel-research/
└── workspace-biz-strategy/
```

---

## 6. Kapacitás & Skálázás

### Jelenlegi OCCP limitek

| Paraméter | Jelenlegi | Javasolt |
|-----------|----------|----------|
| Concurrent tasks (MAIN) | 5 | **20** (Brain tier) |
| Max workflow nodes | Unbounded | **50** (safety cap) |
| Max wave parallelism | asyncio.gather | **8** (match OpenClaw maxConcurrent) |
| Session tiers | 3 (MAIN/DM/GROUP) | **+BRAIN** (új tier, 20 concurrent) |
| Sub-agent depth | Implicit ~10 | **3** (Brain→Agent→SubAgent) |
| Sandbox timeout | 30s | **120s** (complex tasks) |
| Agent count | No limit | **8 fő + 37 sub = 45 agent** |

### OpenClaw limitek

| Paraméter | Érték | Forrás |
|-----------|-------|--------|
| maxSpawnDepth | 2 (max 5) | openclaw.json agents.defaults |
| maxChildrenPerAgent | 5 (max 20) | openclaw.json agents.defaults |
| maxConcurrent | 8 (global queue) | Gateway config |
| Session compaction | Auto (context limit) | JSONL truncation + summary |
| Memory | SQLite + vector (per agent) | Hybrid BM25 + embedding search |

### Teljes kapacitás

```
Brain dispatches → 8 fő agent (parallel max: 8)
Each agent spawns → max 5 sub-agent (depth 1→2)
Total concurrent: 8 + (8 × 5) = 48 agent session
ACP sessions: +8 external coding harnesses
Grand total: ~56 concurrent agent session
```

---

## 7. Implementációs Roadmap

### Phase 1: Brain Webhook Gateway (1-2 nap)
- [ ] `api/routes/agents.py` — dispatch/callback endpoints
- [ ] HMAC-SHA256 signing module
- [ ] Agent registry (8 agent config in DB)
- [ ] Tesztek: webhook roundtrip, signature verify

### Phase 2: OpenClaw Agent Setup (2-3 nap)
- [ ] `openclaw.json` — 8 agent config
- [ ] Per-agent workspace: AGENTS.md + TOOLS.md + skills/
- [ ] Binding rules (session key patterns)
- [ ] Webhook receiver config → OCCP callback

### Phase 3: DAG Workflow Bővítés (2-3 nap)
- [ ] `multi_agent.py` — webhook-based node execution (nem csak in-process)
- [ ] BRAIN session tier (20 concurrent)
- [ ] Wave status tracking (real-time WebSocket)
- [ ] Workflow API endpoints

### Phase 4: Skill Library (3-5 nap)
- [ ] 8 × 4-5 workspace skill = ~35 SKILL.md
- [ ] Brain-level skills (task-router, approval-gate, etc.)
- [ ] Deterministic dispatch rules
- [ ] Skill metadata gating (env vars, bins)

### Phase 5: Quality & Learning (2-3 nap)
- [ ] Cross-agent review chain
- [ ] Learning loop integration (per-agent metrics)
- [ ] Degradation alerting
- [ ] Auto-escalation rules

---

## 8. Példa Folyamatok

### "Készíts egy AI tanfolyam landing oldalt felnottkepzes.hu-ra"

```
User → OCCP Brain
  │
  ├─ task-router: MULTI-DOMAIN (wordpress + content + design + seo + deploy)
  │
  ├─ risk-check: MEDIUM (nem prod-critical, de éles site)
  │
  └─ multi-agent-planner → DAG:
     │
     Wave 0 (parallel):
     ├── intel-research → market-research: "AI tanfolyam piac HU 2026"
     └── content-forge → seo-copy: "AI tanfolyam keywords + copy"
     │
     Wave 1 (parallel, depends on W0):
     ├── design-lab → ui-layout: "Landing wireframe (kutatás alapján)"
     └── content-forge → sales-copy: "CTA + benefit stack"
     │
     Wave 2 (depends on W1):
     └── wp-web → elementor-builder + conversion-page-builder:
         "Build in Elementor (copy + design + SEO)"
     │
     Wave 3 (depends on W2):
     ├── wp-web → seo-page-optimizer: "Final SEO check"
     └── design-lab → brand-visual: "Visual QA"
     │
     Wave 4 (depends on W3):
     └── infra-ops → live-verifier: "Deploy to felnottkepzes.hu + verify"
     │
     Wave 5:
     └── BRAIN → approval-gate + final-synthesis:
         "Összesítés + audit log + értesítés"
```

### "Facebook hirdetés az AI tanfolyamra"

```
User → OCCP Brain
  │
  ├─ task-router: social-growth (primary) + content-forge (support)
  │
  └─ DAG:
     Wave 0: content-forge → sales-copy: "Hirdetés szöveg variációk"
     Wave 1: social-growth → facebook-ads: "3 ad variáció + targeting"
             design-lab → ad-creative: "Visual brief + banner"
     Wave 2: BRAIN → approval-gate: "Review + publish ready"
```

---

## Összegzés

| Szint | Elem | Darab |
|-------|------|-------|
| L0 — Brain | OCCP Orchestrator | 1 |
| L1 — Agent | OpenClaw specialist | 8 |
| L2 — Sub-Agent | OpenClaw sub-agent | 37 |
| L3 — Skill | SKILL.md per agent | ~90 |
| L4 — Tool | MCP + native + ACP | 400+ |
| **Összesen** | **Agent kapacitás** | **~56 concurrent session** |

**Protokollok:** OCCP↔OpenClaw webhook (HMAC-SHA256), OpenClaw internal (WebSocket Gateway), ACP (JSON-RPC stdio for Claude/Codex/Gemini), MCP (tool connectivity).

**Minőségbiztosítás:** Minden agent output → Policy Engine → Audit Merkle → Learning Loop → Trust Level check. HIGH risk → human approval gate.
