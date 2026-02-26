# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.8.x   | :white_check_mark: |
| < 0.8   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in OCCP, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email: **security@occp.ai**
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

| Action | Timeline |
|--------|----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix release | Within 30 days (critical: 7 days) |

### Scope

The following are in scope:

- API endpoints (`api.occp.ai`)
- Dashboard (`dash.occp.ai`)
- Policy engine bypass
- RBAC/authentication bypass
- SQL injection
- XSS in dashboard
- Sandbox escape
- Credential exposure

### Out of Scope

- Self-hosted instances with default credentials (documented requirement to change)
- Denial of service (DoS)
- Social engineering

## Security Architecture

- **Authentication**: JWT with configurable expiry
- **Authorization**: Casbin RBAC (viewer, operator, org_admin, system_admin)
- **Input sanitization**: Pydantic models with strict validation
- **Output**: CSP headers, no X-Powered-By leak
- **Audit**: SHA-256 chained audit log
- **Sandbox**: nsjail/bubblewrap/process-level isolation
- **Dependencies**: Automated scanning via Snyk and GitHub Dependabot
