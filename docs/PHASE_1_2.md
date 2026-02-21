# Phase 1.2 – Secure Onboarding & Multi-Channel Configuration

This phase focuses on building a *user-friendly, secure onboarding experience* and preparing OCCP to manage multiple messaging channels safely.

## A) Onboarding Wizard

1. Interactive script (`scripts/onboard.sh`) that:
   - Prompts for required secrets (API keys, bot tokens) **without echoing** them on screen.
   - Writes secrets to `.env` (or instructs to use GitHub Secrets / vault).
   - Copies `config/occp.config.yaml.example` to `config/occp.config.yaml`.
   - Verifies `.env` is git-ignored and not committed.
   - Validates required fields and warns about insecure bind addresses (`0.0.0.0`).
   - Does **not** execute untrusted code.
2. Manual onboarding instructions in this document and `README.md`.

## B) Secret Management

1. `docs/SECRETS.md` – explains how to manage secrets safely.
2. `.github/workflows/secrets-scan.yml` – TruffleHog-based secret scanning on every push.
3. `scripts/security-report.sh` – local dependency and secret scanning.

## C) Multi-Channel Safety

1. Channel configs in `config/occp.config.yaml.example` with safe defaults:
   - Bind to `127.0.0.1` by default.
   - `pairing_required: true` for each channel.
2. Placeholders for Slack and Telegram connectors.

## D) Policy & Tool Management

1. Config template `skills` section: allowlist + deny-all default.
2. Comments on skill version pinning and signature verification (future work).

## E) Enterprise Controls & Scanning

1. CodeQL, Dependabot, SBOM and pip-audit from Phase 1.1.
2. Secret scanning and supply chain protection enabled in GitHub UI.

## F) Exit Criteria

- [x] Onboarding wizard runs without errors, produces `.env` and `occp.config.yaml`.
- [x] No secrets committed to repository.
- [x] Multi-channel configs present and disabled by default.
- [x] Secret scanning workflow in place.
- [x] Updated documentation merged.
