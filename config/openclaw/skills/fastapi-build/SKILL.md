---
name: fastapi-build
description: Build production-ready FastAPI endpoints with Pydantic models, auth, and tests
user-invocable: true
---

## Implementation Standards

**Stack:** FastAPI 0.115+, Pydantic v2, Python 3.11+, SQLAlchemy 2.x async, Alembic

**Every endpoint must include:**
- Pydantic request/response models with field validators
- Dependency injection for DB session and current user
- `current_user_can()` equivalent: role/permission check before business logic
- HTTP exception handling with typed error responses
- Docstring with description, parameters, and response codes

## Code Structure
```python
@router.post("/api/v1/{resource}", response_model=ResourceResponse, status_code=201)
async def create_resource(
    payload: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> ResourceResponse:
    ...
```

**Security requirements:**
- All write endpoints: verify HMAC or JWT signature
- All endpoints: rate limit via middleware
- Never expose internal IDs directly — use UUIDs
- Log all write operations to audit trail

## Output Expectations
- Fully working endpoint code (no TODOs, no placeholder logic)
- Corresponding Pydantic models in `schemas/`
- Route registered in router `__init__`
- At minimum 1 happy-path and 1 error-path test in `tests/`

## Quality Criteria
- PHPStan equivalent: mypy strict mode passes
- No raw SQL — use SQLAlchemy ORM or `$db->prepare()` equivalent
- Response time target: p99 < 200ms for CRUD ops
