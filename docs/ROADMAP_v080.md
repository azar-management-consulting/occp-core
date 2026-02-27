# OCCP v0.8.0 Roadmap

> **Version**: 1.0.0 | **Created**: 2026-02-24
> **Status**: DESIGN ONLY — no implementation in this document
> **Baseline**: v0.7.0 (16 merged PRs, 313 tests, deploy verified 2026-02-24)

---

## Pre-Roadmap: Critical Findings from v0.7.0 Verification

| # | Finding | Severity | Source |
|---|---------|----------|--------|
| F1 | `PermissionChecker` not wired to ANY route — RBAC not enforced | **P0** | `api/routes/*.py` — zero imports of `PermissionChecker` |
| F2 | Default admin password `changeme` in production | **P0** | `config/settings.py:48`, server `.env` missing `OCCP_ADMIN_PASSWORD` |
| F3 | No `/auth/register` endpoint — users cannot be created via API | **P1** | `api/routes/auth.py` — only `/login` and `/refresh` |
| F4 | Production runs SQLite — no PostgreSQL deployed | **P0** | `sqlite+aiosqlite:///data/occp.db` |
| F5 | Sandbox fallback to `process` (rlimit only) despite kernel support | **P0** | `detect_backend()` → `process`; nsjail/bwrap not installed |
| F6 | CSP header missing on `dash.occp.ai` | **P1** | `curl -sI` — no `Content-Security-Policy` |
| F7 | CHANGELOG not updated for v0.7.0 | **P0** | Last entry: v0.6.0 |
| F8 | README says "74+ tests" — actual: 313 | **P0** | `README.md` |
| F9 | Anthropic API credits exhausted | **P1** | Task plans contain credit error |

---

## Sections

| ID | Title | Priority | Effort | Dependencies |
|----|-------|----------|--------|-------------|
| B7 | Housekeeping | P0 | S (< 1 day) | None |
| B1 | PostgreSQL Production Cutover | P0 | L (3-5 days) | B7 |
| B2 | Sandbox Hardening | P0 | M (2-3 days) | B7 |
| B5 | Observability | P1 | M (2-3 days) | None |
| B4 | API Key Management | P1 | M (2-3 days) | B1 |
| B3 | Multi-Tenancy Foundation | P1 | L (5-7 days) | B1 |
| B6 | Dashboard RBAC Gating | P2 | M (2-3 days) | B3 |

---

## B7 — HOUSEKEEPING [P0 — do first]

**Effort**: S (< 1 day) | **Dependencies**: None

### a) CHANGELOG.md: Add v0.7.0 Entry

```markdown
## 0.7.0 – ORM Migration, RBAC & Sandbox Isolation

### Core
- **SQLAlchemy 2.0 ORM**: Full migration from raw SQL to async Mapped models
  - Cross-dialect types: JSONBText (JSONB/TEXT), GUID (UUID/CHAR)
  - Dual-backend engine factory (aiosqlite / asyncpg)
- **Casbin RBAC**: 4-role hierarchy (system_admin > admin > operator > viewer)
  - UserStore with argon2-cffi password hashing
  - JWT HS256 authentication with 24h expiry
- **Sandbox Executor**: nsjail → bwrap → process fallback chain
  - Auto-detection based on available binaries and kernel capabilities
  - Configurable limits: time (30s), memory (256MB), PIDs (32)

### Security
- SecurityHeadersMiddleware (X-Content-Type-Options, X-Frame-Options, etc.)
- RateLimitMiddleware (20 req/60s on auth endpoints)
- RequestLoggingMiddleware with structlog JSON output

### Infrastructure
- Alembic async migrations with dual-backend support
- pydantic-settings configuration (OCCP_ prefix, .env file)
- Docker Compose: healthcheck, read_only, no-new-privileges
- 313 passing tests (from 165)
```

### b) README.md Updates

- Test count: `74+ tests` → `313 tests`
- Add RBAC section (4 roles, Casbin)
- Add Sandbox section (fallback chain)
- Add Architecture diagram (ASCII)

### c) pyproject.toml

```toml
"Development Status :: 4 - Beta"
```

### d) Wire PermissionChecker to Routes (CRITICAL — from F1)

Apply `PermissionChecker` dependency to all protected routes:

| Route file | Endpoints | Required permission |
|------------|-----------|-------------------|
| `api/routes/tasks.py` | POST /tasks | `tasks`, `create` |
| `api/routes/tasks.py` | GET /tasks | `tasks`, `read` |
| `api/routes/agents.py` | POST /agents | `agents`, `create` |
| `api/routes/agents.py` | DELETE /agents/{id} | `agents`, `delete` |
| `api/routes/policy.py` | PUT /policy | `policy`, `write` |
| `api/routes/pipeline.py` | POST /pipeline/{id}/run | `pipeline`, `execute` |

### e) Add `/auth/register` endpoint (from F3)

- `POST /api/v1/auth/register` — admin-only (requires `system_admin` role)
- Body: `{"username", "password", "role", "display_name"}`
- Uses existing `UserStore.create_user()` method

### f) Set Production Admin Password (from F2)

- Add `OCCP_ADMIN_PASSWORD` to server `.env` with strong password
- Add CSP header to `SecurityHeadersMiddleware` (from F6)

### Acceptance Criteria

- [ ] CHANGELOG has v0.7.0 entry
- [ ] README reflects actual state (313 tests, RBAC, sandbox)
- [ ] `PermissionChecker` wired to all protected routes
- [ ] `/auth/register` endpoint works (admin-only)
- [ ] Production admin password changed from default
- [ ] CSP header present on dash.occp.ai
- [ ] `pytest -q` still passes

---

## B1 — POSTGRESQL PRODUCTION CUTOVER [P0 — critical path]

**Effort**: L (3-5 days) | **Dependencies**: B7 | **Status**: planned

### Design Constraints (Research-Validated)

| Constraint | Source | Impact |
|-----------|--------|--------|
| `ACCESS EXCLUSIVE` locks block ALL reads/writes during DDL | PG 16 explicit-locking docs | Must use `lock_timeout` to fail fast |
| `ALTER ADD COLUMN` with `DEFAULT` is instant on PG 11+ | PG 16 ALTER TABLE docs | Safe for PG 16 target |
| Alembic autogenerate can misinterpret renames as drop+add | Alembic batch.html docs | Ban column renames; use expand/contract |
| `CREATE INDEX CONCURRENTLY` cannot run inside transaction | PG 16 CREATE INDEX docs | Requires `op.execute("COMMIT")` first |
| `asyncpg` uses prepared statements; PgBouncer `transaction` mode breaks them | asyncpg FAQ | Skip PgBouncer — native pooling sufficient |

### a) Alembic `env.py` Enhancements

Current `do_run_migrations()` at `migrations/env.py:67-78` lacks safety timeouts.

```python
def do_run_migrations(connection: Connection) -> None:
    url = _get_url()
    if not is_sqlite(url):
        connection.execute(text("SET lock_timeout = '4s'"))
        connection.execute(text("SET statement_timeout = '30s'"))

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=is_sqlite(url),
        compare_type=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()
```

Import needed: `from sqlalchemy import text`

### b) Migration Safety Rules

| Pattern | Rule |
|---------|------|
| Add column | Always `nullable=True` or with `server_default` |
| Add NOT NULL | 3-step: add nullable → batch backfill 1000/tx → `ALTER ADD CONSTRAINT NOT VALID` → `VALIDATE CONSTRAINT` |
| Create index | `CREATE INDEX CONCURRENTLY` in separate non-transactional migration |
| Column rename | **BANNED** — always expand/contract |
| Add FK | Two-phase: `NOT VALID` → `VALIDATE CONSTRAINT` |
| Column type change | **BANNED** in-place — use expand/contract |

### c) Docker Compose: PostgreSQL Service

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: occp
      POSTGRES_USER: occp
      POSTGRES_PASSWORD: ${OCCP_PG_PASSWORD:?Set OCCP_PG_PASSWORD in .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 512M
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U occp"]
      interval: 10s
      timeout: 5s
      retries: 5
    security_opt:
      - no-new-privileges:true
    shm_size: 128mb
    command:
      - postgres
      - -c
      - shared_buffers=128MB
      - -c
      - effective_cache_size=256MB
      - -c
      - work_mem=4MB
      - -c
      - maintenance_work_mem=64MB
      - -c
      - max_connections=50
      - -c
      - wal_buffers=4MB
      - -c
      - random_page_cost=1.1
      - -c
      - effective_io_concurrency=200
      - -c
      - max_wal_size=256MB
      - -c
      - idle_in_transaction_session_timeout=60000
```

API service update:

```yaml
  api:
    environment:
      - OCCP_DATABASE_URL=postgresql+asyncpg://occp:${OCCP_PG_PASSWORD}@db:5432/occp
    depends_on:
      db:
        condition: service_healthy
```

### d) `store/engine.py` Pool Tuning

```python
_PG_POOL_SIZE = 5       # Keep — matches uvicorn workers
_PG_MAX_OVERFLOW = 5    # Change from 10 to 5 — total max 10 connections
```

Add to `_create_pg_engine()`:

```python
pool_timeout=10,
pool_recycle=1800,
connect_args={
    "prepared_statement_cache_size": 64,
    "statement_cache_size": 64,
},
```

**PgBouncer verdict**: SKIP. Single FastAPI service, `max_connections=50`, native pooling sufficient.

### e) Data Migration Script: `scripts/migrate_sqlite_to_pg.py`

- Read from SQLite via ORM (FK order: `AgentConfigRow` → `UserRow` → `TaskRow` → `AuditEntryRow`)
- Batch insert 1000 rows/commit
- Post-migration: row count comparison + audit hash chain verification
- FELT: Current production data < 10k rows → migration under 5 seconds

### f) Zero-Downtime Cutover Sequence

1. Add `db` service to docker-compose, `docker compose up -d db`
2. Alembic against PG: `alembic -x sqlalchemy.url=postgresql+asyncpg://... upgrade head`
3. Brief maintenance window: run `migrate_sqlite_to_pg.py`
4. Switch `OCCP_DATABASE_URL` in `.env` to PG
5. `docker compose up -d api` (restart with new DB)
6. Verify: health check + row counts + audit chain integrity
7. Keep SQLite volume as backup for 7 days

### g) Backup Strategy

- `pg_dump` via cron (daily 03:00 UTC, 7-day rotation)
- Before-migration SQLite snapshot
- Script: `scripts/backup-pg.sh`

### Acceptance Criteria

- [ ] Alembic migrations pass on fresh PG 16
- [ ] All 313 tests pass with `asyncpg` backend
- [ ] Production reads/writes from PG
- [ ] Audit hash chain intact after migration
- [ ] Response times ≤ current SQLite baseline

### Rollback Trigger

Error rate >1% OR p95 latency >500ms OR audit chain invalid → revert `DATABASE_URL` to SQLite, restart API.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lock timeout during migration | Low (small DB) | Med | Retry 3x with exponential backoff |
| asyncpg incompatibility | Low (already in engine.py) | High | Full test suite on PG before deploy |
| Data corruption during transfer | Very Low | Critical | Row count + hash chain verification |

---

## B2 — SANDBOX HARDENING [P0 — security critical]

**Effort**: M (2-3 days) | **Dependencies**: B7 (parallel with B1)

### Verified Kernel State (from Phase A6)

| Capability | Value | Status |
|-----------|-------|--------|
| `unprivileged_userns_clone` | 1 | **READY** |
| `CONFIG_USER_NS` | y | **READY** |
| `user.max_user_namespaces` | 62311 | **READY** |
| Kernel | 6.8.0-90-generic | **READY** |
| Cgroup | cgroup2fs | **READY** |
| AppArmor | loaded (120 profiles) | **CAUTION** — may need `apparmor=unconfined` |
| `unshare --user` test | `userns_works` | **READY** |
| nsjail/bwrap | not installed | **ACTION REQUIRED** |

**Conclusion**: Kernel fully supports namespace isolation. Only binary installation needed.

### a) Kernel Verification Script: `scripts/verify_sandbox_kernel.sh`

Output JSON capability report checking all kernel prerequisites.

### b) Installation Priority

| Priority | Method | Isolation Level | Install Complexity |
|----------|--------|----------------|-------------------|
| 1 (immediate) | `apt install bubblewrap` | Namespace isolation (PID, MNT, NET) + rlimits | Zero deps |
| 2 (next sprint) | Build nsjail from source (multi-stage Docker) | Full: namespaces + cgroups + seccomp | Build deps required |
| 3 (future) | gVisor `runsc` (systrap mode, no KVM) | Kernel-level syscall interception | apt install |

### c) Docker Compose Sandbox Service Config

For nsjail (Tier 2):

```yaml
services:
  api:
    cap_add:
      - SYS_ADMIN
      - SETUID
      - SETGID
    security_opt:
      - seccomp=/etc/docker/nsjail-seccomp.json
      - apparmor=unconfined
    sysctls:
      - kernel.unprivileged_userns_clone=1
```

**NEVER use `--privileged` in production.**

### d) Seccomp Profile: `config/nsjail-seccomp.json`

Allow: `clone, clone3, unshare, setns, mount, umount2, pivot_root, setuid, setgid, setgroups, prctl, seccomp, mknod, mknodat`

Block: `kexec_load, reboot, swapon, swapoff, personality`

### e) Resource Limit Defaults

| Resource | Current | Proposed | Justification |
|----------|---------|----------|---------------|
| Memory | 256 MB | 512 MB | Sufficient for Python + pip install |
| PIDs | 32 | 100 | Prevents fork bomb, allows multiprocessing |
| Time | 30s | 30s default, 300s max | Configurable per agent type |
| Network | disabled | disabled default | Opt-in via policy gate only |
| Max FDs | 64 | 64 | Sufficient for most workloads |

### f) Dockerfile.api Update

```dockerfile
FROM ubuntu:22.04 AS nsjail-builder
RUN apt-get update && apt-get install -y \
    autoconf bison flex gcc g++ git libprotobuf-dev \
    libnl-route-3-dev libtool make pkg-config protobuf-compiler
RUN git clone --depth=1 https://github.com/google/nsjail.git /nsjail \
    && cd /nsjail && make && mv /nsjail/nsjail /usr/local/bin/nsjail

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap && rm -rf /var/lib/apt/lists/*
COPY --from=nsjail-builder /usr/local/bin/nsjail /usr/local/bin/nsjail
```

### g) Integration Test Plan

| Test | Method | Expected |
|------|--------|----------|
| Host FS isolation | Read `/etc/shadow` from sandbox | Permission denied |
| Network isolation | `curl` external host | Connection refused |
| Memory limit | Allocate > limit | OOM kill (exit 137) |
| Time limit | `sleep 999` | SIGKILL after timeout |
| PID limit | Fork bomb | Fork fails beyond limit |

### Fallback Chain

```
nsjail (full isolation) → bwrap (namespace isolation) → process (rlimits only)
```

Auto-detection in `detect_backend()` already implemented. No code changes needed for fallback logic.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AppArmor blocks namespace creation | Medium | Medium | `apparmor=unconfined` in compose |
| nsjail build fails on newer protobuf | Low | Low | Pin protobuf version; bwrap as fallback |

---

## B3 — MULTI-TENANCY FOUNDATION [P1]

**Effort**: L (5-7 days) | **Dependencies**: B1 (PostgreSQL required for FK constraints)

### a) New Tables (Alembic Migration)

```python
class OrganizationRow(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    plan: Mapped[str] = mapped_column(String(32), default="free")
    settings: Mapped[dict] = mapped_column(JSONBText(), default=dict)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
```

Add `org_id` FK (nullable initially) to: `users`, `tasks`, `agent_configs`, `audit_entries`.

### b) Casbin Domain Model Upgrade

Current: `g = _, _` (user, role). Target:

```ini
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _    # user, role, org_id

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && r.obj == p.obj && r.act == p.act
```

Libraries: `pycasbin>=1.36.0`, `casbin-sqlalchemy-adapter>=1.0.0`.

### c) Query Scoping: `OrgBoundMixin`

```python
class OrgBoundMixin:
    org_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id"), index=True)
```

Repository pattern with explicit `org_id` filter. `system_admin` bypasses scope.

### d) API Changes

- JWT claim: add `org_id`
- `X-Org-Id` header for org switching (`system_admin` only)
- All list endpoints filter by `org_id`
- Dashboard URL: `/dashboard/{org_slug}/...`

### e) Data Leak Mitigation

- Middleware validates `org_id` on EVERY query
- Cache keys include `org_id`
- Audit log includes `org_id`
- Future: PG Row-Level Security (RLS)

### Acceptance Criteria

- [ ] Organization CRUD endpoints work
- [ ] Users belong to org, JWT contains org_id
- [ ] Task queries scoped to org_id
- [ ] system_admin can cross-org
- [ ] Audit log includes org_id

---

## B4 — API KEY MANAGEMENT [P1]

**Effort**: M (2-3 days) | **Dependencies**: B1 (PG for proper indexing)

### a) ApiKeyRow Table

```python
class ApiKeyRow(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    org_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    scopes: Mapped[dict] = mapped_column(JSONBText(), default=dict)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    rate_limit_per_day: Mapped[int] = mapped_column(Integer, default=10000)
    last_used_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
```

### b) Key Format (Stripe-style)

- `sk_live_a1B2c3D4...` — production
- `sk_test_x9Y8w7V6...` — sandbox

Storage: SHA-256 hash only. Prefix stored plain for O(1) lookup. Full key shown ONCE at creation.

### c) Auth Flow

```
Bearer token starts with "sk_" → API key path
  → Extract prefix (first 16 chars)
  → DB lookup by prefix (indexed)
  → SHA-256 verify (secrets.compare_digest)
  → Load user + role + org_id
  → Update last_used_at
```

### d) Key Rotation

Create new → old key gets 72h grace period → auto-expires.

### e) Rate Limiting

Per API key, separate from user session limits. Phase 1: in-memory (existing `RateLimitMiddleware` pattern). Phase 2: Redis.

### Acceptance Criteria

- [ ] `POST /api/v1/keys` creates key, returns full key once
- [ ] `GET /api/v1/keys` lists keys (prefix only)
- [ ] `DELETE /api/v1/keys/{id}` revokes immediately
- [ ] `POST /api/v1/keys/{id}/rotate` creates new + grace period
- [ ] API key auth works for all endpoints

---

## B5 — OBSERVABILITY [P1]

**Effort**: M (2-3 days) | **Dependencies**: None (parallel)

### a) Prometheus Metrics: `GET /api/v1/metrics`

Library: `prometheus-fastapi-instrumentator==7.1.0`

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics")
```

Custom business metrics:

| Metric | Type | Labels |
|--------|------|--------|
| `occp_sandbox_execution_seconds` | Histogram | `backend`, `language`, `org_id` |
| `occp_sandbox_oom_total` | Counter | `org_id` |
| `occp_sandbox_timeout_total` | Counter | `org_id` |
| `occp_audit_chain_length` | Gauge | — |
| `occp_api_key_requests_total` | Counter | `org_id`, `key_prefix` |

Cardinality rule: No `task_id` or `user_id` in labels. Only bounded dimensions.

### b) Observability Stack (docker-compose.observability.yml)

| Service | Image | RAM | Purpose |
|---------|-------|-----|---------|
| Prometheus | `prom/prometheus:latest` | ~200 MB | Metrics (15s interval, 15d retention) |
| Loki | `grafana/loki:latest` | ~100 MB | Log aggregation |
| Promtail | `grafana/promtail:latest` | ~30 MB | Log shipping |
| Grafana | `grafana/grafana:latest` | ~100 MB | Dashboards |
| Alertmanager | `prom/alertmanager:latest` | ~30 MB | Alert routing |
| **Total** | | **~460 MB** | Fits on 4GB VPS |

### c) Alert Rules

| Alert | Expression | For | Severity |
|-------|-----------|-----|----------|
| ServiceDown | `up{job="fastapi"} == 0` | 1m | critical |
| HighErrorRate | 5xx rate > 5% | 3m | critical |
| HighLatency | p95 > 2s | 5m | critical |
| DiskSpaceLow | avail < 20% | 10m | warning |
| SandboxOOMSpike | OOM increase > 10/15m | 0m | warning |
| AuditChainInvalid | chain_valid == 0 | 0m | critical |

### d) Structured Logging → Loki

Add per-request context via `structlog.contextvars`:

```python
structlog.contextvars.bind_contextvars(
    request_id=request_id,
    method=request.method,
    path=request.url.path,
    org_id=getattr(request.state, "current_org_id", None),
    user_id=getattr(request.state, "user_id", None),
)
```

### e) Grafana Dashboards

Import: **16110** (FastAPI), **1860** (Node Exporter), **13639** (Loki Logs).

### Acceptance Criteria

- [ ] `GET /api/v1/metrics` returns Prometheus text format
- [ ] Custom sandbox metrics populated
- [ ] Grafana accessible with dashboards
- [ ] Alerts fire correctly on simulated conditions

---

## B6 — DASHBOARD RBAC GATING [P2]

**Effort**: M (2-3 days) | **Dependencies**: B3 (org model)

### a) `GET /api/v1/auth/me` Enhancement

```json
{
  "id": "...",
  "username": "admin",
  "role": "admin",
  "org_id": "org_123",
  "permissions": ["task:read", "task:create", "agent:read", "agent:manage", "policy:read", "audit:read"]
}
```

### b) Page Visibility Matrix

| Page | viewer | operator | admin | system_admin |
|------|--------|----------|-------|-------------|
| /agents (list) | read | read | full | full |
| /agents (register/delete) | - | - | full | full |
| /policy (view) | read | read | read | read |
| /policy (edit) | - | - | full | full |
| /audit | read | read | read | read |
| /users | - | - | - | full |
| /settings (org) | - | - | full | full |

### c) WebSocket Auth

`/ws/pipeline/{task_id}`: Require auth token in first message. Validate `task:read` + task belongs to user's org.

### Acceptance Criteria

- [ ] Viewer cannot see register/delete agent buttons
- [ ] Viewer cannot access /users page
- [ ] Operator cannot edit policies
- [ ] All pages respect org_id scope

---

## Dependency Graph

```
B7 (housekeeping + RBAC wiring + register endpoint) ────────────→ DONE
  │
  ├── B1 (PostgreSQL) ──┬── B3 (multi-tenancy) ──── B6 (dashboard RBAC)
  │                     └── B4 (API keys)
  │
  └── B2 (sandbox) ─────────────────────────────────────────────→ DONE
      │
      └── B5 (observability) ───────────────────────────────────→ DONE
```

Parallel tracks: B1+B2 simultaneously. B5 anytime.

## Recommended Execution Order

| Phase | Section | Effort | Depends On | Calendar Days |
|-------|---------|--------|------------|---------------|
| 1 | B7 — Housekeeping + RBAC wiring | S+M | — | Days 1-2 |
| 2a | B1 — PostgreSQL cutover | L | B7 | Days 3-5 |
| 2b | B2 — Sandbox hardening | M | B7 | Days 3-4 (parallel) |
| 3 | B5 — Observability | M | — | Days 5-6 |
| 4 | B4 — API key management | M | B1 | Days 6-7 |
| 5 | B3 — Multi-tenancy | L | B1 | Days 7-12 |
| 6 | B6 — Dashboard RBAC | M | B3 | Days 12-14 |
| **Total** | | | | **~14 working days** |

---

## 2026 Competitive Landscape

| Competitor | Key Strength | OCCP Differentiator |
|------------|-------------|---------------------|
| **EV** (eevee.build) | K8s-native, declarative YAML governance, MIT | 5-stage Verified Autonomy Pipeline, hash-chain audit |
| **Gravitee 4.10** | Unified AI Gateway + MCP proxy + agentic IAM | Multi-LLM failover, policy-as-code |
| **Cordum** | Policy enforcement + human approval gates | Sandbox isolation, open-core model |

### Top 3 Features OCCP Lacks vs Competitors

1. **Multi-tenant governance** — EV and Gravitee both have org-scoped policies (B3 addresses)
2. **API key management** — Gravitee has full API key lifecycle (B4 addresses)
3. **Observability** — All competitors have built-in metrics/tracing (B5 addresses)
