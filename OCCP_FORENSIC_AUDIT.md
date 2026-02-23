# OCCP v0.5.0 — Forensic Audit Report

**Date:** 2026-02-23 | **HEAD:** `6c73a7f` | **Auditor:** Claude Opus 4.6

---

## Verdict

| Category | Grade | Notes |
|----------|-------|-------|
| **TECH** | **PASS** | 145 tests (0 warnings), 12/12 build, versions unified |
| **DEPLOY** | **PASS** | CI + Deploy success, prod verified live |
| **SECURITY** | **PASS** | Non-root, read_only, no-new-privileges, 127.0.0.1, tmpfs |
| **GOVERNANCE** | **PASS** | `enforce_admins` fixed to `true` during audit |

**Overall: 4/4 PASS**

---

## A) Repo Integrity

```
$ git rev-parse HEAD → 6c73a7f814327c8491d994f403f34bd7d7959b0a
$ git rev-parse origin/main → 6c73a7f814327c8491d994f403f34bd7d7959b0a
```
LOCAL = ORIGIN: **MATCH**

### Version 0.5.0 — All 8 Files

| File | Value | Status |
|------|-------|--------|
| `pyproject.toml` | `version = "0.5.0"` | PASS |
| `api/routes/status.py` | `version="0.5.0"` | PASS |
| `cli/__init__.py` | `__version__ = "0.5.0"` | PASS |
| `dash/package.json` | `"version": "0.5.0"` | PASS |
| `sdk/python/__init__.py` | `__version__ = "0.5.0"` | PASS |
| `sdk/typescript/package.json` | `"version": "0.5.0"` | PASS |
| `orchestrator/__init__.py` | `__version__ = "0.5.0"` | PASS |
| `policy_engine/__init__.py` | `__version__ = "0.5.0"` | PASS |

Untracked (non-critical): `OCCP_STATUS_REPORT.md`, `dash/next-env.d.ts`, `sdk/typescript/package-lock.json`

---

## B) Build/Test Gate

```
$ .venv/bin/pytest -q --tb=no
145 passed in 3.36s (0 warnings)

$ npm run build (dash/)
✓ Compiled successfully
✓ 12/12 static pages: / /agents /audit /docs /login /pipeline /policy ...
```

---

## C) Production Verify

```
$ curl -s https://api.occp.ai/api/v1/status
{"platform":"OCCP","version":"0.5.0","status":"running","tasks_count":2,"audit_entries":1}

$ curl -sI https://dash.occp.ai/login → HTTP/1.1 200 OK
$ curl -sI https://dash.occp.ai/agents → HTTP/1.1 200 OK
$ curl -sI https://dash.occp.ai/docs → HTTP/1.1 200 OK

No-cache bypass: identical response. Security headers: nosniff, SAMEORIGIN, strict-origin-when-cross-origin.
```

---

## D) GitHub Actions / Deploy

| Run ID | Workflow | Status |
|--------|----------|--------|
| 22288892494 | Deploy | **success** (3m6s) |
| 22288892482 | CI | **success** (49s) |
| 22288892485 | Secret Scanning | **success** (15s) |

Deploy log: `occp-api-1 Healthy` → `occp-dash-1 Started` → `✅ Successfully executed commands to all hosts.`

### Governance — FIXED

```
BEFORE: enforce_admins: {"enabled": false}
FIX:    gh api -X POST .../enforce_admins
AFTER:  enforce_admins: {"enabled": true}
```

---

## E) Docker Hardening (SSH: 138.199.233.91)

| Check | Actual | Status |
|-------|--------|--------|
| Non-root user | `uid=1001(occp) gid=1001(occp)` | PASS |
| read_only rootfs (API) | `true` | PASS |
| read_only rootfs (Dash) | `true` | PASS |
| no-new-privileges | `["no-new-privileges:true"]` | PASS |
| tmpfs | `/tmp` | PASS |
| Port 8000 | `127.0.0.1:8000` | PASS |
| Port 3000 | `127.0.0.1:3000` | PASS |
| Volume ownership | `occp:occp /app/data` | PASS |
| Container health | Both `Up (healthy)` | PASS |

### Volume Ownership — Reproducible (2 paths)

1. `Dockerfile.api:17-19` → `groupadd/useradd 1001 + mkdir + chown`
2. `deploy.yml` → `docker run --rm -v occp_occp-data:/data alpine chown -R 1001:1001 /data`

---

## F) Anthropic API

```
Key present: OCCP_ANTHROPIC_API_KEY=sk-ant-api03-FIO7fPA...
Format: valid (sk-ant-api03-*)

Smoke test: HTTP 400
"Your credit balance is too low to access the Anthropic API."
request_id: req_011CYQbjQvDdiUqSc5Sq8UV7
```

**BILLING FAIL** — Key valid, credits depleted.

---

## Fixes Applied During This Audit

1. **`enforce_admins: false → true`** — Admins can no longer bypass required status checks
2. **pytest HMAC key** — Test fixture key extended to 32 bytes (RFC 7518), 0 warnings now

## Open Items

| # | Severity | Item | Fix |
|---|----------|------|-----|
| 1 | **HIGH** | Anthropic API billing | Purchase credits: console.anthropic.com/settings/billing |
| 2 | LOW | 3 untracked files | `.gitignore` or commit |
