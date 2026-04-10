---
name: pytest-generate
description: Generate comprehensive pytest test suites with fixtures, mocks, and coverage targets
user-invocable: true
---

## Test Generation Protocol

**Framework:** pytest 8+, pytest-asyncio, pytest-cov, httpx (for FastAPI), factory-boy

**For each function/endpoint under test, generate:**
1. Happy-path test (valid input → expected output)
2. Edge case tests (boundary values, empty inputs, max limits)
3. Error path tests (invalid input → correct HTTP code / exception)
4. Auth tests (unauthenticated → 401, unauthorized → 403)
5. Integration test if DB or external service is involved

## Test Structure
```python
class TestResourceCreate:
    async def test_creates_resource_with_valid_payload(self, client, auth_headers, db):
        ...
    async def test_returns_422_on_missing_required_field(self, client, auth_headers):
        ...
    async def test_returns_401_without_auth(self, client):
        ...
    async def test_returns_403_for_insufficient_role(self, client, limited_auth_headers):
        ...
```

**Fixture rules:**
- Database fixtures: use transactions + rollback (never commit to test DB)
- External APIs: always mock with `respx` or `pytest-mock`
- Auth: provide `auth_headers` fixture at conftest level

## Output Expectations
- Minimum coverage target: 85% for new code, 100% for security-critical paths
- All async endpoints tested with `pytest-asyncio` and `anyio`
- Factory classes for all models in `tests/factories/`

## Quality Criteria
- Tests run in isolation (no shared state between test functions)
- No `time.sleep()` — use `freezegun` for time-dependent logic
- Test names are self-documenting (no comments needed to understand intent)
