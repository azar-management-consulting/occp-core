# OCCP Secrets Policy – Phase 1.2

1. **No secrets in source control**: `.env` and any files containing secrets must be git-ignored. The onboarding script ensures `.env` is created and ignored.
2. **No secrets in YAML/Markdown**: configuration files reference environment variables or secret IDs, never actual values.
3. **Rotate and minimize**: use short-lived tokens (TTL) when possible; restrict permissions on API keys (least privilege).
4. **Scan and monitor**: secrets scanning must run on every push; monitor alerts for exposures.
5. **Use vaults in production**: environment variables are acceptable for local dev; use secret managers in production.

This policy is enforced via CI (`.github/workflows/secrets-scan.yml`) and documented in `docs/SECRETS.md`.
