# OCCP v0.5.0 FORENSIC AUDIT REPORT

**Date:** 2026-02-23 | **Commit:** `d97273f` | **Auditor:** Claude Opus 4.6

---

## VERDICT TABLE

| Category | Result | Details |
|----------|--------|---------|
| **TECH** (code/build/test/prod) | **PASS** | 145 tests pass, build OK, prod v0.5.0 confirmed |
| **DEPLOY** | **PASS** | GH Actions run #22288104108 success, containers healthy |
| **SECURITY** | **CONDITIONAL PASS** | Docker hardening full, Anthropic billing fail (non-security) |
| **GOVERNANCE** | **FAIL** | `enforce_admins: false` allows required check bypass |

**Overall: 3/4 PASS, 1 GOVERNANCE FAIL**

---

## A) REPO INTEGRITY

```
$ git rev-parse HEAD
d97273feddedfb6c1528aa72d95051a913f92a43

$ git rev-parse origin/main
d97273feddedfb6c1528aa72d95051a913f92a43
```
HEAD = origin/main: **MATCH**

### Version Consistency (0.5.0)
| File | Version | Status |
|------|---------|--------|
| `pyproject.toml:7` | 0.5.0 | PASS |
| `api/routes/status.py:16` | 0.5.0 | PASS |
| `cli/__init__.py:3` | 0.5.0 | PASS |
| `dash/package.json:3` | 0.5.0 | PASS |
| `sdk/python/__init__.py:3` | 0.5.0 | PASS |
| `sdk/typescript/package.json:3` | 0.5.0 | PASS |
| `README.md` badge | 0.5.0 | PASS |
| `CHANGELOG.md` | 0.5.0 | PASS |

Untracked (non-critical): `OCCP_STATUS_REPORT.md`, `dash/next-env.d.ts`, `sdk/typescript/package-lock.json`

---

## B) BUILD/TEST GATE

### Python Tests
```
$ .venv/bin/pytest -q
145 passed, 12 warnings in 3.33s
```
Warnings: InsecureKeyLengthWarning (test fixtures only, not production). **PASS**

### Dashboard Build
```
$ npm run build
Compiled successfully in 2.4s
7 routes: /, /agents, /audit, /login, /pipeline, /policy, /_not-found
11/11 static pages generated
```
**PASS**

---

## C) PRODUCTION VERIFY

### API Status
```
$ curl -s https://api.occp.ai/api/v1/status
{"platform":"OCCP","version":"0.5.0","status":"running","tasks_count":2,"audit_entries":1}
```
No-cache identical. **PASS**

### Dashboard Routes
```
$ curl -I https://dash.occp.ai/login
HTTP/1.1 200 OK

$ curl -I https://dash.occp.ai/agents
HTTP/1.1 200 OK
```
Security headers present: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`. **PASS**

---

## D) GITHUB ACTIONS / DEPLOY

### Last 3 Runs
| Run ID | Workflow | Status | Commit |
|--------|----------|--------|--------|
| 22288104108 | Deploy | success | d97273f (retro redesign) |
| 22288104105 | CI | success | d97273f |
| 22288104102 | Secret Scanning | success | d97273f |

### Deploy Log Evidence
```
Container occp-api-1 Healthy
Container occp-dash-1 Started
{"platform":"OCCP","version":"0.5.0","status":"running"...}
Deploy OK: Sun Feb 22 11:55:39 PM UTC 2026
Successfully executed commands to all hosts.
```
**PASS**

### GOVERNANCE: Branch Protection Bypass
```
$ gh api .../branches/main/protection
"enforce_admins": {"enabled": false}
"required_status_checks": {"contexts": ["test"]}
```
Push output recorded: `"Bypassed rule violations for refs/heads/main: Required status check 'test' is expected."`

**FAIL** — Admin users can bypass required `test` status check.

**FIX:** Enable `enforce_admins` via GitHub Settings > Branches > main > "Include administrators" checkbox, or:
```
gh api -X PATCH repos/azar-management-consulting/occp-core/branches/main/protection/enforce_admins \
  -f enabled=true
```

---

## E) DOCKER HARDENING

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Non-root user | uid!=0 | `uid=1001(occp)` | PASS |
| read_only rootfs (API) | true | `true` | PASS |
| read_only rootfs (Dash) | true | `true` | PASS |
| no-new-privileges | true | `["no-new-privileges:true"]` | PASS |
| tmpfs /tmp | present | `{"/tmp":""}` | PASS |
| Port 8000 bind | 127.0.0.1 | `127.0.0.1:8000` | PASS |
| Port 3000 bind | 127.0.0.1 | `127.0.0.1:3000` | PASS |
| Volume ownership | occp:1001 | `drwxr-xr-x occp occp /app/data` | PASS |
| Container health | healthy | Both `Up 32 min (healthy)` | PASS |

### Volume Ownership Fix — Reproducible
```yaml
# .github/workflows/deploy.yml line 38-39
# Fix volume ownership for non-root container user (occp:1001)
docker run --rm -v occp_occp-data:/data alpine chown -R 1001:1001 /data
```
Runs on every deploy before `docker compose up`. **PASS**

---

## F) ANTHROPIC API

### Key Present
```
$ docker exec occp-api-1 sh -c 'echo $OCCP_ANTHROPIC_API_KEY | head -c 20'
sk-ant-api03-FIO7fPA
```
Key format valid (`sk-ant-api03-*`). **PASS**

### Smoke Test
```
HTTP 400: {"type":"error","error":{"type":"invalid_request_error",
"message":"Your credit balance is too low to access the Anthropic API.
Please go to Plans & Billing to upgrade or purchase credits."},
"request_id":"req_011CYQ4BEuTaXRc9keQHuagU"}
```
**BILLING FAIL** — Key valid but account has insufficient credits.

**FIX:** Purchase API credits at https://console.anthropic.com/settings/billing (NOT claude.ai subscription — these are separate billing systems).

---

## OPEN ITEMS

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | **HIGH** | Governance: `enforce_admins=false` allows bypassing required checks | Enable via GH branch protection settings |
| 2 | **HIGH** | Anthropic API billing: zero credits | Purchase credits at console.anthropic.com |
| 3 | LOW | pytest InsecureKeyLengthWarning | Use 32+ byte HMAC key in test fixtures |
| 4 | LOW | 3 untracked files in repo | Add to `.gitignore` or commit |
