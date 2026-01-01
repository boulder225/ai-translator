#!/bin/bash
# Build and run the Docker container locally for testing

set -e

echo "Building Docker image..."
docker build -f frontend/Dockerfile -t legal-translator:local .

echo ""
echo "Building complete! Starting container..."
echo ""

# Check if .env file exists and load ANTHROPIC_API_KEY
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep ANTHROPIC_API_KEY | xargs)
    echo "Loaded ANTHROPIC_API_KEY from .env"
else
    echo "Warning: .env file not found. Set ANTHROPIC_API_KEY environment variable."
fi

# Run the container
docker run -it --rm \
    -p 8080:80 \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e CORS_ORIGINS="*" \
    --name legal-translator-local \
    legal-translator:local
