#!/bin/bash
# Script to expose the backend API via ngrok

echo "Starting ngrok tunnel for backend API (port 8000)..."
echo "Public URL will be displayed below."
echo ""
echo "Make sure the backend API is running first: ./run_api.sh"
echo "CORS is already configured to allow ngrok domains."
echo ""

ngrok http 8000
