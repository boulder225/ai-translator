#!/bin/bash
# Quick test script for local Docker deployment

echo "=========================================="
echo "Testing LexDeep Local Deployment"
echo "=========================================="
echo ""

echo "1. Checking containers..."
docker ps --filter "name=lexdeep" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

echo "2. Testing backend API..."
curl -s http://localhost:8000/ | python3 -m json.tool
echo ""

echo "3. Checking custom prompt..."
PROMPT_LEN=$(curl -s http://localhost:8000/api/prompt | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('prompt', '')))" 2>/dev/null || echo "0")
if [ "$PROMPT_LEN" -gt "1000" ]; then
    echo "✅ Custom prompt loaded ($PROMPT_LEN characters)"
else
    echo "❌ Custom prompt NOT loaded (length: $PROMPT_LEN)"
fi
echo ""

echo "4. Testing frontend..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/)
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "✅ Frontend accessible (HTTP $FRONTEND_STATUS)"
else
    echo "❌ Frontend not accessible (HTTP $FRONTEND_STATUS)"
fi
echo ""

echo "5. Testing API proxy through frontend..."
curl -s http://localhost/api/glossaries | python3 -m json.tool
echo ""

echo "=========================================="
echo "✅ Testing complete!"
echo "=========================================="
echo ""
echo "Access your app at: http://localhost"
echo "Backend API: http://localhost:8000"
echo ""
