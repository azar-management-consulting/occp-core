# Changelog

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
