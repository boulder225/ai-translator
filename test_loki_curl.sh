#!/bin/bash
# Test script for Loki authentication using curl with current timestamp

# Load .env file if it exists (same directory as script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/.env" ]; then
    # Source .env file (simple key=value format)
    set -a
    source "${SCRIPT_DIR}/.env"
    set +a
    echo "✅ Loaded .env file"
fi

# Set your credentials here (or export as environment variables)
LOKI_URL="${LOKI_URL:-https://logs-prod-039.grafana.net/loki/api/v1/push}"
LOKI_USERNAME="${LOKI_USERNAME:-1435429}"
LOKI_PASSWORD="${LOKI_PASSWORD:-}"

# Check if password is set
if [ -z "$LOKI_PASSWORD" ] || [ "$LOKI_PASSWORD" = "your-token-here" ]; then
    echo "❌ Error: LOKI_PASSWORD not set!"
    echo ""
    echo "Options:"
    echo "  1. Set environment variable:"
    echo "     export LOKI_PASSWORD='glc_your-token-here'"
    echo ""
    echo "  2. Add to .env file (in same directory as this script):"
    echo "     LOKI_PASSWORD=glc_your-token-here"
    echo ""
    echo "  3. Edit this script to set it directly"
    exit 1
fi

# Get current timestamp in nanoseconds (Loki requires current timestamps)
# Python method (preferred): multiply seconds by 1 billion
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1_000_000_000))" 2>/dev/null)
if [ -z "$TIMESTAMP" ]; then
    # Fallback: date gives seconds, append 9 zeros for nanoseconds
    SECONDS=$(date +%s)
    TIMESTAMP="${SECONDS}000000000"
fi

echo "Testing Loki authentication..."
echo "URL: $LOKI_URL"
echo "Username: $LOKI_USERNAME"
echo "Password: ${LOKI_PASSWORD:0:10}... (${#LOKI_PASSWORD} chars)"
echo "Timestamp: $TIMESTAMP"
echo ""

# Test the connection
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
  -u "${LOKI_USERNAME}:${LOKI_PASSWORD}" \
  -X POST "${LOKI_URL}" \
  -H 'Content-Type: application/json' \
  -d "{\"streams\": [{\"stream\": {\"job\": \"test\", \"service\": \"loki-test\"}, \"values\": [[\"${TIMESTAMP}\", \"Test log from curl script - $(date)\"]]}]}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "Response:"
echo "$BODY"
echo ""
echo "HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Success! Logs sent to Loki"
    echo "   Check Grafana Cloud → Explore → Loki"
    echo "   Query: {job=\"test\"}"
elif [ "$HTTP_CODE" = "401" ]; then
    echo "❌ Authentication failed (401)"
    if echo "$BODY" | grep -q "invalid token"; then
        echo "   Error: 'invalid token'"
        echo "   → Token might be expired or incorrect"
        echo "   → Generate a new token from Access Policies"
    elif echo "$BODY" | grep -q "invalid scope"; then
        echo "   Error: 'invalid scope'"
        echo "   → Token missing 'logs:write' permission"
    else
        echo "   Check:"
        echo "   1. Token has 'logs:write' scope in Access Policies"
        echo "   2. Username is correct (try Loki Instance ID instead of User ID)"
        echo "   3. Token is correct (starts with 'glc_')"
        echo "   4. Token is from Access Policy (not API Keys)"
    fi
elif echo "$BODY" | grep -q "invalid scope"; then
    echo "❌ Invalid scope - token missing 'logs:write' permission"
    echo "   → Create Access Policy with 'logs:write' scope"
    echo "   → Generate token from that policy"
elif echo "$BODY" | grep -q "timestamp too old"; then
    echo "❌ Timestamp too old"
    echo "   → Check system clock is correct"
    echo "   → Timestamp used: $TIMESTAMP"
else
    echo "❌ Error: $BODY"
fi
