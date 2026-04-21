# hello-agent — OCCP starter template

Your first **OCCP agent** in 60 seconds.

## Setup

```bash
# Install
cd hello-agent
npm install

# Configure — paste your API key from https://dash.occp.ai/onboarding
cp .env.example .env
# → edit .env and set OCCP_API_KEY=occp_live_sk_...

# Run
npm start
```

You should see:

```
[hello-agent] sending task to https://api.occp.ai ...
[hello-agent] pipeline result: pass
[hello-agent] output: Hello from your first OCCP agent ✓
```

## What's happening

This template:

1. Reads your `OCCP_API_KEY` from `.env`
2. POSTs a simple task to `https://api.occp.ai/api/v1/brain/message`
3. Prints the verified pipeline result

No policy engine setup, no infrastructure. Just a 20-line Node script that shows the happy path.

## Next steps

- Replace `src/agent.js` with your own task logic
- Add a tool: drop a file under `src/tools/` and reference it in the agent
- Deploy: push the repo + click **Deploy to OCCP** on `https://dash.occp.ai`
- Read the guides at `https://docs.occp.ai/guides`

## Files

- `src/agent.js` — entry point (20 LoC)
- `src/tools/echo.js` — sample tool definition
- `.env.example` — required env vars
- `AGENTS.md` — instructions for AI coding assistants (Claude Code, Cursor, etc.)
- `CLAUDE.md` — Claude Code integration guide
- `.github/workflows/deploy.yml` — optional CI/CD

## License

MIT — use this template freely for your own agents.
