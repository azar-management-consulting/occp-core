# OCCP — EU AI Act Alignment

OCCP supports alignment with EU AI Act requirements for high-risk AI systems.

| Requirement | OCCP Capability |
|-------------|-----------------|
| Art. 12 — Record-keeping | SHA-256 chained audit log |
| Art. 14 — Human oversight | Policy gates, approval workflows |
| Art. 19 — Log retention | **Enforced** — default 180 days, configurable via `OCCP_AUDIT_RETENTION_DAYS` (minimum recommended ≥ 180). Pruning runs at every startup (safe, idempotent). Set to `0` to disable pruning. |
| Transparency | Full audit trail, provenance |

## Configuration

```bash
# .env or environment variable
OCCP_AUDIT_RETENTION_DAYS=180   # days to retain audit entries (0 = keep forever)
```

Retention is enforced automatically at application startup. Entries older than the configured threshold are permanently deleted. The hash chain continues from the most recent surviving entry.

**Disclaimer**: This is not legal advice. Verify compliance for your deployment.
