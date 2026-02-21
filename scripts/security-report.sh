#!/usr/bin/env bash
set -euo pipefail

# OCCP Phase 1.2: Local security scans (dependency & secret scan)

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "═══ OCCP Security Report ═══"
echo ""

# Python dependency audit
echo "─── Python Dependency Audit ───"
if command -v pip-audit >/dev/null 2>&1; then
    pip-audit || true
else
    echo "pip-audit not installed. Install: pip install pip-audit"
fi
echo ""

# Node/JS audit
if [[ -f dash/package.json ]]; then
    echo "─── Node.js Dependency Audit (dash) ───"
    if command -v npm >/dev/null 2>&1; then
        (cd dash && npm audit 2>/dev/null) || true
    fi
    echo ""
fi

if [[ -f sdk/typescript/package.json ]]; then
    echo "─── Node.js Dependency Audit (sdk/typescript) ───"
    if command -v npm >/dev/null 2>&1; then
        (cd sdk/typescript && npm audit 2>/dev/null) || true
    fi
    echo ""
fi

# Secret scanning
echo "─── Secret Scan (TruffleHog) ───"
if command -v trufflehog >/dev/null 2>&1; then
    trufflehog filesystem --no-update --fail . || true
elif command -v gitleaks >/dev/null 2>&1; then
    echo "Using gitleaks..."
    gitleaks detect --source . || true
else
    echo "No secret scanner found. Install trufflehog or gitleaks."
fi

# .env check
echo ""
echo "─── .env Safety Check ───"
if [[ -f .env ]]; then
    if git ls-files --error-unmatch .env >/dev/null 2>&1; then
        echo "CRITICAL: .env is tracked by git!"
    else
        echo "✓ .env exists and is NOT tracked by git"
    fi
else
    echo "✓ No .env file found (safe)"
fi

echo ""
echo "═══ Security Report Complete ═══"
