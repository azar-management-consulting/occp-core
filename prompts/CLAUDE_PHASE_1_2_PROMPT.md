# Claude Code Prompt – Phase 1.2 Secure Onboarding & Multi-Channel

> Use this prompt in Claude Code from the root of the `occp-core` repository.
> This task builds upon Phase 1.1 (hardening baseline).

## Objectives

1. Implement a secure, user-friendly onboarding wizard (`scripts/onboard.sh`).
2. Integrate secret management guidance and config templates.
3. Add multi-channel configuration placeholders with safe defaults.
4. Update documentation and workflows accordingly.

## Acceptance Criteria

- Onboarding wizard runs without errors, produces `.env` and `occp.config.yaml`.
- No secrets committed to repository.
- Multi-channel configs present and disabled by default.
- Secret scanning workflow in place and passes.
- All existing tests pass.
- Updated documentation merged.
