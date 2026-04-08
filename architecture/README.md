# OCCP Architecture Memory (L6 Foundation)

This directory contains the **machine-readable self-model** of the OCCP platform.
Every YAML file here is a source of truth that the system itself can introspect
to propose redesigns, detect drift, and validate migrations.

## Files

| File | Purpose | Consumed by |
|------|---------|-------------|
| `services.yaml` | All backend + frontend services and their endpoints | Health checks, dashboard, redesign engine |
| `agents.yaml` | All 8 specialists + brain + seeded pipeline agents | AgentToolGuard, routing, RFC scoring |
| `tools.yaml` | MCP bridge tools + per-agent permissions | MCP bridge registration, allowlist generation |
| `dataflows.yaml` | Request paths: Telegram → Brain → Pipeline → OpenClaw | Tracing, anomaly detection, redesign impact |
| `boundaries.yaml` | Immutable vs mutable module zones | Self-modifier gate, governance |
| `runtime_inventory.yaml` | Runtime dependencies + versions + host nodes | SBOM, upgrade planner |
| `governance.yaml` | L6 rules: what Claude Code may or may not autonomously modify | Meta-supervisor, audit |

## Update policy

- **Human-authored** initially (this baseline).
- **Claude Code may propose updates** via RFCs in `.planning/rfc/`.
- **Any change to a YAML here requires a passing test in `tests/architecture/`**.
- **Any change to `governance.yaml` requires 2 reviewers** (Henry + 1).

## Validation

Run `pytest tests/architecture/` to verify:
- YAML parses
- All referenced services/agents/tools exist in code
- No orphan references
- governance.yaml immutable_paths are real paths

## L6 principle

OCCP at L6 reads these files at runtime and uses them to:
1. Observe its own structure
2. Detect drift (code vs declaration)
3. Generate redesign proposals grounded in the model
4. Validate migrations against boundaries
