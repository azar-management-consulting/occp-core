# OCCP Production Smoke Tests

Validates every live OCCP surface end-to-end.  Run nightly in CI and on
every release.  Zero mocking in live mode — real HTTP against real prod.

## Run locally

```bash
pip install pytest httpx          # minimum deps
pytest tests/smoke --smoke -v     # hit real prod
```

Offline/mock mode (no network):

```bash
pip install pytest httpx respx
OCCP_SMOKE_MODE=offline pytest tests/smoke --smoke -v
```

## Override target (staging / preview)

```bash
OCCP_SMOKE_TARGET_BASE=https://api-staging.occp.ai \
OCCP_SMOKE_DASH_BASE=https://dash-staging.occp.ai \
pytest tests/smoke --smoke -v
```

## Test inventory (6 tests)

| Test | What it checks |
|------|---------------|
| `test_status_endpoint_healthy` | 200, JSON schema, platform/status/environment/version |
| `test_swagger_live` | /docs 200 + Swagger UI body |
| `test_dash_live` | dash.occp.ai 200 + OCCP/login content |
| `test_landing_live` | occp.ai 200 |
| `test_api_response_under_1s` | SLO: wall-clock < 1 s |
| `test_api_security_headers` | x-content-type-options + HSTS present |
| `test_dash_csp_header` | CSP present, connect-src includes api.occp.ai |

## Extending

Add a new `@pytest.mark.smoke` function to `test_prod_surfaces.py`.
Use `_client()` for the httpx transport (handles offline mode automatically).

## When a test fails in CI

1. Check the GitHub Issue auto-created with label `production-incident`.
2. Reproduce locally with `--smoke -v -s` to see full response bodies.
3. Confirm the endpoint directly with `curl -I <url>`.
4. Page on-call if `test_status_endpoint_healthy` or `test_api_response_under_1s` fails.
