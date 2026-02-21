# OpenClaw Comparison & Lessons Learned

OpenClaw is a self-hosted, always-on AI agent that gained popularity in early 2026. Its architecture offers valuable lessons for OCCP.

## Patterns to Emulate

1. **User-friendly onboarding**: CLI wizard that lowers the barrier to entry. OCCP offers `scripts/onboard.sh` but avoids auto-executing untrusted scripts.
2. **Local-first storage**: data stored locally in YAML/Markdown. OCCP separates config from secrets.
3. **Tool/Skill modularity**: extensible plugin architecture. OCCP adopts deny-by-default policy with allowlist.
4. **One-command install**: `scripts/install.sh` mirrors the approach without running remote code.

## Patterns to Avoid

1. **Storing secrets in plain files**: OCCP uses `.env` + secrets managers, never plaintext config files.
2. **Exposing services to all interfaces**: OCCP binds to `127.0.0.1` by default; remote access via proxy/tunnel only.
3. **Unvetted extensions**: all skills must be reviewed and pinned; signature verification is planned.

## Security Risks Observed in OpenClaw

- Supply chain attacks on skills (malicious community-contributed skills).
- Credentials stored in plaintext under `~/.openclaw/`.
- Default network exposure (`0.0.0.0` bind).
- No mandatory review or code signing for skills.
