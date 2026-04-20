# OCCP Python Modernization 2026

**Dátum:** 2026-04-20 · FastAPI 0.115 + SQLA 2.0 + aiosqlite + Pydantic 2.10 + Py 3.13 + uv → 2026 best practice

---

## §1 OCCP stack vs 2026 state

| Layer | Current | 2026 best | Gap | Priority |
|---|---|---|---|---|
| Framework | FastAPI 0.115 | FastAPI 0.116 OR Litestar 2.13 | Litestar 2x perf | MEDIUM |
| Validation | Pydantic 2.10 | Pydantic 2.14 (v3 ~2026-H2) | Minor bump | LOW |
| ORM | SQLA 2.0 + aiosqlite | SQLA 2.1 + asyncpg/psycopg3 | SQLite bottleneck | **HIGH** |
| Type check | mypy | pyrefly/ty (Rust, 10-20× faster) | Dev loop slow | MEDIUM |
| Lint | ruff | ruff 0.15.11 unified | OK | LOW |
| Pkg mgmt | uv | uv 0.11.7 workspace | Monorepo nem kihasználva | MEDIUM |
| Test | pytest + asyncio | pytest 9 + hypothesis + mutmut | No property/mutation | MEDIUM |
| Container | FELT slim | uv distroless multi-stage | Méret ismeretlen | **HIGH** |
| Logging | stdlib/structlog | structlog + OTel bridge | OTel integráció | MEDIUM |
| Concurrency | asyncio.gather | TaskGroup + anyio | Unstructured cancel | **HIGH** |

**Verdikt:** OCCP stack szilárd, 6-9 hónap lemaradás. Nagy nyerés: Postgres + structured concurrency + distroless.

---

## §2 FastAPI → Litestar migration

**FastAPI 0.116** (2026-Q1): `fastapi deploy` CLI, Starlette 0.47 pathsend ASGI. Minor release, no breaking.

**Litestar 2.13** — msgspec (nem Pydantic) → **2x throughput** TechEmpower 2026. DI pytest-inspired (tisztább mint FastAPI `Depends`).

**OCCP cost (103 endpoint):**
- Route rewrite: 3-5 nap (type hints transferable, `Depends` → `Provide`)
- msgspec.Struct vs pydantic.BaseModel: partial — Pydantic marad LLM tool schema-hoz
- OpenAPI native, kompatibilis
- **BLOCKER:** `TestClient` lifespan → Litestar equivalent, rewrite ~1 nap

**Benefit:** 2× RPS, alacsonyabb p99, tisztább typing.

**Verdikt: NEM URGENT.** Agent backend LLM-bound, nem framework-bound. **Revisit 2026-Q4.**

**Alternatívák:**
- **Robyn 0.72** (Rust runtime, 5× faster) — kis ecosystem, no OpenAPI parity. ❌
- **BlackSheep 2.6.2** — Neoteroi-only maintenance risk. ❌

---

## §3 Pydantic v2 → v3

- **v3 release FELT:** 2026-Q3/Q4
- Breaking: `pydantic.v1` shim remove, deprecated helpers remove
- **Migration trivial** (unlike v1→v2)
- **OCCP action:** bump 2.14 most, `python -W error::DeprecationWarning -m pytest` → future-incompat surface

---

## §4 SQLite → Postgres (Supabase)

**SQLAlchemy 2.1.0b2** (2026-04-16): greenlet NOT default, `sqlalchemy[asyncio]` extra.

**Driver:**
- **asyncpg** — leggyorsabb raw
- **psycopg3** — unified sync/async, 2026 default

**Supabase CRITICAL gotcha:** pooler port 6543 = PgBouncer transaction mode **breaks asyncpg prepared statements**. Use port **5432 direct** OR `statement_cache_size=0`.

**Alembic 1.18.4** stable — async: `alembic init -t async`.

**OCCP plan:**
1. `aiosqlite` → `asyncpg` (URL: `postgresql+asyncpg://...`)
2. Connection pool lifespan-ban (nem per-request)
3. `alembic init -t async migrations` + baseline SQLite schema
4. SQLite-specifikus SQL port (`INSERT OR REPLACE` → `ON CONFLICT`)
5. testcontainers-python Postgres fixture

---

## §5 Typing progressive strict

**Benchmark 2026-04 (53 OSS package):**

| Tool | Pandas check | Conformance |
|---|---|---|
| mypy 1.19.1 | 30-60s | 57% |
| pyright 1.1.408 | 144s | ~60% |
| **pyrefly 0.60** (Meta Rust) | **1.9s** | 58% |
| **ty 0.0.29** (Astral Rust) | **1.5s** | 15% (early) |

**OCCP:** mypy CI-ben + **pyrefly dev-loop** (pre-commit). `ty` nem ready (15%).

**Agent-specifikus type:**
- `Protocol` — adapter interface (duck typing)
- `TypedDict` — LLM tool_use JSON schema
- `ParamSpec` — decorator-wrapped agent call (signature preserve)
- `assert_type()` — compile-time sanity
- `Self` — builder pattern

**Progressive plan (12 hét):**
- W1-2: mypy CI, no-strict baseline
- W3-4: strict for `api/`
- W5-8: strict for `adapters/`, `security/`
- W9-12: strict for `orchestrator/` (utolsó, complex)

---

## §6 Container size + cold start

**Target: <100MB FastAPI + asyncpg + deps**

Stack: `astral-sh/uv:0.11.7-python3.13-bookworm-slim` (builder) → `distroless/cc-debian12` (runtime)

**Multi-stage minta:**
```dockerfile
FROM ghcr.io/astral-sh/uv:0.11.7-python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY uv.lock pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

FROM gcr.io/distroless/cc-debian12
COPY --from=builder /app /app
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
WORKDIR /app
ENTRYPOINT ["/app/.venv/bin/python", "-m", "uvicorn", "occp.main:app", "--host", "0.0.0.0"]
```

**Méret (FELT):** ~85MB (distroless cc 24MB + Python 35MB + deps 25MB)
**Cold start:** `UV_COMPILE_BYTECODE=1` → pre-compile .pyc → -30-40% first-import

---

## §7 Testing modernization

**Stack:**
- **pytest 9.0** (FELT 2026-Q1) — native async mocks; current stable 8.x
- **pytest-asyncio 0.26+** — `asyncio_mode = "auto"` → `@pytest.mark.asyncio` boilerplate remove
- **hypothesis 6.152.1** (2026-04) — property-based `security/` validators
- **mutmut** — mutation testing; 70%→92% fault detection paired with hypothesis
- **testcontainers-python** — real Postgres fixture

**OCCP 30K LoC actions:**
1. 10 critical `security/` fn → hypothesis strategies
2. `mutmut run` on `adapters/` → kill surviving mutants
3. `TestClient` → `httpx.AsyncClient` + `asgi_lifespan.LifespanManager`
4. Target: 95% line coverage + 85% mutation score

**TestClient lifespan gotcha:** Must `with TestClient(app) as c:` — else lifespan doesn't run.

---

## §8 CI/CD GitHub Actions (full draft)

```yaml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { version: "0.11.7", enable-cache: true }
      - run: uv sync --locked --all-extras --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .

  typecheck:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --locked --dev
      - run: uv run mypy src/
      - run: uv run pyrefly check src/

  test:
    runs-on: ubuntu-24.04
    strategy:
      matrix:
        python: ["3.12", "3.13", "3.14"]
    services:
      postgres:
        image: postgres:17
        env: { POSTGRES_PASSWORD: test }
        ports: [5432:5432]
        options: --health-cmd pg_isready
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { python-version: ${{ matrix.python }}, enable-cache: true }
      - run: uv sync --locked --all-extras --dev
      - run: uv run pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v5

  security:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
      - uses: github/codeql-action/init@v3
        with: { languages: python }
      - uses: github/codeql-action/analyze@v3

  docker:
    needs: [lint, typecheck, test]
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          platforms: linux/amd64,linux/arm64
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## §9 10 konkrét 1-hour refactor (small wins)

1. `UV_COMPILE_BYTECODE=1` Dockerfile → faster cold start (5 min)
2. `asyncio.gather` → `asyncio.TaskGroup` (Py 3.11+) orchestrator.py → structured cancellation (30 min)
3. `TestClient(app)` → `with TestClient(app) as c:` → real lifespan (20 min sed)
4. `asyncio_mode = "auto"` pyproject → remove `@pytest.mark.asyncio` boilerplate (15 min)
5. Pin `ruff 0.15.11` + `ruff-lsp` pre-commit (10 min)
6. `UV_LINK_MODE=copy` Docker builder → fix hard-link mount issues (2 min)
7. `dict[str, Any]` agent config → TypedDict → mypy catches (45 min)
8. `asgi-lifespan.LifespanManager` async HTTPX test → no unclosed-client warning (30 min)
9. Enable `strict = true` `src/occp/security/` mypy.ini (progressive) — 10-20 bug surface (1h fix)
10. structlog `JSONRenderer` prod / `ConsoleRenderer` dev via `LOG_FORMAT` env (15 min)

---

## §10 Anti-patterns 2026

1. `requirements.txt` + `pip freeze` → use `uv.lock`
2. Monkey-patching tests → `pytest.MonkeyPatch` fixture
3. `global` pool objects → lifespan + `request.state.db` / DI
4. `asyncio.create_task` TaskGroup nélkül → orphaned silent exceptions
5. `Depends(get_db)` per-request sync SQLA → blocks event loop
6. Pydantic hot-path serialization → msgspec 10-20× gyorsabb
7. `from X import *` agent kódban → mypy/ruff F405 break
8. `print()` prod → structlog + OTel
9. `time.sleep()` async → always `await asyncio.sleep()`
10. Single Dockerfile (no multi-stage) → image bloat
11. `aiosqlite` prod multi-writer → **global write lock**, Postgres-or-bust
12. Mutable default args Pydantic → `Field(default_factory=list)`
13. Sync blocking libs (requests, psycopg2) async handlerben `run_in_executor` nélkül → thread-pool saturation

---

## Források (access 2026-04-20)

- [FastAPI releases](https://github.com/fastapi/fastapi/releases) 83k★
- [Litestar GitHub](https://github.com/litestar-org/litestar) ~6k★
- [Litestar vs FastAPI migration](https://docs.litestar.dev/main/migration/fastapi.html)
- [byteiota Litestar speed 2026](https://byteiota.com/litestar-vs-fastapi-python-speed-test-2026-analysis/)
- [Robyn GitHub](https://github.com/sparckles/Robyn)
- [BlackSheep GitHub](https://github.com/Neoteroi/BlackSheep)
- [Pydantic v3 issue](https://github.com/pydantic/pydantic/issues/10033)
- [SQLAlchemy 2.1 asyncio](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html)
- [Supabase asyncpg fix](https://github.com/supabase/supabase/issues/39227)
- [uv GitHub](https://github.com/astral-sh/uv) 40k+★ v0.11.7
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)
- [uv-docker-example](https://github.com/astral-sh/uv-docker-example)
- [Josh Kasuboski distroless](https://www.joshkasuboski.com/posts/distroless-python-uv/)
- [Ruff GitHub](https://github.com/astral-sh/ruff) 40k+★
- [Pyrefly speed comparison](https://pyrefly.org/blog/speed-and-memory-comparison/)
- [pyrefly vs ty](https://blog.edward-li.com/tech/comparing-pyrefly-vs-ty/)
- [ty (Astral)](https://astral.sh/blog/ty)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [hypothesis](https://github.com/HypothesisWorks/hypothesis) v6.152.1
- [mutmut 2026 guide](https://johal.in/mutation-testing-with-mutmut-python-for-code-reliability-2026/)
- [AnyIO](https://anyio.readthedocs.io/) v4.13.0
- [msgspec benchmarks](https://jcristharif.com/msgspec/benchmarks.html)
- [setup-uv action](https://github.com/astral-sh/setup-uv)
- [structlog FastAPI](https://wazaari.dev/blog/fastapi-structlog-integration)

---
*v1.0 · 2026-04-20 · deep-research agent output*
