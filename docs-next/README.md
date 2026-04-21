# docs-next — docs.occp.ai (Fumadocs skeleton)

Source for `docs.occp.ai`, built per `.planning/OCCP_DOCS_10_2026.md`:
**Fumadocs + Scalar OpenAPI + Inkeep AI search**.

**Status:** content skeleton only — the Fumadocs Next.js app is deferred
to a follow-up session (the `create-fumadocs-app` CLI requires interactive
prompts that block headless runs). This directory contains the MDX content
that will be wired into the site once the scaffold lands.

## Structure

```
docs-next/
├── README.md                   (this file)
├── content/docs/
│   ├── index.mdx               Landing  ("Get started in 60s")
│   ├── quickstart.mdx          5-min first verified action
│   ├── concepts/
│   │   ├── index.mdx
│   │   └── verified-autonomy.mdx
│   ├── guides/
│   │   └── first-agent.mdx
│   ├── api-reference.mdx       → Scalar embed (configured in app/)
│   ├── mcp.mdx                 Claude Desktop / Cursor / VSCode
│   ├── security.mdx
│   └── changelog.mdx
└── scripts/
    └── generate-llms-txt.js    Build-time llms.txt + llms-full.txt
```

## Next steps to ship

1. Scaffold Fumadocs app in the same directory:
   ```bash
   npx create-fumadocs-app@latest . --template "+next+fuma-docs-mdx" \
       --src --search orama --linter eslint --og-image next-og
   ```
2. Run `npm i @scalar/nextjs-api-reference` for the OpenAPI page.
3. Point `source.config.ts` at `./content/docs`.
4. Deploy to Vercel under `docs.occp.ai`.

Full information architecture (8 top sections), content-calendar
(10 weeks), and AI-search integration (Inkeep) are documented in
`.planning/OCCP_DOCS_10_2026.md`.
