# CLAUDE.md — Claude Code integration guide

This repository is designed to be edited with [Claude Code](https://claude.com/claude-code).

## Quick commands

- `npm start` — run the agent once against production OCCP API
- `npm test` — run the test suite
- `curl https://api.occp.ai/api/v1/status` — sanity-check the backend

## When you (Claude Code) edit this repo

1. **Keep `src/agent.js` under 30 lines.** This is a reference
   implementation — readability > cleverness.
2. **Never commit `.env`.** It's gitignored; keep it that way.
3. **If you add a tool**, follow the `src/tools/echo.js` shape exactly
   (`name`, `description`, `parameters`, `async run(...)`).
4. **If you add a dependency**, justify it in the commit message. The
   template intentionally stays zero-dep.

## Deploying your changes

`.github/workflows/deploy.yml` runs on push to `main` and calls the OCCP
Deploy API. Credentials come from the `OCCP_DEPLOY_TOKEN` GitHub Action
secret — never hard-code it.

## Learn more

- https://docs.occp.ai/concepts
- https://docs.occp.ai/guides/first-agent
- [AGENTS.md](./AGENTS.md)
