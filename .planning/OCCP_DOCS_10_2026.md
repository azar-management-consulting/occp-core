# OCCP Docs 10/10 — 2026-Q2

**Dátum:** 2026-04-20 · Scope: `docs.occp.ai` live, interaktív, AI-ready

---

## §1 Platform pick: **Fumadocs + Scalar + Inkeep**

| Platform | Stars | Licenc | Ár | OpenAPI | AI search | Next.js | DX |
|---|---|---|---|---|---|---|---|
| **Fumadocs** | 11.3k | MIT | Free | Plugin | roll-own / Inkeep | ✅ App Router | **9/10** |
| **Mintlify** | SaaS | Proprietary | $250+/hó Pro | Built-in best | Beépített (metered) | Hosted | 9/10 SaaS |
| **Nextra 4** | ~18k | MIT | Free | Limitált | Pagefind | ✅ | 8/10 |
| **Starlight** | ~8k | MIT | Free | Plugin | Pagefind | Astro | 7/10 |
| **Docusaurus 3** | ~57k | MIT | Free | Plugin | Algolia | React | 7/10 |

**Miért Fumadocs:**
1. Dash már Next.js 15 App Router → **stack egység**
2. MIT OSS self-host → **nincs vendor lock-in**
3. Composable → Scalar API ref + Inkeep widget szabadon
4. 3x YoY growth 2026-03
5. Hibrid: narrative docs + interactive API reference

**Gyors alt:** Mintlify Startup Program 6 hó ingyen Pro → 6 hó múlva migrate Fumadocs.

**Decision:** ship speed > control → Mintlify. Control + brand > speed → Fumadocs.

---

## §2 Information Architecture (8 top)

```
docs.occp.ai/
├── /                → Landing (hero + "Get started in 60s")
├── /quickstart      → 5 perc: install → first verified action
├── /concepts        → Verified Autonomy, Agent, Skill, MCP, Policy
├── /api-reference   → Scalar embed
├── /guides          → 20+ recipe (first-agent, policy-writing, etc.)
├── /skills          → Skill catalog (SDK-generated)
├── /mcp             → MCP integrations (Claude Desktop, Cursor, VSCode)
├── /security        → Secrets, RBAC, audit, threat model
└── /changelog       → Keep-a-changelog + RSS + email sub
```

Plusz: `/community` (Discord, Discussions), `/cookbook`, `/llms.txt` + `/llms-full.txt`.

**Stripe-pattern:** left sidebar (stable, collapsible, max 3 depth), center narrative + snippets, right sticky language-tabbed code, top Cmd+K search + "Ask AI" + theme toggle, footer "Edit on GitHub" + timestamp + 👍/👎.

---

## §3 Interactive API Reference: **Scalar**

**Scalar > Stoplight Elements > Redoc > Swagger UI**

- Egybeépített "Try it" API client (nem iframe hack)
- Three-column Stripe-like layout out-of-box
- Next.js App Router natív: `@scalar/nextjs-api-reference`
- Tailwind v4 CSS layer compatible
- Dark mode, custom branding

```tsx
// app/api-reference/page.tsx
import { ApiReference } from '@scalar/nextjs-api-reference'
export default () => <ApiReference configuration={{
  url: 'https://api.occp.ai/openapi.json',
  theme: 'purple',
  hideDownloadButton: false,
}} />
```

**Redoc fallback** ha Scalar bugol.

---

## §4 Code Snippet Standard

**Minimum per endpoint: 4 nyelv × 2 case (happy + error)**

```mdx
<CodeTabs>
  <Tab label="cURL">
    curl https://api.occp.ai/v1/agents \
      -H "Authorization: Bearer $OCCP_API_KEY" \
      -H "Content-Type: application/json"
  </Tab>
  <Tab label="Python" default>
    from occp import OCCP
    client = OCCP(api_key=os.environ["OCCP_API_KEY"])
    agent = client.agents.create(name="my-agent")
  </Tab>
  <Tab label="TypeScript">
    import OCCP from '@occp/sdk';
    const occp = new OCCP({ apiKey: process.env.OCCP_API_KEY });
    const agent = await occp.agents.create({ name: 'my-agent' });
  </Tab>
  <Tab label="Go">
    // FELT: Go SDK v0.8.0
  </Tab>
</CodeTabs>
```

**Mandatory UX:**
- Copy button top-right
- ENV var prompt hover tooltip
- "Copy as cURL" universal button
- Error example inline (Stripe mintája)
- Rate limit badge per endpoint: `429 after 100/min per key`

---

## §5 AI Search: **Inkeep** (primary) vagy **Kapa.ai** (fallback)

| | Inkeep | Kapa.ai | Mendable | Roll-own |
|---|---|---|---|---|
| Pricing 2026 | Custom | ~$500+/hó | Custom | $50/hó |
| Multi-agent | ✅ | ❌ | ❌ | — |
| Self-host | ✅ TS SDK | Limited | ❌ | ✅ |
| Sources | MDX + web + GitHub + Discord | MDX + web | MDX | manuál |
| Widget | React drop-in | React drop-in | React | Custom |
| CX (out-of-docs) | ✅ | ❌ | Limited | — |

**Pick: Inkeep** — TS SDK self-host (OCCP brand), multi-agent (Docs Q&A + Code explainer + Skill recommender), `llms-full.txt` native.

**Roll-own alt ($50/hó):** OpenAI text-embedding-3-small + pgvector + Next.js edge. FELT: 2-3 nap dev.

---

## §6 `llms.txt` enrichment

Jelenlegi OCCP `llms.txt` **22 sor** — bővítendő.

```markdown
# OCCP — OpenCloud Control Plane

> Agent Control Plane with Verified Autonomy Pipeline.
> Every autonomous action verified before execution.

## Core Concepts
- [Verified Autonomy](https://docs.occp.ai/concepts/verified-autonomy.md)
- [Skill Architecture](https://docs.occp.ai/concepts/skills.md)
- [Policy DSL](https://docs.occp.ai/concepts/policy.md)

## API
- [REST Reference](https://docs.occp.ai/api-reference.md)
- [OpenAPI Spec](https://api.occp.ai/openapi.json)

## Skills Catalog
- [skill:deploy](https://docs.occp.ai/skills/deploy.md)
- [skill:audit](https://docs.occp.ai/skills/audit.md)
...

## MCP
- [Claude Desktop](https://docs.occp.ai/mcp/claude-desktop.md)
- [Cursor Integration](https://docs.occp.ai/mcp/cursor.md)

## Optional
- [Architecture Deep-Dive](https://docs.occp.ai/concepts/architecture.md)
- [Contributing](https://github.com/azar-management-consulting/occp-core/blob/main/CONTRIBUTING.md)
```

**Plusz `llms-full.txt`:** minden `.md` concat, 1 fájl, RAG-ready. Build-time gen (Fumadocs remark plugin). Mintlify: `llms-full.txt` 2× gyakrabban AI-queried.

---

## §7 Community section

```
/community/
├── /contributing   → PR flow, conventional commits, DCO
├── /discord        → invite + rules
├── /discussions    → GitHub Discussions embed
├── /showcase       → "Built with OCCP" gallery
├── /cookbook       → 40+ recipe MDX
└── /roadmap        → public GitHub Project embed
```

**Feedback widget:** Fumadocs `<Feedback>` + Discord webhook thumbs-down → #docs-feedback.

---

## §8 Deploy: **Vercel** (primary) / Cloudflare Pages (fallback)

**Vercel:** Next.js natív, zero-config Fumadocs. Preview per-PR. Edge cache + ISR. Hobby $0 / Pro $20/user/hó.

**Cloudflare Pages:** 500 build/hó free, unlimited bw, better global latency. Next.js via `@cloudflare/next-on-pages`.

**DNS:** `docs.occp.ai  CNAME  cname.vercel-dns.com`

**CI/CD:**
1. PR → Vercel preview (`docs-pr-123.occp.ai`)
2. Lychee broken-link check (GitHub Action) → fail on 404
3. Prettier + MDX lint
4. Algolia DocSearch reindex webhook on merge (**2026-tól ingyen minden docs site-nak**)
5. `llms-full.txt` regenerate → commit/S3

---

## §9 Migration plan: README → Structured (10 nap)

| Nap | Task |
|---|---|
| 1 | Fumadocs scaffold `docs/` subfolder + Vercel deploy `docs.occp.ai` |
| 2 | Scalar integration + `/api-reference` route live |
| 3 | `QuickStart.md` → `content/docs/quickstart.mdx` (hero) |
| 4 | `ARCHITECTURE.md` → split `/concepts/verified-autonomy` + `/skills` + `/policy` |
| 5 | `API.md` DEPRECATED → redirect to Scalar |
| 6 | `security/` → `/security/` section |
| 7 | Inkeep widget + `llms-full.txt` generator |
| 8 | Algolia DocSearch apply + index |
| 9 | GitHub Actions: lychee + MDX lint + preview |
| 10 | Launch: old docs/ → 301 redirect |

---

## §10 10-week content calendar

| Hét | Focus | Deliverable |
|---|---|---|
| W1 | Platform setup | Fumadocs live docs.occp.ai |
| W2 | Quickstart + Concepts | 5 core concept pages |
| W3 | API Reference | Scalar embed + 2 Guide |
| W4 | Skills catalog | Auto-gen from SDK |
| W5 | MCP section | Claude Desktop / Cursor / VSCode guides |
| W6 | Security + Threat Model | Full security section |
| W7 | Cookbook v1 | 10 recipe |
| W8 | AI search + llms-full | Inkeep widget live, llms-full.txt indexed |
| W9 | Community + Showcase | Discord, Discussions, "Built with" gallery |
| W10 | Polish + launch | Blog post, HN launch, Algolia DocSearch live |

---

## Konklúzió

**Fumadocs + Scalar + Inkeep + enriched `llms-full.txt` + Vercel deploy `docs.occp.ai` = 10/10 2026-Q2**, OSS brand-passzol, zero-lock, 10 hét ship.

**Fallback 2 hét:** Mintlify Startup 6 hó free, utána Fumadocs migrate.

---

## Források (2026-04-20)

- [Fumadocs](https://www.fumadocs.dev/) 11.3k★ · [Comparisons](https://www.fumadocs.dev/docs/comparisons)
- [Fumadocs vs Nextra vs Starlight 2026](https://www.pkgpulse.com/blog/fumadocs-vs-nextra-v4-vs-starlight-documentation-sites-2026)
- [Nextra 4 release](https://the-guild.dev/blog/nextra-4)
- [Mintlify Pricing](https://ferndesk.com/blog/mintlify-pricing) · [Startup Program](https://www.mintlify.com/startups)
- [Scalar](https://scalar.com/) · [Scalar Next.js](https://scalar.com/products/api-references/integrations/nextjs)
- [@scalar/nextjs-api-reference](https://www.npmjs.com/package/@scalar/nextjs-api-reference)
- [13 OpenAPI tools 2026 — Treblle](https://treblle.com/blog/best-openapi-documentation-tools)
- [llms.txt spec](https://llmstxt.org/) · [Mintlify llms.txt blog](https://www.mintlify.com/blog/what-is-llms-txt)
- [llms.txt + llms-full.txt — Fern](https://buildwithfern.com/learn/docs/ai-features/llms-txt)
- [Inkeep vs Kapa 2026](https://inkeep.com/blog/inkeep-vs-kapa)
- [Top 5 AI docs chatbots 2026](https://www.kapa.ai/blog/top-5-ai-documentation-chatbots-2026)
- [Stripe API Reference](https://docs.stripe.com/api) · [Why Stripe docs benchmark — apidog](https://apidog.com/blog/stripe-docs/)
- [Algolia DocSearch free for all](https://www.algolia.com/blog/product/algolia-docsearch-is-now-free-for-all-docs-sites)
- [lychee broken-link check](https://github.com/lycheeverse/lychee-action)

---
*v1.0 · 2026-04-20 · deep-research agent output*
