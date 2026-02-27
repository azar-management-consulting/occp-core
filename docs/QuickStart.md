# Quick Start

Get OCCP running in under 5 minutes.

## Prerequisites

- Python 3.11+ and pip
- Docker and Docker Compose (for full stack)
- Git

## Option A: Docker Compose (recommended)

```bash
git clone https://github.com/azar-management-consulting/occp-core.git
cd occp-core
cp .env.example .env  # edit with your settings
docker compose up -d
```

- API: http://localhost:8000/api/v1/status
- Dashboard: http://localhost:3000

## Option B: Local Development

```bash
git clone https://github.com/azar-management-consulting/occp-core.git
cd occp-core
pip install -e ".[dev]"
occp demo              # run the full Verified Autonomy Pipeline demo
occp demo --inject     # test prompt injection blocking
occp start             # launch API server on :8000
```

## First Steps

1. **Login**: POST to `/api/v1/auth/login` with your admin credentials
2. **Create a task**: POST to `/api/v1/tasks` with a Bearer token
3. **Run pipeline**: POST to `/api/v1/pipeline/run/{task_id}`
4. **Check audit**: GET `/api/v1/audit` for the full hash-chain log

## API Endpoints

See the full [API reference](API.md) or visit https://api.occp.ai/docs
for the interactive OpenAPI documentation.

## RBAC Roles

| Role | Access Level |
|------|-------------|
| `system_admin` | Full access — user management, all operations |
| `org_admin` | Agent management, pipeline, audit |
| `operator` | Task and pipeline execution |
| `viewer` | Read-only access |

## Next Steps

- [Architecture Overview](ARCHITECTURE.md)
- [Security Policy](../security/SECRETS_POLICY.md)
- [Competitor Comparison](COMPARISON.md)
- [v0.8.0 Roadmap](ROADMAP_v080.md)
