---
name: deployment-verification
description: Run post-deployment health checks and smoke tests to verify production is stable
user-invocable: true
---

## Verification Checklist

Run all checks sequentially. First failure triggers rollback consideration.

**1. Service health:**
```bash
# All containers running
docker compose ps --status running

# Health endpoint responds
curl -sf https://api.domain.com/health | jq .status  # expected: "ok"
curl -sf https://dash.domain.com/                     # expected: 200
```

**2. SSL and DNS:**
```bash
# Certificate valid and not expiring soon
echo | openssl s_client -connect domain.com:443 2>/dev/null | openssl x509 -noout -dates

# DNS resolves to expected IP
dig +short domain.com  # must match server IP
```

**3. Application smoke tests:**
- Authentication flow: POST `/api/v1/auth/login` → 200 with token
- Core read endpoint: GET `/api/v1/health` → `{"status":"ok","version":"x.y.z"}`
- Dashboard loads: Playwright screenshot of `/dashboard` (no error page)

**4. Database connectivity:**
- Run: `SELECT 1` via app health endpoint DB check
- Verify migration version matches deployed code: `alembic current`

**5. Version alignment:**
- API version header matches deployed tag
- Dashboard reports same version as API

## Rollback Triggers (auto-suggest to human)
- Any health endpoint returns 5xx
- SSL certificate expired or chain broken
- DB connection fails
- Version mismatch between API and Dashboard

## Output Format
```json
{
  "deployment_status": "PASS|FAIL",
  "checks": { "containers": "OK", "ssl": "OK", "dns": "OK", "api_health": "OK", "db": "OK", "version": "0.9.0" },
  "rollback_recommended": false,
  "timestamp": "2026-03-26T14:00:00Z"
}
```

## Quality Criteria
- All 5 check categories must PASS for deployment to be marked SUCCESS
- FAIL on any check → immediately notify operator, do not auto-proceed
