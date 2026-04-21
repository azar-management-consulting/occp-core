# create-occp-app

Scaffold a new [OCCP](https://occp.ai) agent project in seconds.

## Use

```bash
# default template (hello-agent), interactive prompts:
npx create-occp-app@latest my-agent

# fully non-interactive:
npx create-occp-app@latest my-agent --template hello-agent --yes
```

## Templates

| Template        | Status  | What it is                                          |
|-----------------|---------|-----------------------------------------------------|
| `hello-agent`   | ✅      | 20-line Node starter (the default)                  |
| `rag-pipeline`  | stub    | Retrieval + verified generation (v0.11)             |
| `mcp-server`    | stub    | Custom Model Context Protocol server                |
| `scheduler`     | stub    | Cron-scheduled agents                               |

`hello-agent` is the production-ready one. Others redirect to it while
the templates mature.

## After scaffolding

```bash
cd my-agent
cp .env.example .env
# edit .env — set OCCP_API_KEY
npm install
npm start
```

Expected output:

```
[hello-agent] sending task to https://api.occp.ai ...
[hello-agent] pipeline result: pass
[hello-agent] output: Hello from your first OCCP agent ✓
```

## How it works

The CLI is a ~180-line Node 20 script using `@clack/prompts` for
interactive UX. It copies `templates/<name>/` recursively, rewrites
`package.json` with your project name, and prints next steps.

No network calls during scaffolding — templates ship with the CLI.

## License

MIT
