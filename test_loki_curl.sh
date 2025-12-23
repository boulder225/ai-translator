#!/bin/bash
# Test script for Loki authentication using curl with current timestamp

# Set your credentials here
LOKI_URL="${LOKI_URL:-https://logs-prod-039.grafana.net/loki/api/v1/push}"
LOKI_USERNAME="${LOKI_USERNAME:-1435429}"
LOKI_PASSWORD="${LOKI_PASSWORD:-your-token-here}"

# Get current timestamp in nanoseconds (Loki requires current timestamps)
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1_000_000_000))" 2>/dev/null || date +%s)000000000

echo "Testing Loki authentication..."
echo "URL: $LOKI_URL"
echo "Username: $LOKI_USERNAME"
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
    echo "   Check:"
    echo "   1. Token has 'logs:write' scope in Access Policies"
    echo "   2. Username is correct (try Loki Instance ID)"
    echo "   3. Token is correct"
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
