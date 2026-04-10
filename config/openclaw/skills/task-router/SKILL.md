---
name: task-router
description: Classify incoming task type and route to the appropriate specialist agent
user-invocable: true
command-dispatch: tool
command-tool: workflow_dispatch
---

## Task Classification Rules

Apply deterministic keyword matching first, then NLP classification if ambiguous.

**Routing map (priority order):**
- `wordpress|elementor|wp-|plugin|theme|woocommerce` → `wp-web`
- `react|nextjs|fastapi|python|api|backend|frontend|sql|migration` → `eng-core`
- `hetzner|docker|deploy|ssl|dns|server|vps|nginx|apache|mailcow` → `infra-ops`
- `design|ui|ux|wireframe|visual|logo|brand|banner|mockup` → `design-lab`
- `szöveg|copy|cikk|blog|content|seo|landing text|email kampány` → `content-forge`
- `facebook|instagram|tiktok|social|hirdetés|ad|reel|story` → `social-growth`
- `kutatás|research|competitor|piac|versenytárs|trend|tender` → `intel-research`
- `ajánlat|proposal|pricing|pitch|partnership|b2b|üzlet` → `biz-strategy`
- **MULTI-DOMAIN detected** (2+ categories) → spawn `multi-agent-planner`

## Output Format

```json
{
  "primary_agent": "wp-web",
  "confidence": 0.95,
  "matched_keywords": ["wordpress", "elementor"],
  "secondary_agents": [],
  "workflow_type": "single|dag"
}
```

## Quality Criteria
- Deterministic match takes priority over NLP inference
- If confidence < 0.7 on a single domain → treat as MULTI-DOMAIN
- Never route prod-deploy tasks without `risk-check` running first
