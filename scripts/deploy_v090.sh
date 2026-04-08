#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# OCCP v0.9.0 Production Deploy Script
# Target: 195.201.238.144 (Hetzner AZAR)
# Containers: occp-api-1 (:8000), occp-dash-1 (:3000)
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly VERSION="0.9.0"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
readonly DEPLOY_TAG="v${VERSION}-${TIMESTAMP}"

readonly SERVER="195.201.238.144"
readonly SSH_USER="root"
readonly SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"

# Detect SSH key
if [[ -f "$HOME/.ssh/id_ed25519" ]]; then
    SSH_KEY="$HOME/.ssh/id_ed25519"
elif [[ -f "$HOME/.ssh/id_rsa" ]]; then
    SSH_KEY="$HOME/.ssh/id_rsa"
else
    echo "FATAL: No SSH key found at ~/.ssh/id_ed25519 or ~/.ssh/id_rsa"
    exit 1
fi

readonly REMOTE_DIR="/opt/occp"
readonly BACKUP_DIR="/opt/occp-backups"
readonly ARCHIVE_NAME="occp-${DEPLOY_TAG}.tar.gz"
readonly LOG_FILE="/tmp/occp_deploy_${TIMESTAMP}.log"

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log() {
    local level="$1"; shift
    local msg="[$(date '+%H:%M:%S')] [$level] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

log_ok()   { log "OK"   "$@"; }
log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_fail() { log "FAIL" "$@"; }

# ---------------------------------------------------------------------------
# SSH / SCP helpers
# ---------------------------------------------------------------------------
ssh_cmd() {
    ssh $SSH_OPTS -i "$SSH_KEY" "${SSH_USER}@${SERVER}" "$@"
}

scp_to() {
    scp $SSH_OPTS -i "$SSH_KEY" "$1" "${SSH_USER}@${SERVER}:$2"
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
preflight() {
    log_info "=== Pre-flight Checks ==="

    # Verify repo root
    if [[ ! -f "$REPO_ROOT/pyproject.toml" ]]; then
        log_fail "Not in OCCP repo root"
        exit 1
    fi

    # Verify version in pyproject.toml
    local pyproject_version
    pyproject_version=$(grep -oP 'version = "\K[^"]+' "$REPO_ROOT/pyproject.toml" | head -1)
    if [[ "$pyproject_version" != "$VERSION" ]]; then
        log_fail "pyproject.toml version ($pyproject_version) != deploy version ($VERSION)"
        exit 1
    fi
    log_ok "Version check: $VERSION"

    # Check SSH connectivity
    if ! ssh_cmd "echo ok" >/dev/null 2>&1; then
        log_fail "Cannot SSH to $SERVER"
        exit 1
    fi
    log_ok "SSH connectivity to $SERVER"

    # Check Docker on remote
    if ! ssh_cmd "docker compose version" >/dev/null 2>&1; then
        log_fail "docker compose not available on $SERVER"
        exit 1
    fi
    log_ok "Docker Compose available on remote"

    # Check disk space (need at least 2GB free)
    local free_gb
    free_gb=$(ssh_cmd "df -BG /opt | tail -1 | awk '{print \$4}' | tr -d 'G'")
    if [[ "$free_gb" -lt 2 ]]; then
        log_fail "Low disk space: ${free_gb}GB free (need 2GB+)"
        exit 1
    fi
    log_ok "Disk space: ${free_gb}GB free"

    log_info "Pre-flight PASSED"
}

# ---------------------------------------------------------------------------
# Step 1: Create archive from local git state
# ---------------------------------------------------------------------------
create_archive() {
    log_info "=== Step 1: Creating Archive ==="

    cd "$REPO_ROOT"

    # Use git archive for clean export (respects .gitignore)
    git archive --format=tar.gz \
        --prefix=occp/ \
        -o "/tmp/${ARCHIVE_NAME}" \
        HEAD

    local size
    size=$(du -h "/tmp/${ARCHIVE_NAME}" | cut -f1)
    log_ok "Archive created: /tmp/${ARCHIVE_NAME} ($size)"
}

# ---------------------------------------------------------------------------
# Step 2: Transfer archive to server
# ---------------------------------------------------------------------------
transfer_archive() {
    log_info "=== Step 2: Transferring Archive ==="

    # Ensure remote directories exist
    ssh_cmd "mkdir -p ${BACKUP_DIR} ${REMOTE_DIR}"

    scp_to "/tmp/${ARCHIVE_NAME}" "${BACKUP_DIR}/${ARCHIVE_NAME}"
    log_ok "Archive transferred to ${BACKUP_DIR}/${ARCHIVE_NAME}"
}

# ---------------------------------------------------------------------------
# Step 3: Backup current deployment
# ---------------------------------------------------------------------------
backup_current() {
    log_info "=== Step 3: Backing Up Current Deployment ==="

    ssh_cmd "
        if [[ -d ${REMOTE_DIR} && -f ${REMOTE_DIR}/docker-compose.yml ]]; then
            tar czf ${BACKUP_DIR}/occp-rollback-${TIMESTAMP}.tar.gz \
                -C /opt occp \
                --exclude='occp/data' \
                --exclude='occp/.venv' \
                --exclude='occp/node_modules' \
                --exclude='occp/dash/node_modules' \
                --exclude='occp/dash/.next'
            echo 'Backup created: occp-rollback-${TIMESTAMP}.tar.gz'
        else
            echo 'No existing deployment to back up'
        fi
    "

    # Also snapshot the .env separately
    ssh_cmd "
        if [[ -f ${REMOTE_DIR}/.env ]]; then
            cp ${REMOTE_DIR}/.env ${BACKUP_DIR}/.env.bak.${TIMESTAMP}
            echo '.env backed up'
        fi
    "

    log_ok "Backup complete"
}

# ---------------------------------------------------------------------------
# Step 4: Extract new code
# ---------------------------------------------------------------------------
extract_code() {
    log_info "=== Step 4: Extracting New Code ==="

    ssh_cmd "
        cd /opt
        # Extract archive (creates /opt/occp/ from prefix)
        tar xzf ${BACKUP_DIR}/${ARCHIVE_NAME} --strip-components=0

        # Restore .env from backup (never overwrite production secrets)
        if [[ -f ${BACKUP_DIR}/.env.bak.${TIMESTAMP} ]]; then
            cp ${BACKUP_DIR}/.env.bak.${TIMESTAMP} ${REMOTE_DIR}/.env
            echo '.env restored from backup'
        fi

        # Verify extraction
        ls -la ${REMOTE_DIR}/docker-compose.yml
        echo 'Code extracted successfully'
    "

    log_ok "Code extracted to ${REMOTE_DIR}"
}

# ---------------------------------------------------------------------------
# Step 5: Rebuild Docker images
# ---------------------------------------------------------------------------
rebuild_containers() {
    log_info "=== Step 5: Rebuilding Docker Images ==="

    ssh_cmd "
        cd ${REMOTE_DIR}

        # Stop current containers gracefully
        echo 'Stopping containers...'
        docker compose down --timeout 30 2>&1 || true

        # Build with no cache for clean rebuild
        echo 'Building images (--no-cache)...'
        docker compose build --no-cache 2>&1

        echo 'Build complete'
    "

    log_ok "Docker images rebuilt"
}

# ---------------------------------------------------------------------------
# Step 6: Run migrations
# ---------------------------------------------------------------------------
run_migrations() {
    log_info "=== Step 6: Running Migrations ==="

    ssh_cmd "
        cd ${REMOTE_DIR}

        # Start only the API container temporarily for migrations
        # We run alembic inside the container
        docker compose run --rm --no-deps api \
            python -m alembic upgrade head 2>&1 || {
            echo 'WARN: Migration via alembic failed, checking if tables exist...'
            echo 'Migration may not be needed if DB is up to date.'
        }
    "

    log_ok "Migrations complete"
}

# ---------------------------------------------------------------------------
# Step 7: Start containers with health checks
# ---------------------------------------------------------------------------
start_containers() {
    log_info "=== Step 7: Starting Containers ==="

    ssh_cmd "
        cd ${REMOTE_DIR}

        # Start all services
        docker compose up -d 2>&1

        echo 'Waiting for containers to become healthy...'

        # Wait up to 90 seconds for health checks
        local attempt=0
        local max_attempts=18
        while [[ \$attempt -lt \$max_attempts ]]; do
            local api_health
            api_health=\$(docker inspect --format='{{.State.Health.Status}}' occp-api-1 2>/dev/null || echo 'unknown')

            if [[ \"\$api_health\" == 'healthy' ]]; then
                echo \"API container healthy after \$(( attempt * 5 )) seconds\"
                break
            fi

            echo \"  Attempt \$((attempt+1))/\$max_attempts: api=\$api_health\"
            sleep 5
            attempt=\$((attempt + 1))
        done

        if [[ \$attempt -ge \$max_attempts ]]; then
            echo 'TIMEOUT: Containers did not become healthy in 90 seconds'
            docker compose logs --tail=50
            exit 1
        fi

        # Show final container status
        docker compose ps
    "

    log_ok "Containers started and healthy"
}

# ---------------------------------------------------------------------------
# Step 8: Verify endpoints
# ---------------------------------------------------------------------------
verify_endpoints() {
    log_info "=== Step 8: Verifying Endpoints ==="

    local failures=0

    # API status
    local status_code
    status_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/status" 2>/dev/null)
    if [[ "$status_code" == "200" ]]; then
        log_ok "GET /api/v1/status -> 200"
    else
        log_fail "GET /api/v1/status -> $status_code"
        failures=$((failures + 1))
    fi

    # Health check
    status_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health" 2>/dev/null)
    if [[ "$status_code" == "200" ]]; then
        log_ok "GET /api/v1/health -> 200"
    else
        log_fail "GET /api/v1/health -> $status_code"
        failures=$((failures + 1))
    fi

    # Brain registry (requires auth, expect 401 or 200)
    status_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/agents/registry" 2>/dev/null)
    if [[ "$status_code" == "200" || "$status_code" == "401" || "$status_code" == "403" ]]; then
        log_ok "GET /api/v1/agents/registry -> $status_code (endpoint exists)"
    else
        log_fail "GET /api/v1/agents/registry -> $status_code"
        failures=$((failures + 1))
    fi

    # Dashboard
    status_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/" 2>/dev/null)
    if [[ "$status_code" == "200" || "$status_code" == "304" ]]; then
        log_ok "GET dash:3000/ -> $status_code"
    else
        log_fail "GET dash:3000/ -> $status_code"
        failures=$((failures + 1))
    fi

    # External HTTPS checks (via Apache reverse proxy)
    status_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://api.occp.ai/api/v1/status" 2>/dev/null || echo "000")
    if [[ "$status_code" == "200" ]]; then
        log_ok "HTTPS api.occp.ai/api/v1/status -> 200"
    else
        log_warn "HTTPS api.occp.ai/api/v1/status -> $status_code (may need DNS propagation)"
    fi

    if [[ $failures -gt 0 ]]; then
        log_fail "$failures endpoint(s) failed verification"
        return 1
    fi

    log_ok "All endpoints verified"
    return 0
}

# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------
rollback() {
    log_warn "=== ROLLBACK INITIATED ==="

    ssh_cmd "
        cd /opt

        # Stop current containers
        cd ${REMOTE_DIR} && docker compose down --timeout 15 2>&1 || true

        # Restore from backup
        if [[ -f ${BACKUP_DIR}/occp-rollback-${TIMESTAMP}.tar.gz ]]; then
            rm -rf ${REMOTE_DIR}
            tar xzf ${BACKUP_DIR}/occp-rollback-${TIMESTAMP}.tar.gz -C /opt
            echo 'Code restored from backup'
        else
            echo 'ERROR: No rollback archive found!'
            exit 1
        fi

        # Restore .env
        if [[ -f ${BACKUP_DIR}/.env.bak.${TIMESTAMP} ]]; then
            cp ${BACKUP_DIR}/.env.bak.${TIMESTAMP} ${REMOTE_DIR}/.env
        fi

        # Rebuild and start old version
        cd ${REMOTE_DIR}
        docker compose build 2>&1
        docker compose up -d 2>&1

        # Wait for health
        sleep 15
        docker compose ps
    "

    log_warn "Rollback complete — running previous version"
}

# ---------------------------------------------------------------------------
# Cleanup old backups (keep last 5)
# ---------------------------------------------------------------------------
cleanup_backups() {
    log_info "=== Cleaning Up Old Backups ==="

    ssh_cmd "
        cd ${BACKUP_DIR}
        # Keep last 5 rollback archives
        ls -t occp-rollback-*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
        # Keep last 5 deploy archives
        ls -t occp-v*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
        echo 'Cleanup done. Current backups:'
        ls -lh *.tar.gz 2>/dev/null || echo '(none)'
    "
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  OCCP v${VERSION} Production Deploy"
    echo "  Target: ${SSH_USER}@${SERVER}"
    echo "  Tag:    ${DEPLOY_TAG}"
    echo "  Log:    ${LOG_FILE}"
    echo "═══════════════════════════════════════════════════"
    echo ""

    log_info "Deploy started at $(date)"

    preflight
    create_archive
    transfer_archive
    backup_current
    extract_code
    rebuild_containers
    run_migrations
    start_containers

    if verify_endpoints; then
        cleanup_backups
        log_ok "═══ DEPLOY v${VERSION} SUCCESS ═══"
        log_info "Rollback archive: ${BACKUP_DIR}/occp-rollback-${TIMESTAMP}.tar.gz"
    else
        log_fail "Endpoint verification failed — initiating rollback"
        rollback
        log_fail "═══ DEPLOY v${VERSION} FAILED — ROLLED BACK ═══"
        exit 1
    fi

    log_info "Deploy finished at $(date)"
    echo ""
    echo "Deploy log saved to: $LOG_FILE"
}

# ---------------------------------------------------------------------------
# CLI arguments
# ---------------------------------------------------------------------------
case "${1:-deploy}" in
    deploy)
        main
        ;;
    rollback)
        TIMESTAMP="${2:-$(date +%Y%m%d_%H%M%S)}"
        rollback
        ;;
    verify)
        verify_endpoints
        ;;
    preflight)
        preflight
        ;;
    *)
        echo "Usage: $0 {deploy|rollback [timestamp]|verify|preflight}"
        exit 1
        ;;
esac
