#!/usr/bin/env bash
set -euo pipefail

# OCCP Phase 1.2: Secure Onboarding Wizard
# Guides the operator through setting up secrets and configuration.
# Does NOT run remote code or connect to external services.

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly CONFIG_EXAMPLE="$REPO_ROOT/config/occp.config.yaml.example"
readonly CONFIG_FILE="$REPO_ROOT/config/occp.config.yaml"
readonly ENV_FILE="$REPO_ROOT/.env"
readonly GITIGNORE="$REPO_ROOT/.gitignore"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

color_green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
color_yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
color_red() { printf '\033[0;31m%s\033[0m\n' "$*"; }

prompt_secret() {
    local var="$1"
    local desc="$2"
    local value
    # Read without echoing to screen
    read -r -s -p "  Enter $desc (leave blank to skip): " value
    echo ""  # newline after silent read
    if [[ -n "$value" ]]; then
        # Append or update in .env
        if grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
            # Update existing value
            local tmp
            tmp=$(mktemp)
            while IFS= read -r line; do
                if [[ "$line" == "${var}="* ]]; then
                    echo "${var}=${value}"
                else
                    echo "$line"
                fi
            done < "$ENV_FILE" > "$tmp"
            mv "$tmp" "$ENV_FILE"
        else
            echo "${var}=${value}" >> "$ENV_FILE"
        fi
        color_green "    ✓ ${var} saved"
    else
        color_yellow "    ○ ${var} skipped"
    fi
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

echo ""
color_green "╔══════════════════════════════════════════╗"
color_green "║   OCCP Secure Onboarding Wizard v1.2    ║"
color_green "╚══════════════════════════════════════════╝"
echo ""

# Verify we are in the repo root
if [[ ! -f "$REPO_ROOT/pyproject.toml" ]]; then
    color_red "ERROR: pyproject.toml not found. Run this script from the OCCP repo root."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 1: .env setup
# ---------------------------------------------------------------------------

echo "─── Step 1: Secret Configuration ───"
echo ""

# Create .env if missing
if [[ ! -f "$ENV_FILE" ]]; then
    touch "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "Created $ENV_FILE (mode 600)"
else
    echo "Found existing $ENV_FILE"
fi

# Ensure .env is git-ignored
if ! grep -q "^\.env$" "$GITIGNORE" 2>/dev/null; then
    echo ".env" >> "$GITIGNORE"
    color_yellow "WARNING: Added .env to .gitignore (was missing!)"
fi

# Check .env is not tracked by git
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    color_red "CRITICAL: .env is tracked by git! Run: git rm --cached .env"
    exit 1
fi

echo ""
echo "Enter your API keys below. Input is hidden for security."
echo "(Press Enter to skip any key you don't have yet)"
echo ""

# LLM Provider keys
echo "  [LLM Providers]"
prompt_secret "ANTHROPIC_API_KEY" "Anthropic API key"
prompt_secret "OPENAI_API_KEY" "OpenAI API key"

echo ""
echo "  [Channel Tokens]"
prompt_secret "SLACK_BOT_TOKEN" "Slack bot token"
prompt_secret "SLACK_SIGNING_SECRET" "Slack signing secret"
prompt_secret "TELEGRAM_BOT_TOKEN" "Telegram bot token"

echo ""
echo "  [OCCP Internal]"
prompt_secret "OCCP_DASH_JWT_SECRET" "Dashboard JWT secret"

# Ensure base vars from .env.example are present
for base_var in OCCP_PORT DATABASE_URL; do
    if ! grep -q "^${base_var}=" "$ENV_FILE" 2>/dev/null; then
        case "$base_var" in
            OCCP_PORT) echo "OCCP_PORT=3000" >> "$ENV_FILE" ;;
            DATABASE_URL) echo "DATABASE_URL=sqlite:///occp.db" >> "$ENV_FILE" ;;
        esac
    fi
done

echo ""
color_green "✓ Secrets saved to .env (mode 600)"

# ---------------------------------------------------------------------------
# Step 2: Config file
# ---------------------------------------------------------------------------

echo ""
echo "─── Step 2: Configuration File ───"
echo ""

if [[ ! -f "$CONFIG_FILE" ]]; then
    if [[ -f "$CONFIG_EXAMPLE" ]]; then
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        color_green "✓ Created $CONFIG_FILE from example template"
    else
        color_red "ERROR: Config example not found at $CONFIG_EXAMPLE"
        exit 1
    fi
else
    color_green "✓ Config file already exists: $CONFIG_FILE"
fi

# Add config to .gitignore (contains no secrets but is local override)
if ! grep -q "^config/occp\.config\.yaml$" "$GITIGNORE" 2>/dev/null; then
    echo "config/occp.config.yaml" >> "$GITIGNORE"
fi

# ---------------------------------------------------------------------------
# Step 3: Security validations
# ---------------------------------------------------------------------------

echo ""
echo "─── Step 3: Security Validation ───"
echo ""

WARNINGS=0

# Check for insecure bind addresses
if grep -q "bind_address:.*0\.0\.0\.0" "$CONFIG_FILE" 2>/dev/null; then
    color_red "⚠ WARNING: Config binds to 0.0.0.0 (all interfaces)."
    color_yellow "  Recommendation: Use 127.0.0.1 for local safety."
    color_yellow "  Use a reverse proxy (nginx/caddy) or Tailscale for remote access."
    WARNINGS=$((WARNINGS + 1))
fi

# Check default channels are disabled
for channel in slack telegram; do
    if grep -A2 "^  ${channel}:" "$CONFIG_FILE" 2>/dev/null | grep -q "enabled: true"; then
        color_yellow "⚠ WARNING: Channel '${channel}' is enabled. Verify pairing_required is true."
        WARNINGS=$((WARNINGS + 1))
    fi
done

# Verify skills deny-all
if ! grep -q 'deny:.*\["\*"\]' "$CONFIG_FILE" 2>/dev/null; then
    color_yellow "⚠ WARNING: Skills deny-all policy may not be set. Check config skills section."
    WARNINGS=$((WARNINGS + 1))
fi

if [[ $WARNINGS -eq 0 ]]; then
    color_green "✓ All security checks passed"
else
    color_yellow "  $WARNINGS warning(s) found — review config before deploying"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "─── Onboarding Complete ───"
echo ""
color_green "Next steps:"
echo "  1) Review and customize config/occp.config.yaml"
echo "  2) Run tests: pytest -v"
echo "  3) Start with Docker: docker compose up -d"
echo "  4) Read docs/SECRETS.md for secret management best practices"
echo ""
