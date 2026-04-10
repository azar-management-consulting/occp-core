#!/usr/bin/env bash
# OCCP Brain CloudCode Hook
# Bridges Claude Code CLI hooks to Brian the Brain via HTTP.
#
# Install: Add to .claude/settings.json hooks.UserPromptSubmit
#
# Usage in .claude/settings.json:
# {
#   "hooks": {
#     "UserPromptSubmit": [
#       {
#         "matcher": "Brian:",
#         "command": "bash /Users/air/Desktop/PROJECTEK/OCCP/occp-core/scripts/cloudcode-hook.sh"
#       }
#     ]
#   }
# }

set -euo pipefail

# Configuration (override via env)
OCCP_API_URL="${OCCP_API_URL:-https://api.occp.ai/api/v1}"
OCCP_TOKEN_FILE="${OCCP_TOKEN_FILE:-$HOME/.occp/token}"

# Read stdin (JSON context from Claude Code)
INPUT=$(cat)

# Extract the user prompt from hook JSON payload
PROMPT=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('prompt',''))" 2>/dev/null || echo "")

# Only process if starts with "Brian:"
if [[ ! "$PROMPT" == Brian:* ]]; then
    exit 0
fi

# Strip "Brian:" prefix and trim leading whitespace
COMMAND="${PROMPT#Brian:}"
COMMAND="${COMMAND# }"

if [ -z "$COMMAND" ]; then
    echo "Error: empty command after 'Brian:' prefix" >&2
    exit 1
fi

# Read auth token (optional)
TOKEN=""
if [ -f "$OCCP_TOKEN_FILE" ]; then
    TOKEN=$(cat "$OCCP_TOKEN_FILE")
fi

# Build auth header
AUTH_HEADER=""
if [ -n "$TOKEN" ]; then
    AUTH_HEADER="-H \"Authorization: Bearer $TOKEN\""
fi

# Escape command for JSON (handle quotes and backslashes)
COMMAND_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$COMMAND" 2>/dev/null)

# Send to OCCP Brain API
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${OCCP_API_URL}/cloudcode/command" \
    -H "Content-Type: application/json" \
    ${TOKEN:+-H "Authorization: Bearer $TOKEN"} \
    -d "{
        \"command\": ${COMMAND_JSON},
        \"source\": \"cloudcode\",
        \"hook_type\": \"UserPromptSubmit\",
        \"priority\": \"high\",
        \"cwd\": \"$(pwd)\"
    }" 2>/dev/null) || true

# Split response body and HTTP status
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
    echo "Error: OCCP API returned HTTP $HTTP_CODE" >&2
    echo "$BODY" >&2
    exit 1
fi

# Extract task ID
TASK_ID=$(echo "$BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null || echo "")

if [ -n "$TASK_ID" ]; then
    echo "Brain received task: $TASK_ID"
    echo "  Poll: curl -s ${OCCP_API_URL}/cloudcode/tasks/$TASK_ID"
else
    echo "Warning: no task_id in response" >&2
    echo "$BODY"
fi
