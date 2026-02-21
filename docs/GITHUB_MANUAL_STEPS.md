# GitHub Manual Steps – Phase 1.2

## 1) Enable secret scanning and supply chain protection

Navigate to **Settings > Security & analysis** for each repository (`occp-core`, `occp-ee`) and enable:

- Secret scanning
- Secret scanning > push protection
- Supply chain security (dependency graph & advisory database)

## 2) Add repository secrets

Under **Settings > Secrets and variables > Actions**, add:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `OCCP_DASH_JWT_SECRET`

Use environment-specific names for production (e.g., `ANTHROPIC_API_KEY_PROD`).

## 3) Branch protection

Verify branch protection rules on `main`:

- Require pull request & approval
- Require status checks: CI, secrets-scan
- Optionally require signed commits

## 4) Repository transfer (optional)

When ready to move to `opencloud-controlplane` organization:
**Settings > Transfer ownership**. Ensure the org has branch protection and secret scanning enabled.

## 5) Delete outdated personal repos

Delete `fulophenry-hue/occp-core` from the web interface if it still exists.
