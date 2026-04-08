#!/usr/bin/env bash
# OpenClaw 8-Agent Config Deployment Script
# Target: 95.216.212.174 (OpenClaw server)
# Usage: ./deploy.sh [--dry-run]

set -euo pipefail

# --- Configuration ---
SERVER="95.216.212.174"
SSH_KEY="$HOME/.ssh/openclaw_ed25519"
SSH_USER="root"
SSH_OPTS="-i ${SSH_KEY} -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
REMOTE_BASE="/home/openclawadmin/.openclaw"
LOCAL_BASE="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DRY_RUN=false

AGENTS=("eng-core" "wp-web" "infra-ops" "design-lab" "content-forge" "social-growth" "intel-research" "biz-strategy")

# --- Parse args ---
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY-RUN] No changes will be made on the server."
fi

ssh_cmd() {
    if $DRY_RUN; then
        echo "[DRY-RUN] ssh ${SSH_USER}@${SERVER}: $*"
    else
        ssh ${SSH_OPTS} "${SSH_USER}@${SERVER}" "$@"
    fi
}

scp_cmd() {
    if $DRY_RUN; then
        echo "[DRY-RUN] scp $1 → ${SSH_USER}@${SERVER}:$2"
    else
        scp ${SSH_OPTS} "$1" "${SSH_USER}@${SERVER}:$2"
    fi
}

echo "========================================="
echo " OpenClaw 8-Agent Deploy"
echo " Server: ${SERVER}"
echo " Date:   ${TIMESTAMP}"
echo "========================================="

# --- Step 1: Verify SSH connectivity ---
echo ""
echo "[1/6] Verifying SSH connectivity..."
if ! $DRY_RUN; then
    ssh ${SSH_OPTS} "${SSH_USER}@${SERVER}" "echo 'SSH OK'" || {
        echo "FAIL: Cannot connect to ${SERVER}"
        exit 1
    }
fi
echo "  OK"

# --- Step 2: Backup current config ---
echo ""
echo "[2/6] Backing up current openclaw.json..."
ssh_cmd "if [ -f ${REMOTE_BASE}/openclaw.json ]; then
    cp ${REMOTE_BASE}/openclaw.json ${REMOTE_BASE}/openclaw.json.bak.${TIMESTAMP}
    echo 'Backup created: openclaw.json.bak.${TIMESTAMP}'
else
    echo 'No existing config to backup'
fi"

# --- Step 3: Create workspace directories ---
echo ""
echo "[3/6] Creating workspace directories..."
MKDIR_CMD="mkdir -p ${REMOTE_BASE}/workspaces"
for agent in "${AGENTS[@]}"; do
    MKDIR_CMD="${MKDIR_CMD} ${REMOTE_BASE}/workspaces/${agent}"
done
MKDIR_CMD="${MKDIR_CMD} ${REMOTE_BASE}/skills ${REMOTE_BASE}/data ${REMOTE_BASE}/logs"
ssh_cmd "${MKDIR_CMD}"
echo "  Created directories for ${#AGENTS[@]} agents"

# --- Step 4: Copy openclaw.json ---
echo ""
echo "[4/6] Deploying openclaw.json..."
scp_cmd "${LOCAL_BASE}/openclaw.json" "${REMOTE_BASE}/openclaw.json"
echo "  OK"

# --- Step 5: Copy workspace files (AGENTS.md + TOOLS.md) ---
echo ""
echo "[5/6] Deploying workspace files..."
for agent in "${AGENTS[@]}"; do
    AGENTS_FILE="${LOCAL_BASE}/workspaces/${agent}/AGENTS.md"
    TOOLS_FILE="${LOCAL_BASE}/workspaces/${agent}/TOOLS.md"

    if [ -f "$AGENTS_FILE" ]; then
        scp_cmd "$AGENTS_FILE" "${REMOTE_BASE}/workspaces/${agent}/AGENTS.md"
    else
        echo "  WARN: Missing ${AGENTS_FILE}"
    fi

    if [ -f "$TOOLS_FILE" ]; then
        scp_cmd "$TOOLS_FILE" "${REMOTE_BASE}/workspaces/${agent}/TOOLS.md"
    else
        echo "  WARN: Missing ${TOOLS_FILE}"
    fi

    echo "  ${agent}: OK"
done

# --- Step 6: Restart OpenClaw gateway and verify ---
echo ""
echo "[6/6] Restarting OpenClaw gateway..."
ssh_cmd "cd /home/openclawadmin && \
    if command -v openclaw >/dev/null 2>&1; then
        openclaw gateway restart 2>&1 || systemctl restart openclaw 2>&1 || echo 'WARN: Could not restart via openclaw CLI or systemctl'
    elif systemctl is-active --quiet openclaw 2>/dev/null; then
        systemctl restart openclaw
    elif docker ps --format '{{.Names}}' | grep -q openclaw; then
        docker restart openclaw-gateway 2>&1 || echo 'WARN: Docker restart failed'
    else
        echo 'WARN: No known OpenClaw service found — manual restart may be needed'
    fi"

# --- Verification ---
echo ""
echo "========================================="
echo " Verification"
echo "========================================="

ssh_cmd "echo '--- Config file ---' && \
    ls -la ${REMOTE_BASE}/openclaw.json && \
    echo '' && \
    echo '--- Workspace dirs ---' && \
    ls -la ${REMOTE_BASE}/workspaces/ && \
    echo '' && \
    echo '--- Agent files ---' && \
    for agent in ${AGENTS[*]}; do
        if [ -f ${REMOTE_BASE}/workspaces/\${agent}/AGENTS.md ] && [ -f ${REMOTE_BASE}/workspaces/\${agent}/TOOLS.md ]; then
            echo \"  \${agent}: AGENTS.md + TOOLS.md OK\"
        else
            echo \"  \${agent}: MISSING FILES\"
        fi
    done && \
    echo '' && \
    echo '--- Agent count in config ---' && \
    grep -c '\"id\":' ${REMOTE_BASE}/openclaw.json | xargs -I{} echo '  Registered agents: {}'"

echo ""
echo "========================================="
echo " Deploy complete: ${TIMESTAMP}"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Verify gateway is running: ssh -i ${SSH_KEY} ${SSH_USER}@${SERVER} 'systemctl status openclaw'"
echo "  2. Test agent routing: curl https://api.occp.ai/api/v1/agents/registry"
echo "  3. Check logs: ssh -i ${SSH_KEY} ${SSH_USER}@${SERVER} 'tail -50 ${REMOTE_BASE}/logs/openclaw.log'"
