# AGENTS — AI coding-assistant guide

This file follows the emerging 2026 convention (Next.js, Vercel, and the
[AGENTS.md](https://agents.md) initiative) of leaving a short guide in the
repo root for AI coding assistants like Claude Code, Cursor, and Aider.

## Project summary

`hello-agent` is a minimal JavaScript starter that posts a task to the
[OCCP Brain API](https://api.occp.ai) and prints the pipeline result.

## Conventions

- **ESM-only.** All files use `import` / `export`, never `require`.
- **Zero runtime dependencies.** We use Node 20+ built-ins (`fetch`,
  `node:fs`) intentionally so the template stays reviewable.
- **No secrets in source.** Read `OCCP_API_KEY` from `.env` (gitignored).
- **20-line budget.** `src/agent.js` is the happy-path script — resist
  the urge to make it a framework.

## Common tasks for AI assistants

- **"Add a tool"** → create `src/tools/<name>.js`, export a shape like
  `src/tools/echo.js`. Pure functions only.
- **"Swap the task"** → edit the `task` constant in `src/agent.js`. Don't
  build a task-runner yet — keep it one task, one print.
- **"Deploy to OCCP"** → do NOT edit the agent code to handle production
  routing. Use the Deploy button on https://dash.occp.ai — the platform
  wires auth for you.

## What not to do

- Do not add a build step. This runs with plain `node src/agent.js`.
- Do not add TypeScript transpilation. Use `// @ts-check` if you want
  types — the editor will do the rest.
- Do not bring in a framework (Express, Fastify, etc.). If you need a
  server, graduate to the `mcp-server` template.

## References

- [OCCP docs](https://docs.occp.ai/)
- [OCCP dashboard](https://dash.occp.ai)
- [Brain API reference](https://api.occp.ai/docs)
- [AGENTS.md spec](https://agents.md)
