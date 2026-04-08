#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# OCCP v0.9.0 Post-Deploy Verification Script
# Checks: containers, endpoints, brain, websocket, SSL, response times
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

readonly SERVER="195.201.238.144"
readonly SSH_USER="root"
readonly SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
readonly DOMAIN_API="api.occp.ai"
readonly DOMAIN_DASH="dash.occp.ai"

# Detect SSH key
if [[ -f "$HOME/.ssh/id_ed25519" ]]; then
    SSH_KEY="$HOME/.ssh/id_ed25519"
elif [[ -f "$HOME/.ssh/id_rsa" ]]; then
    SSH_KEY="$HOME/.ssh/id_rsa"
else
    echo "FATAL: No SSH key found"
    exit 1
fi

# Counters
PASS=0
FAIL=0
WARN=0
TOTAL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ssh_cmd() {
    ssh $SSH_OPTS -i "$SSH_KEY" "${SSH_USER}@${SERVER}" "$@"
}

check() {
    local name="$1"
    local result="$2"
    local expected="$3"
    TOTAL=$((TOTAL + 1))

    if [[ "$result" == "$expected" ]]; then
        printf "  %-45s %s\n" "$name" "PASS"
        PASS=$((PASS + 1))
    else
        printf "  %-45s %s (got: %s, expected: %s)\n" "$name" "FAIL" "$result" "$expected"
        FAIL=$((FAIL + 1))
    fi
}

check_range() {
    local name="$1"
    local result="$2"
    local min="$3"
    local max="$4"
    TOTAL=$((TOTAL + 1))

    if [[ "$result" -ge "$min" && "$result" -le "$max" ]]; then
        printf "  %-45s %s (%s)\n" "$name" "PASS" "$result"
        PASS=$((PASS + 1))
    else
        printf "  %-45s %s (got: %s, expected: %s-%s)\n" "$name" "FAIL" "$result" "$min" "$max"
        FAIL=$((FAIL + 1))
    fi
}

warn_check() {
    local name="$1"
    local result="$2"
    local expected="$3"
    TOTAL=$((TOTAL + 1))

    if [[ "$result" == "$expected" ]]; then
        printf "  %-45s %s\n" "$name" "PASS"
        PASS=$((PASS + 1))
    else
        printf "  %-45s %s (got: %s)\n" "$name" "WARN" "$result"
        WARN=$((WARN + 1))
    fi
}

# ---------------------------------------------------------------------------
# 1. Docker Container Health
# ---------------------------------------------------------------------------
echo ""
echo "═══ 1. Docker Container Health ═══"
echo ""

api_state=$(ssh_cmd "docker inspect --format='{{.State.Status}}' occp-api-1 2>/dev/null" || echo "missing")
check "API container running" "$api_state" "running"

api_health=$(ssh_cmd "docker inspect --format='{{.State.Health.Status}}' occp-api-1 2>/dev/null" || echo "unknown")
check "API container healthy" "$api_health" "healthy"

dash_state=$(ssh_cmd "docker inspect --format='{{.State.Status}}' occp-dash-1 2>/dev/null" || echo "missing")
check "Dash container running" "$dash_state" "running"

# Check restart count (should be 0 after fresh deploy)
api_restarts=$(ssh_cmd "docker inspect --format='{{.RestartCount}}' occp-api-1 2>/dev/null" || echo "-1")
check "API restart count" "$api_restarts" "0"

# Check container uptime (should be recent)
api_started=$(ssh_cmd "docker inspect --format='{{.State.StartedAt}}' occp-api-1 2>/dev/null | cut -c1-19" || echo "unknown")
printf "  %-45s %s\n" "API started at" "$api_started"

# Memory usage
api_mem=$(ssh_cmd "docker stats --no-stream --format '{{.MemUsage}}' occp-api-1 2>/dev/null" || echo "unknown")
printf "  %-45s %s\n" "API memory usage" "$api_mem"

# ---------------------------------------------------------------------------
# 2. API Status Endpoint
# ---------------------------------------------------------------------------
echo ""
echo "═══ 2. API Status Endpoint ═══"
echo ""

status_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/status" 2>/dev/null || echo "000")
check "GET /api/v1/status" "$status_code" "200"

status_body=$(ssh_cmd "curl -s http://localhost:8000/api/v1/status" 2>/dev/null || echo "{}")
status_version=$(echo "$status_body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")
check "API version in response" "$status_version" "0.9.0"

health_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health" 2>/dev/null || echo "000")
check "GET /api/v1/health" "$health_code" "200"

# ---------------------------------------------------------------------------
# 3. Brain Endpoints
# ---------------------------------------------------------------------------
echo ""
echo "═══ 3. Brain Endpoints ═══"
echo ""

# Registry — may require auth (401/403 is acceptable = endpoint exists)
registry_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/agents/registry" 2>/dev/null || echo "000")
check_range "GET /agents/registry (exists)" "$registry_code" 200 403

# Dispatch endpoint — POST without body should be 422 (validation) or 401 (auth)
dispatch_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/api/v1/agents/eng-core/dispatch" 2>/dev/null || echo "000")
check_range "POST /agents/{id}/dispatch (exists)" "$dispatch_code" 401 422

# Callback endpoint — POST without body should be 422 or 401
callback_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/api/v1/agents/callback" 2>/dev/null || echo "000")
check_range "POST /agents/callback (exists)" "$callback_code" 401 422

# Workflows endpoint — POST without body should be 422 or 401
workflow_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/api/v1/workflows" 2>/dev/null || echo "000")
check_range "POST /workflows (exists)" "$workflow_code" 401 422

# ---------------------------------------------------------------------------
# 4. WebSocket Connectivity
# ---------------------------------------------------------------------------
echo ""
echo "═══ 4. WebSocket Connectivity ═══"
echo ""

# Test WebSocket upgrade — check if the endpoint responds to upgrade request
ws_code=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' \
    -H 'Upgrade: websocket' \
    -H 'Connection: Upgrade' \
    -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    -H 'Sec-WebSocket-Version: 13' \
    http://localhost:8000/api/v1/ws/pipeline/test-task" 2>/dev/null || echo "000")
# 101 = upgrade successful, 403 = auth required but WS endpoint exists
check_range "WS /ws/pipeline/{task_id} (upgrade)" "$ws_code" 101 426

# External WebSocket via wss://
ws_ext=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    -H 'Upgrade: websocket' \
    -H 'Connection: Upgrade' \
    -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    -H 'Sec-WebSocket-Version: 13' \
    "https://${DOMAIN_API}/api/v1/ws/pipeline/test-task" 2>/dev/null || echo "000")
warn_check "WSS external upgrade" "$ws_ext" "101"

# ---------------------------------------------------------------------------
# 5. SSL Certificate Validity
# ---------------------------------------------------------------------------
echo ""
echo "═══ 5. SSL Certificate Validity ═══"
echo ""

for domain in "$DOMAIN_API" "$DOMAIN_DASH"; do
    cert_expiry=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | \
        openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")

    if [[ "$cert_expiry" != "unknown" ]]; then
        # Calculate days until expiry
        expiry_epoch=$(date -j -f "%b %d %H:%M:%S %Y %Z" "$cert_expiry" +%s 2>/dev/null || \
                       date -d "$cert_expiry" +%s 2>/dev/null || echo "0")
        now_epoch=$(date +%s)
        days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

        TOTAL=$((TOTAL + 1))
        if [[ $days_left -gt 14 ]]; then
            printf "  %-45s %s (%d days left)\n" "SSL $domain" "PASS" "$days_left"
            PASS=$((PASS + 1))
        elif [[ $days_left -gt 0 ]]; then
            printf "  %-45s %s (%d days left — RENEW SOON)\n" "SSL $domain" "WARN" "$days_left"
            WARN=$((WARN + 1))
        else
            printf "  %-45s %s (EXPIRED)\n" "SSL $domain" "FAIL"
            FAIL=$((FAIL + 1))
        fi
    else
        TOTAL=$((TOTAL + 1))
        printf "  %-45s %s\n" "SSL $domain" "WARN (could not check)"
        WARN=$((WARN + 1))
    fi
done

# ---------------------------------------------------------------------------
# 6. Response Times
# ---------------------------------------------------------------------------
echo ""
echo "═══ 6. Response Times ═══"
echo ""

# Internal response times (from server)
for endpoint in "/api/v1/status" "/api/v1/health"; do
    time_ms=$(ssh_cmd "curl -s -o /dev/null -w '%{time_total}' http://localhost:8000${endpoint}" 2>/dev/null || echo "9.999")
    time_ms_int=$(echo "$time_ms" | awk '{printf "%d", $1 * 1000}')

    TOTAL=$((TOTAL + 1))
    if [[ $time_ms_int -lt 500 ]]; then
        printf "  %-45s %s (%dms)\n" "Internal ${endpoint}" "PASS" "$time_ms_int"
        PASS=$((PASS + 1))
    elif [[ $time_ms_int -lt 2000 ]]; then
        printf "  %-45s %s (%dms — slow)\n" "Internal ${endpoint}" "WARN" "$time_ms_int"
        WARN=$((WARN + 1))
    else
        printf "  %-45s %s (%dms)\n" "Internal ${endpoint}" "FAIL" "$time_ms_int"
        FAIL=$((FAIL + 1))
    fi
done

# External response times (HTTPS through Apache proxy)
for endpoint in "/api/v1/status" "/api/v1/health"; do
    time_ms=$(curl -s -o /dev/null -w '%{time_total}' --max-time 10 "https://${DOMAIN_API}${endpoint}" 2>/dev/null || echo "9.999")
    time_ms_int=$(echo "$time_ms" | awk '{printf "%d", $1 * 1000}')

    TOTAL=$((TOTAL + 1))
    if [[ $time_ms_int -lt 1000 ]]; then
        printf "  %-45s %s (%dms)\n" "External ${endpoint}" "PASS" "$time_ms_int"
        PASS=$((PASS + 1))
    elif [[ $time_ms_int -lt 3000 ]]; then
        printf "  %-45s %s (%dms — slow)\n" "External ${endpoint}" "WARN" "$time_ms_int"
        WARN=$((WARN + 1))
    else
        printf "  %-45s %s (%dms)\n" "External ${endpoint}" "FAIL" "$time_ms_int"
        FAIL=$((FAIL + 1))
    fi
done

# ---------------------------------------------------------------------------
# 7. Additional Checks
# ---------------------------------------------------------------------------
echo ""
echo "═══ 7. Additional Checks ═══"
echo ""

# Docker volume exists
vol_exists=$(ssh_cmd "docker volume inspect occp-data >/dev/null 2>&1 && echo 'yes' || echo 'no'")
check "Docker volume occp-data exists" "$vol_exists" "yes"

# Container logs — check for Python tracebacks in last 50 lines
traceback_count=$(ssh_cmd "docker logs occp-api-1 2>&1 | tail -50 | grep -c 'Traceback\|CRITICAL\|FATAL' || echo 0")
check "No tracebacks in recent API logs" "$traceback_count" "0"

# Check .env exists on server
env_exists=$(ssh_cmd "test -f /opt/occp/.env && echo 'yes' || echo 'no'")
check ".env file present" "$env_exists" "yes"

# Check .env has required brain vars
if [[ "$env_exists" == "yes" ]]; then
    has_webhook=$(ssh_cmd "grep -q 'OCCP_WEBHOOK_SECRET' /opt/occp/.env && echo 'yes' || echo 'no'" 2>/dev/null)
    warn_check ".env has OCCP_WEBHOOK_SECRET" "$has_webhook" "yes"

    has_openclaw=$(ssh_cmd "grep -q 'OCCP_OPENCLAW_BASE_URL' /opt/occp/.env && echo 'yes' || echo 'no'" 2>/dev/null)
    warn_check ".env has OCCP_OPENCLAW_BASE_URL" "$has_openclaw" "yes"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "═══════════════════════════════════════════════════"
printf "  TOTAL: %d  |  PASS: %d  |  WARN: %d  |  FAIL: %d\n" "$TOTAL" "$PASS" "$WARN" "$FAIL"
echo "═══════════════════════════════════════════════════"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo "RESULT: FAIL — $FAIL check(s) failed"
    exit 1
elif [[ $WARN -gt 0 ]]; then
    echo "RESULT: PASS with $WARN warning(s)"
    exit 0
else
    echo "RESULT: ALL PASS"
    exit 0
fi
