#!/bin/bash
# Script to view server logs

LOG_DIR="$(dirname "$0")/logs"

echo "=== Backend API Logs ==="
echo ""
if [ -f "$LOG_DIR/backend.log" ]; then
    tail -n 50 "$LOG_DIR/backend.log"
else
    echo "No backend log file found. Start the server with run_api.sh to generate logs."
fi

echo ""
echo "=== Frontend Logs ==="
echo ""
if [ -f "$LOG_DIR/frontend.log" ]; then
    tail -n 50 "$LOG_DIR/frontend.log"
else
    echo "No frontend log file found. Start the server with run_frontend.sh to generate logs."
fi

echo ""
echo "=== To follow logs in real-time, run: ==="
echo "  tail -f $LOG_DIR/backend.log"
echo "  tail -f $LOG_DIR/frontend.log"



