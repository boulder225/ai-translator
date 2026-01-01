#!/bin/bash
# Quick test script to build and run Docker container in background

set -e

echo "Building Docker image..."
docker build -f frontend/Dockerfile -t legal-translator:local . || {
    echo "Build failed!"
    exit 1
}

echo ""
echo "Stopping any existing container..."
docker stop legal-translator-local 2>/dev/null || true
docker rm legal-translator-local 2>/dev/null || true

echo ""
echo "Starting container in background..."

# Load ANTHROPIC_API_KEY from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep ANTHROPIC_API_KEY | xargs)
fi

docker run -d \
    -p 8080:80 \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e CORS_ORIGINS="*" \
    --name legal-translator-local \
    legal-translator:local

echo ""
echo "Container started! Waiting for services to be ready..."
sleep 5

echo ""
echo "Testing health endpoint..."
curl -f http://localhost:8080/api/health && echo " ✓ Health check passed" || echo " ✗ Health check failed"

echo ""
echo "Container is running!"
echo "Frontend: http://localhost:8080"
echo "API: http://localhost:8080/api"
echo ""
echo "To view logs: docker logs -f legal-translator-local"
echo "To stop: docker stop legal-translator-local"
