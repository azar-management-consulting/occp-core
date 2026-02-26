# Contributing to OCCP

Thank you for your interest in contributing to the Open Claude Control Plane.

## Getting Started

```bash
git clone https://github.com/azar-management-consulting/occp-core.git
cd occp-core
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make changes with tests
4. Run the test suite: `pytest -v`
5. Commit with conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
6. Open a pull request against `main`

## Code Standards

- **Python**: 3.11+, async/await, type hints required
- **TypeScript**: Strict mode, Next.js App Router patterns
- **Tests**: pytest, minimum 325 test floor enforced by CI
- **Security**: Follow OWASP Top 10. See `security/SECRETS_POLICY.md`

## CI Requirements

All PRs must pass:

| Check | Description |
|-------|-------------|
| python (3.11, 3.12, 3.13) | Test suite across Python versions |
| node | Dashboard build |
| sdk-typescript | TypeScript SDK build |
| secrets-scan | No leaked credentials |

## Architecture

- `api/` — FastAPI backend (routes, RBAC, models)
- `orchestrator/` — Pipeline engine, adapters, LLM registry
- `policy_engine/` — PII guard, injection defense, custom rules
- `dash/` — Next.js 15 dashboard (App Router, standalone output)
- `landing/` — Static landing page (occp.ai)
- `cli/` — CLI tool (`occp` command)
- `sdk/` — Python and TypeScript SDKs

## Reporting Issues

- **Bug**: Open an issue with reproduction steps
- **Security**: See [SECURITY.md](SECURITY.md) — do not use public issues
- **Feature**: Open a discussion or issue with use case description
