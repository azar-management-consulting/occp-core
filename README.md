# OpenCloud Control Plane (OCCP) – Community Edition

**Developer:** Azar Management Consulting
**Goal:** User-friendly, fast-to-deploy (1–5 min), auditable and extensible **Agent Control Plane** platform.

OCCP operates on the **Verified Autonomy Pipeline (VAP)** principle:

```
Plan → Gate → Execute → Validate → Ship
```

The CE (Community Edition) provides the open-source core. Enterprise features are available in the **OCCP Enterprise Edition (EE)** package (separate private repo).

---

## Quick Start (Docker Compose)

```bash
git clone https://github.com/opencloud-controlplane/occp-core.git
cd occp-core
cp .env.example .env
docker compose up -d
```

Dashboard: `http://localhost:3000`

## Quick Start (CLI)

```bash
pip install occp
occp start
```

## Quick Start (Development)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

---

## Architecture

| Module | Description |
|--------|-------------|
| `orchestrator/` | VAP pipeline engine – planning, gating, execution, validation, shipping |
| `policy_engine/` | Policy-as-code, audit log (SHA-256 hash chain), PII/injection guards |
| `dash/` | Web dashboard & mission control (Next.js 14 + Tailwind CSS) |
| `cli/` | Command-line interface (`occp start`, `occp run`, `occp status`) |
| `sdk/python/` | Python SDK – stdlib-only HTTP client |
| `sdk/typescript/` | TypeScript SDK – native fetch, zero deps |
| `docs/` | QuickStart, scenario docs, Claude Code commands |
| `.github/` | CI, CODEOWNERS, CONTRIBUTING, issue/PR templates |

## Verified Autonomy Pipeline (VAP)

1. **Plan** – Task planning + risk classification
2. **Gate** – Policy engine check + required approvals
3. **Execute** – Sandboxed execution
4. **Validate** – Tests, static analysis, diff review
5. **Ship** – PR, release, deploy

## Policy Engine Features (CE)

- PII detection (email, phone, SSN, credit card patterns)
- Prompt injection detection
- Resource limit enforcement
- YAML/JSON policy rules with ALLOW/DENY/REQUIRE_APPROVAL actions
- Tamper-evident audit log with SHA-256 hash chain

---

## Documentation

- [QuickStart](docs/QuickStart.md)
- [Scenario & Research](docs/forgato_scenario.md)
- [Claude Code Commands](docs/claude_code_commands.md)

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md)
Critical modules protected by [CODEOWNERS](.github/CODEOWNERS)

## License

Community Edition (occp-core) is available under the **MIT** license. See [LICENSE](LICENSE).

---

*Built by [Azar Management Consulting](https://azar.hu)*
