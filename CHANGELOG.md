# Changelog

## 0.4.0 – Dashboard Auth & Next.js 15

### Dashboard
- **Login page**: Full JWT authentication UI with OCCP branding
  - AuthProvider context with localStorage token persistence
  - AuthGuard route protection (redirect to /login)
  - Bearer token auto-injection in all API calls
  - 401 response handling with auto-redirect
  - Nav: user display, sign out button, hidden on /login

### Upgrades
- **Next.js 15** (from 14.2.x) + **React 19** (from 18.3.x)
- **Node.js 22** Alpine base image in Dockerfile
- TypeScript types updated (@types/node ^22, @types/react ^19)
- 0 npm vulnerabilities

### Fixes
- OG image URL: added `metadataBase` for absolute social sharing URLs
- Version bumped to 0.4.0 across all modules (API, CLI, SDK, dashboard, tests)

---

## 0.3.0 – Production Intelligence & Branding

### Core
- **LLM Planner adapter**: Anthropic Claude integration for real planning
- **Prompt injection detection**: regex + keyword guards in policy engine
- **Pipeline injection rejection**: 422 on detected injection attempts

### Dashboard
- Real-time pipeline status visualization
- Policy evaluation UI
- OCCP branding (favicon, OG tags, logo)

### Infrastructure
- Apache reverse proxy config (api.occp.ai, dash.occp.ai)
- Docker healthchecks for both services
- CI/CD: GitHub Actions with workflow_call trigger
- 145 passing tests (100% pass rate)

---

## 0.2.0 – Production Platform

### Core
- **FastAPI REST API**: Full CRUD for tasks, agents, pipeline execution
- **JWT Authentication**: Login, refresh, protected endpoints
- **Audit API**: Hash-chain verified audit log endpoint
- **Policy evaluation endpoint**: Runtime content checking

### CLI Enhancements
- Live API client mode (connects to running server)
- `occp export` with JSON/CSV formats

### SDK Updates
- Python SDK: urllib-based HTTP client with full API coverage
- TypeScript SDK: fetch-based client with strict types

### Dashboard
- Next.js 14 App Router pages (Mission Control, Pipeline, Policy, Audit)
- Tailwind CSS with custom OCCP theme
- API integration layer with error handling

### Infrastructure
- Docker Compose: API + Dashboard + test runner
- Production deployment on Hetzner VPS
- 100+ passing tests

---

## 0.1.0 – Initial Release

### Core Modules
- **Orchestrator**: Verified Autonomy Pipeline (Plan → Gate → Execute → Validate → Ship)
  - Task lifecycle models with status transitions
  - Agent scheduler with concurrency control
  - Protocol-based adapter system (Planner, Executor, Validator, Shipper)
  - Full exception hierarchy

- **Policy Engine**: Policy-as-code enforcement
  - PII detection guard (email, phone, SSN, credit card)
  - Prompt injection detection guard
  - Resource limit guard
  - YAML/JSON policy rules (ALLOW/DENY/REQUIRE_APPROVAL)
  - Tamper-evident audit log with SHA-256 hash chain
  - Async evaluation API

- **CLI**: Command-line interface
  - `occp start` – Launch platform
  - `occp run <workflow>` – Execute workflow (with --dry-run)
  - `occp status` – Platform status
  - `occp export` – Audit log export (JSON/CSV)

- **SDK (Python)**: stdlib-only HTTP client
  - Full REST API coverage (status, agents, workflows, tasks, audit)
  - Error hierarchy (auth, not found, rate limit, validation)

- **SDK (TypeScript)**: Native fetch client (Node 18+)
  - ESM + strict TypeScript
  - Full type definitions for all API entities
  - Error classes with retry support

- **Dashboard**: Next.js 14 App Router + Tailwind CSS
  - Mission Control landing page
  - VAP pipeline status visualization
  - Responsive design with OCCP branding

### Infrastructure
- Docker Compose setup (dash + orchestrator + test runner)
- GitHub Actions CI (Python 3.11/3.12 + Node 20 + TypeScript)
- pyproject.toml with editable install support
- 37 passing tests (orchestrator, policy engine, CLI)

### Community
- MIT License
- CODEOWNERS for critical modules
- CONTRIBUTING.md (Hungarian)
- CODE_OF_CONDUCT.md
- Issue templates (bug report, feature request)
- PR template
