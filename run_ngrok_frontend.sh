#!/bin/bash
# Script to expose the frontend via ngrok

echo "Starting ngrok tunnel for frontend (port 5173)..."
echo "Public URL will be displayed below."
echo ""
echo "Make sure the frontend is running first: ./run_frontend.sh"
echo ""

ngrok http 5173
