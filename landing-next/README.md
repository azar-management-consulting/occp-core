# landing-next — occp.ai (Next.js 15, 2026-Q2 rewrite)

Modern replacement for the legacy `landing/index.html` monolith. Built per
`.planning/OCCP_LANDING_10_2026.md` and `.planning/OCCP_WEB_10_OF_10_MASTER.md`.

**Status:** skeleton only — scope is the hero section + code-snippet tabs.
Full migration (pipeline animation, comparison table, pricing, playground)
lands in follow-up commits.

## Stack

- Next.js 15 (App Router, Turbopack, RSC)
- React 19
- Tailwind v4 (`@theme` directive, OKLCH tokens)
- Geist Sans + Geist Mono (Vercel fonts, zero runtime cost)
- Vitest + Testing Library (unit tests)
- Motion 12 + Radix Tabs (deferred: pipeline animation + real tabs)

## Why this instead of editing the 1999-line HTML

- Component reuse — hero/tabs can be shared with `docs.occp.ai` and `dash.occp.ai`
- Code-split + RSC — first contentful paint is a fraction of the old monolith
- OG tags + JSON-LD via `generateMetadata` (type-safe, no duplication)
- Standard pipeline for Vercel preview deploys per PR

## Run

```bash
cd landing-next
npm install
npm run dev     # http://localhost:3000
npm test
npm run build
```

## Files

```
landing-next/
├── package.json
├── tsconfig.json
├── next.config.ts
├── postcss.config.mjs
├── vitest.config.ts
└── src/app/
    ├── globals.css           # Tailwind v4 @theme + OKLCH tokens
    ├── layout.tsx            # Geist fonts + generateMetadata (OG/Twitter)
    ├── page.tsx              # Home → <Hero />
    └── components/
        ├── hero.tsx          # server component (copy, CTAs, trust row)
        ├── code-tabs.tsx     # client island (Python/TS/cURL tabs)
        └── hero.test.tsx     # vitest — 4 assertions
```

## Design tokens

All colors live in `globals.css` under `@theme`. They map to Tailwind
utilities automatically: `bg-brand`, `text-fg-muted`, `border-border-subtle`,
etc. See the Linear 2026-03 refresh writeup for the OKLCH rationale.

## Deploy plan

The existing `landing/index.html` stays untouched — this is additive.
Rollout sequence in `.planning/OCCP_LANDING_10_2026.md` §9:

1. Deploy to `v2.occp.ai` preview
2. QA hero copy + performance (Lighthouse budget: LCP < 1.8s)
3. 301 from `occp.ai/*` after sign-off
4. Keep legacy `v1.occp.ai` for 30 days
