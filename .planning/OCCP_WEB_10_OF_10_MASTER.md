# OCCP Web 10/10 MASTER — Szintézis

**Dátum:** 2026-04-20 · v1.0
**Alap:** 5 deep-research (Landing / Dashboard / Onboarding / Docs / AI-First UX)
**Scope:** `occp.ai` landing + `dash.occp.ai` admin + `docs.occp.ai` + self-serve onboarding

---

## Executive

**Jelenlegi érettség (web surface-ek):** **6/10**
- Landing: retro CRT monolith (1999 sor static HTML), hero nem outcome-first
- Dashboard: Next.js 15 + React 19 modern stack, de **0 UI lib, 0 command palette, 0 charts**
- Onboarding: welcome panel van, de nincs OAuth, nincs "first success 5 min"
- Docs: README-style `docs/*.md`, nincs `docs.occp.ai` site
- I18n: 6 locale spec, next-intl nincs wired

**10/10 state 90 nap alatt elérhető** — 5 párhuzamos workstream.

---

## 🎯 A 10/10 OCCP web — egy mondatban

> **A `occp.ai` egy outcome-first Next.js 15 landing page (Geist font, OKLCH dark-first), `dash.occp.ai` egy shadcn/ui + Tremor + cmdk-powered keyboard-first admin, `docs.occp.ai` Fumadocs + Scalar + Inkeep AI-search docs site, **GitHub OAuth 1-click signup** → 60 sec first task, mindezt **Brian chat drawer** mindenhol `Cmd+J`-vel elérhető, HU/EN/4 locale, WCAG 2.2 AA, mobile read-only + approvals PWA.**

---

## 5 párhuzamos workstream

### W1. Landing — `occp.ai` modernizálás

**Tech:** Next.js 15 + Tailwind v4 + shadcn/ui + **Geist fonts** + OKLCH dark-first + Motion 12

**Hero copy (A control):**
> **H1:** Ship AI agents you can defend in an audit.
> **Subline:** Every autonomous action verified, logged, and reversible — before it runs.
> **CTA:** `Start free — no credit card` (primary) · `Read the docs` (ghost)

**Drop:** CRT scanlines, vignette, 3 competing CTA
**Keep (tasteful):** Geist Pixel badge, cursor blink H1 utolsó szón, monospace install box

**Sections (order):** Hero → Code snippet 3-tab → Pipeline animation (Motion scroll) → Why OCCP comparison (vs LangGraph/CrewAI) → 3×2 feature grid → "Try a Policy" playground (Monaco+OPA) → Compliance badges (SOC2, EU AI Act Art.14) → Social proof → Pricing (OSS/Team $49/Business $499/Ent) → Final CTA

**Migration:** 10-step, static HTML → Next.js → Vercel deploy. Rollback: `v1.occp.ai` subdomain 30 nap.

---

### W2. Dashboard — `dash.occp.ai` shadcn + Tremor + cmdk

**Tech adoption:**
```bash
npx shadcn@latest init     # Tailwind v4 + React 19
npx shadcn@latest add button card dialog command data-table dropdown-menu sonner sheet tabs
npm i @tremor/react recharts cmdk react-hotkeys-hook next-themes
```

**7 core view redesign:**
1. **Home** — 4 KPI + Tremor AreaChart 7d + live activity SSE feed
2. **Pipeline** — Gantt VAP stages + TanStack Table history
3. **Agents** — master-detail split (Sheet), trace waterfall (Phoenix pattern)
4. **Audit** — virtualized timeline react-virtuoso + filter sidebar
5. **MCP** — server cards + tool list Sheet + "Test tool" inline form
6. **Settings** — tabs: Profile · **Passkeys** · Tokens · LLM Providers · Notifications
7. **Admin** — users table + Impersonate row-action + feature flags toggle grid

**Dark-first OKLCH tokens** (Linear-inspired) — `@theme` Tailwind v4

**Migration:** `feat/dash-10of10-2026` branch + `NEXT_PUBLIC_DASH_V2=true` flag + `app/(v2)/` parallel route. **Zero downtime**, 5 hét 1 eng.

---

### W3. Onboarding — 5-minute first task

**Flow (stopwatch):**
- T+00:00 Landing CTA "Start free"
- T+00:10 **GitHub OAuth** redirect (primary, Google secondary)
- T+00:25 Scope consent (read:user, email)
- T+00:35 Auto-create workspace
- T+01:00 Dashboard: **API key reveal-once banner** (`occp_live_sk_...` [Copy])
- T+01:30 "Hello agent" curl snippet prefilled
- T+03:00 Task success

**Features:**
- Email verify **async** (no blocker)
- No SMS (Anthropic friction killer)
- API key prefix scoping: `occp_live_` / `occp_test_` / `occp_pat_` (GitGuardian scanner-compatible)
- **Welcome tour:** Driver.js (MIT, ~5KB) vagy custom Radix (200 LoC, zero dep)
- **North Star:** TTFTS5 — Time-To-First-Task-Success within 5 min → target 60% v1.0

**CLI:** `npx create-occp-app@latest my-agent` — `@clack/prompts` UX. Templates: hello-agent / rag-pipeline / mcp-server / scheduler.

**Drip email (Resend + PostHog):** 5 email day 0/1/3/7/14 — PostHog event `task_success` → suppress #0.

---

### W4. Docs — `docs.occp.ai`

**Stack:** **Fumadocs + Scalar + Inkeep** — Next.js App Router monorepo

**IA (8 top):**
- `/quickstart` (5 min first verified action)
- `/concepts` (Verified Autonomy, Agent, Skill, MCP, Policy)
- `/api-reference` (**Scalar** OpenAPI interactive)
- `/guides` (20+ recipe)
- `/skills` (SDK-generated catalog)
- `/mcp` (Claude Desktop, Cursor, VSCode)
- `/security`
- `/changelog` (RSS + email sub)

**Code snippet:** 4 nyelv × 2 case (happy + error) = Python / TS / cURL / Go tabs minden endpointon.

**AI search:** **Inkeep** (multi-agent: Docs Q&A + Code explainer + Skill recommender). Self-host TS SDK (OCCP brand keep).

**`llms.txt` bővítés** — jelenlegi 22 sor → full IA. **`llms-full.txt` build-time generate** (Fumadocs remark).

**Deploy:** Vercel (`docs.occp.ai` subdomain), per-PR preview, Lychee broken-link CI, Algolia DocSearch (ingyen 2026-tól).

**Alt (speed-to-ship):** Mintlify Startup 6 hó free → 6 hó múlva Fumadocs migrate.

---

### W5. AI-First UX — "Chat with Brian" everywhere

**Core:** Brian már létezik (Telegram bot + orchestrator) — dashboard **vizuális control plane**, nem replacement.

**Patterns:**
- **Chat drawer** `Cmd+J` — right-side slide-in (Claude.ai artifact pattern)
- **Shared conversation** Telegram ↔ Dashboard (thread ID sync)
- **Streaming tokens** Vercel AI SDK 3.0+ `useChat` + `streamText`
- **Tool-call cards** inline (Anthropic pattern) — approve/reject inline
- **Citation badges** (Perplexity-style) — EU AI Act Art.14 audit-ready

**Command palette 32 action** — Nav (7) + Brian/AI (6) + Job (5) + HITL (4) + Safety (3) + Search (3) + System (4)

**HITL Approval Queue:**
- Left: pending by risk
- Center: action + params + Brian reasoning + confidence % + policy triggered
- Right: audit context, past decisions
- `⌘↩` Approve, `⌘⌫` Reject, `⌘E` Modify+approve, `⌘⇧E` Escalate
- **2-op kill switch** (prod deploy, delete): Figma/Linear presence indicator

**Generative UI V1-V3:**
- V1: gallery (pre-built widgets)
- V2: sandboxed "Create widget for X" → Brian generates → preview iframe → approve
- V3: v0 full compose-mode (future)

**42 keyboard shortcuts** Linear-style. A11y WCAG 2.2 AA (Radix). I18n `next-intl` v4 (6 locale, HU primary).

---

## 90-day roadmap (5 workstream párhuzamosan)

### Month 1 (W1-4)
| Hét | W1 Landing | W2 Dashboard | W3 Onboarding | W4 Docs | W5 AI-First |
|---|---|---|---|---|---|
| 1 | Scaffold Next.js, port OG tags | shadcn init + Tremor + cmdk | GitHub OAuth wire | Fumadocs scaffold | Brian drawer component |
| 2 | Hero component split-layout | OKLCH tokens + theme toggle | Driver.js / custom tour | Scalar integration | cmdk 32 actions |
| 3 | Code snippet 3-tab + copy | Command palette global | Welcome modal + first task | QuickStart + Concepts MDX | Chat drawer streaming |
| 4 | Pipeline Motion animation | Data-table Admin/Users | API key reveal UX | 2 guide (first-agent) | Tool-call cards |

### Month 2 (W5-8)
| Hét | W1 | W2 | W3 | W4 | W5 |
|---|---|---|---|---|---|
| 5 | Playground Monaco+OPA | SSE hook + Pipeline retrofit | `create-occp-app` CLI | API reference Scalar | Approval queue UI |
| 6 | Compliance section | Agents master-detail | Sample repo hello-agent | Security section | 2-op kill switch |
| 7 | Pricing component | Audit timeline virtualized | PostHog + drip wire | Inkeep widget | Generative UI V1 gallery |
| 8 | Social proof + status | MCP panel | TTFTS5 metric track | llms-full.txt gen | Keyboard shortcuts help |

### Month 3 (W9-12)
| Hét | W1 | W2 | W3 | W4 | W5 |
|---|---|---|---|---|---|
| 9 | A/B test setup | Settings passkeys | Deploy Button GitHub | Community section | Empty state + first-run |
| 10 | CI Lighthouse budget | Admin impersonate | Free tier limits display | Algolia DocSearch | Mobile read-only PWA |
| 11 | SEO: sitemap, JSON-LD | Page migration remaining | Onboarding tour polish | Cookbook v1 (10 recipe) | Generative UI V2 sandbox |
| 12 | Launch + HN | Legacy retire `retro-*` | Launch announcement | Launch blog post | i18n 6 locale |

---

## Success metrics (12 hét után)

| Metric | Baseline | Target |
|---|---|---|
| Landing LCP | ? | < 1.8s |
| Landing CLS | ? | < 0.05 |
| Signup → First task (p75) | ? | < 5 min |
| TTFTS5 | ? | > 40% (v0.9.5), > 60% (v1.0) |
| Dashboard Cmd+K usage | 0 | > 30% WAU |
| Mobile approval time | N/A | < 30s |
| A11y axe violations | ? | 0 |
| Docs search deflection | 0 | > 40% queries get answer |
| Free → Paid conversion | ? | 2.5%+ |
| 7-day retention | ? | > 30% |

---

## Anti-patterns to avoid

1. **Big-bang rewrite** — flag-gated parallel routes kötelező
2. **Form-first UI** — chat-as-primary, form fallback
3. **Monolithic landing** — code-split, RSC, islands
4. **No HITL** — propose → commit kötelező high-risk-re (EU AI Act Art.14)
5. **Light-mode first** — Linear, Vercel, shadcn 2026 dark-first default
6. **Custom UI lib** — shadcn/ui + Tremor (80k+ + 16k+ stars, de-facto standard)
7. **Custom command palette** — cmdk (12k★, 7M weekly DL)
8. **Ignore Cmd+J chat** — OCCP unique advantage Telegram parity
9. **Verified action-free execution** — minden gen UI output sandboxolt
10. **Full mobile admin** — read-only + approvals (oncall killer use case)

---

## Platform verdict

**Stack pick OCCP web surface-ekhez 2026-Q2:**

| Surface | Tech | Fallback |
|---|---|---|
| Landing `occp.ai` | Next.js 15 + Tailwind v4 + shadcn/ui + Geist + Motion 12 | — |
| Dashboard `dash.occp.ai` | Next.js 15 + shadcn/ui + Tremor + cmdk + react-hotkeys-hook + next-intl | — |
| Docs `docs.occp.ai` | Fumadocs + Scalar + Inkeep | Mintlify Startup 6 hó |
| Signup auth | GitHub OAuth primary, Google secondary, Passkeys Phase 2 | — |
| Onboarding | Driver.js MIT (vagy custom Radix) | — |
| Analytics | PostHog self-host (GDPR, EU) | — |
| Email | Resend transactional | — |
| CLI | `@clack/prompts` + Node 20+ ESM | — |
| Status | status.occp.ai (BetterStack) | — |
| Deploy | Vercel monorepo (landing+dash+docs) | Cloudflare Pages fallback |

---

## Kapcsolódó dokumentumok

- `.planning/OCCP_LANDING_10_2026.md` — landing competitive + Geist/OKLCH + 10-step migration
- `.planning/OCCP_DASHBOARD_10_2026.md` — shadcn/ui + Tremor + cmdk + 7 view redesign
- `.planning/OCCP_ONBOARDING_10_2026.md` — 5-min TTFT + GitHub OAuth + CLI + drip
- `.planning/OCCP_DOCS_10_2026.md` — Fumadocs + Scalar + Inkeep + llms-full
- `.planning/OCCP_AI_FIRST_UX_2026.md` — Chat with Brian + 42 hotkeys + HITL queue
- `.planning/OCCP_10_OF_10_ROADMAP.md` — backend roadmap (complementary)

---

## Next konkrét lépés (4-6 óra, 0 downtime)

**Low-risk quick wins this week:**
1. `npx shadcn@latest init` on `dash/` branch
2. Install cmdk + command palette shell (no actions yet)
3. `next-themes` dark-mode toggle
4. Geist fonts swap on landing (drop Plex Mono)
5. OCCP GitHub repo `occp-skills` scaffold for skill marketplace

Ez a fél nap → **"wow" demo-able dash** shadcn-en, cmdk tooltip `Cmd+K`-val, Geist fonts landingen — zero migration risk.

**Ha ready vagy**: mondd, melyik workstream indul először (W1-W5), vagy all-parallel.

---
*v1.0 · 2026-04-20 · 5 deep-research szintézis · Brian the Brain ready*
