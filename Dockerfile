# Backend Dockerfile for DigitalOcean App Platform
# App Platform will auto-detect this Dockerfile and use it for deployment

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files and README (needed for pyproject.toml)
COPY pyproject.toml README.md ./

# Copy prompt.md (custom translation prompt)
COPY prompt.md ./

# Copy source directory structure
COPY src/ ./src/

# Install Python dependencies (after copying src directory)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Create data directory for file uploads and translation memory
RUN mkdir -p /app/data && \
    chmod 755 /app/data

# Expose port (App Platform will set PORT env var, default to 8080)
EXPOSE 8080

# Use PORT environment variable if set, otherwise default to 8080
ENV PORT=8080

# Health check for App Platform
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/')" || exit 1

# Run the application
# App Platform will override PORT env var, so we use it here
CMD uvicorn src.translator.api:app --host 0.0.0.0 --port ${PORT}
