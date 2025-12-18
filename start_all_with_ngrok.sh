#!/bin/bash
# Script to start backend, frontend, and ngrok tunnel

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Starting Legal Translator Services + ngrok"
echo "=========================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID $NGROK_PID 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start backend API
echo "1. Starting backend API on port 8000..."
mkdir -p logs
source .venv/bin/activate
uvicorn src.translator.api:app --host 0.0.0.0 --port 8000 --reload > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend started (PID: $BACKEND_PID)"
sleep 2

# Start frontend
echo "2. Starting frontend on port 5173..."
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "   Frontend started (PID: $FRONTEND_PID)"
sleep 3

# Start ngrok tunnel to frontend
echo "3. Starting ngrok tunnel for frontend..."
sleep 2
ngrok http 5173 > logs/ngrok.log 2>&1 &
NGROK_PID=$!
echo "   Ngrok started (PID: $NGROK_PID)"
sleep 3

echo ""
echo "=========================================="
echo "All services started!"
echo "=========================================="
echo ""
echo "Backend API:  http://127.0.0.1:8000"
echo "Frontend:     http://localhost:5173"
echo ""
echo "Fetching ngrok public URL..."
sleep 3

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else 'Starting...')" 2>/dev/null || echo "Starting...")

echo "Public URL:   $NGROK_URL"
echo ""
echo "Ngrok dashboard: http://localhost:4040"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for all processes
wait
