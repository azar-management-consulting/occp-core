# Managing Secrets in OCCP

Mismanagement of API keys and tokens is the leading cause of agent compromise.
OCCP takes a security-first approach to secret management.

## Recommended Practices

### 1. Use `.env` for local development
- Create a `.env` file at the repository root with entries like `ANTHROPIC_API_KEY=...`, `SLACK_BOT_TOKEN=...`.
- Ensure `.env` is listed in `.gitignore` so it is never committed.
- Use `scripts/onboard.sh` to prompt for these values securely (silent input).

### 2. Use GitHub Secrets for CI/CD
- Do **not** rely on `.env` in the repository for CI.
- Add keys to **Settings > Secrets and variables > Actions**.
- Reference in workflows: `${{ secrets.MY_SECRET }}`.

### 3. Use a secrets manager for production
- Integrate HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, etc.
- Inject secrets at runtime; never bake into Docker images.

### 4. Rotate and scope tokens
- Rotate API keys regularly.
- Use fine-grained PATs and limited-scope bot tokens.
- Monitor for token leakage via the secret scanning workflow.

### 5. Never store secrets in YAML/Markdown
- Configuration files reference environment variable names, never actual values.
- Keep secrets in environment variables or vaults only.

## Secret Scanning

The `.github/workflows/secrets-scan.yml` workflow runs TruffleHog on each push to detect accidental secret commits.

Local scanning: `scripts/security-report.sh`.

## See Also

- [SECRETS_POLICY.md](../security/SECRETS_POLICY.md)
- [PHASE_1_2.md](PHASE_1_2.md)
