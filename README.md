<p align="center">
  <img src="assets/logo.png" alt="OCCP Logo" width="120">
</p>

<h1 align="center">OpenCloud Control Plane (OCCP)</h1>

<p align="center">
  <strong>Governance-first AI agent orchestration with Verified Autonomy Pipeline</strong><br>
  <em>Policy-gated, audit-logged, kill-switch protected. Built for production AI agent systems.</em>
</p>

<p align="center">
  <a href="https://github.com/azar-management-consulting/occp-core/actions"><img src="https://github.com/azar-management-consulting/occp-core/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.13-blue?logo=python" alt="Python 3.13">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT">
  <img src="https://img.shields.io/badge/docker-compose-blue?logo=docker" alt="Docker Compose">
  <img src="https://img.shields.io/badge/version-0.10.0-orange" alt="Version 0.10.0">
  <img src="https://img.shields.io/badge/tests-2874%20passing-brightgreen" alt="Tests: 2874 passing">
  <img src="https://img.shields.io/badge/L6-96%25%20ready-blueviolet" alt="L6 96% Ready">
  <img src="https://img.shields.io/badge/MCP%20tools-14-informational" alt="14 MCP Tools">
  <img src="https://img.shields.io/badge/agents-8%20specialists-informational" alt="8 Specialist Agents">
  <a href="https://occp.ai"><img src="https://img.shields.io/badge/live-occp.ai-success" alt="Live: occp.ai"></a>
</p>

---

## What is OCCP?

OCCP is an open-source **AI Agent Control Plane** that ensures autonomous AI agents operate safely, auditably, and within policy boundaries. Every agent task flows through the **5-stage Verified Autonomy Pipeline**:

```
Plan → Gate → Execute → Validate → Ship
```

Unlike chatbot frameworks, OCCP is a **governance-first runtime** — it controls *what agents can do*, *who approves it*, *how it's audited*, and *how to stop it*.

### Key Capabilities

- **Verified Autonomy Pipeline (VAP)** — 5-stage immutable execution sequence with skip detection
- **5 Policy Guards** — PII detection, prompt injection defense, resource limits, output sanitization, human oversight
- **Kill Switch** — hard-stop with state capture, drill mode, and automatic pipeline refusal
- **14 MCP Runtime Tools** — WordPress REST API, SSH node execution, filesystem sandbox, HTTP client
- **8 Specialist Agents** — eng-core, wp-web, infra-ops, design-lab, content-forge, social-growth, intel-research, biz-strategy
- **Telegram Integration** — bi-directional voice + text, owner DM bypass, real-time milestone reporting
- **OpenClaw Bridge** — WebSocket connection to 94-method execution gateway
- **Self-Improvement Pipeline** — autodev propose→build→verify→approve→merge with git worktree isolation
- **Architecture Memory** — 8 YAML files describing the system to itself (services, agents, tools, dataflows, boundaries, governance)
- **Observability** — Prometheus-compatible metrics, anomaly detection, behavior digest, readiness markers
- **Feature Flags** — JSON-persistent, gated deployment for safe capability rollout
- **Drift Detection** — architecture YAML vs code cross-reference validation

---

## Quick Start

```bash
git clone https://github.com/azar-management-consulting/occp-core.git
cd occp-core
pip install -e ".[dev]"
occp demo
```

### Docker Compose (Production)

```bash
docker compose up -d
# API:       http://localhost:8000
# Dashboard: http://localhost:3000
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    OCCP Brain                    │
│           (Brian the Brain orchestrator)          │
├─────────────┬───────────────┬───────────────────┤
│  Telegram   │   REST API    │   CloudCode CLI   │
│  (voice+text)│  (103 endpoints)│                  │
├─────────────┴───────────────┴───────────────────┤
│              Verified Autonomy Pipeline           │
│         Plan → Gate → Execute → Validate → Ship   │
├─────────────────────────────────────────────────┤
│  PolicyEngine (5 guards)  │  AgentToolGuard (21) │
├─────────────────────────────────────────────────┤
│  OpenClaw Executor  │  MCP Bridge (14 tools)     │
├─────────────────────────────────────────────────┤
│  Observability │ Evaluation │ Governance │ AutoDev│
├─────────────────────────────────────────────────┤
│  SQLite (9 tables)  │  Audit Hash Chain (374+)   │
└─────────────────────────────────────────────────┘
```

| Module | Description |
|--------|-------------|
| `orchestrator/` | VAP engine, BrainFlow 7-phase conversation, multi-agent DAG workflows |
| `policy_engine/` | 5 guards, ABAC rules, SHA-256 audit chain, policy-as-code |
| `api/` | FastAPI — 95 paths, 103 endpoints, JWT + RBAC |
| `adapters/` | 24 modules — planners (Claude/OpenAI/Ollama), executors (OpenClaw/sandbox), Telegram, Whisper |
| `security/` | 18 modules — agent allowlist, break-glass, vault, signing, SBOM, provenance |
| `observability/` | Prometheus metrics, anomaly detector, behavior digest, readiness markers |
| `evaluation/` | Feature flags, replay harness, canary engine, kill switch, self-modifier, proposal generator, drift detector |
| `autodev/` | Safe self-improvement — sandbox worktree, verification gate, approval queue, budget tracker |
| `architecture/` | 8 YAML self-model files (services, agents, tools, dataflows, boundaries, governance) |
| `dash/` | Next.js 15 + React 19 dashboard |
| `store/` | SQLAlchemy 2.0 async — 9 tables, 15 store modules |
| `tests/` | 2874 tests passing |

---

## Infrastructure

| Node | Role | Status |
|------|------|--------|
| Hetzner Brain (195.201.238.144) | API + Dashboard + DB + Telegram | Production |
| Hetzner OpenClaw (95.216.212.174) | 94-method execution gateway | Production |
| iMac (Tailscale mesh) | Storage + secondary control | Connected |
| MacBook Pro (Tailscale mesh) | Secondary dev | Connected |
| MacBook Air | Claude Code host + primary control | Active |

---

## L6 Readiness (Self-Improving AI)

OCCP implements bounded architectural self-redesign at **96% readiness**:

| Marker | Status |
|--------|--------|
| Architecture memory complete | ✅ |
| Telemetry active | ✅ |
| Observability interpretation | ✅ |
| Kill switch tested (E2E drill) | ✅ |
| Governance runtime enforced | ✅ |
| Self-modifier runtime | ✅ |
| Feature flags persistent | ✅ |
| Proposal engine ready | ✅ |
| Canary engine ready | ✅ |
| Drift detector ready | ✅ |
| AutoDev pipeline (safe self-improvement) | ✅ |

---

## Monitoring

Single-call daily health check:

```bash
curl -H "Authorization: Bearer $TOKEN" https://api.occp.ai/api/v1/daily-check
```

Returns: `healthy`, `score` (0-10), `alerts`, autodev state, budget, anomalies, governance, kill switch.

---

## Security

- **Immutable zones**: `security/`, `policy_engine/`, `api/auth.py` — cannot be modified by autonomous agents
- **Kill switch**: hard-stop at pipeline entry, tested via E2E drill
- **Agent allowlist**: 21 agents with per-tool permissions
- **Prompt injection guard**: 20+ regex patterns, brain-dispatched trust bypass
- **Audit trail**: hash-chained, tamper-evident, 374+ entries
- **RBAC**: 4-tier role hierarchy (viewer → operator → org_admin → system_admin)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

**Built by [Azar Management Consulting](https://azar.hu)** | [occp.ai](https://occp.ai) | [dash.occp.ai](https://dash.occp.ai)
