# docs-next — docs.occp.ai

Fumadocs 16 + Next.js 16 app for `docs.occp.ai`. Built per
`.planning/OCCP_DOCS_10_2026.md` — Fumadocs + Scalar OpenAPI + AI chat.

## Layout

```
docs-next/
├── content/docs/              MDX source (owned by us)
│   ├── index.mdx              "Get started in 60s"
│   ├── quickstart.mdx         5-min first verified action
│   ├── concepts/
│   │   └── verified-autonomy.mdx
│   └── guides/
│       └── first-agent.mdx
├── src/
│   ├── app/                   Fumadocs-generated app router
│   ├── components/
│   └── lib/
├── scripts/
│   └── generate-llms-txt.js   Standalone llms.txt generator (dev aid)
├── public/
│   ├── llms.txt
│   └── llms-full.txt
├── source.config.ts           content/docs → collections
├── next.config.mjs
├── postcss.config.mjs
├── tsconfig.json
├── eslint.config.mjs
└── package.json
```

## Local dev

```bash
cd docs-next
npm install
npm run dev          # http://localhost:3000
npm run build        # production build
npm run types:check  # tsc --noEmit + MDX typegen
```

## Deploy

Target: `docs.occp.ai` on Vercel. See `../vercel/README.md` for DNS +
project wiring. Runtime: Node 20+, build cmd `npm run build`.
