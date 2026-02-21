#!/usr/bin/env bash
set -euo pipefail

# OCCP Phase 1.2: Local development install
# Does NOT execute remote code — installs from local manifests only.

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[OCCP] Starting local development installation..."

cd "$REPO_ROOT"

# Upgrade pip
python3 -m pip install --upgrade pip

# Install Python dependencies
if [[ -f pyproject.toml ]]; then
    echo "Found pyproject.toml – installing with pip (editable + dev)"
    python3 -m pip install -e ".[dev]"
elif [[ -f requirements.txt ]]; then
    echo "Found requirements.txt – installing"
    python3 -m pip install -r requirements.txt
fi

# Install Node/JS dependencies for the dashboard
if [[ -f dash/package.json ]]; then
    echo "Installing dash dependencies..."
    cd dash
    if command -v pnpm &>/dev/null; then
        pnpm install
    else
        npm install
    fi
    cd "$REPO_ROOT"
fi

# Create config template copy if missing
if [[ ! -f config/occp.config.yaml ]]; then
    if [[ -f config/occp.config.yaml.example ]]; then
        cp config/occp.config.yaml.example config/occp.config.yaml
        echo "Created config/occp.config.yaml from example"
    fi
fi

cat <<'POST'

✓ Install completed.

Next steps:
  1) Run scripts/onboard.sh to configure secrets and channels
  2) Run tests: pytest -v
  3) Start the dashboard: docker compose up -d
POST
