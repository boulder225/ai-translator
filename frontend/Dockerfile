# Multi-stage build for legal translator app
# This Dockerfile is in frontend/ but expects build context to be the repository root

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend files
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build && \
    echo "Build completed. Contents of dist:" && \
    ls -la dist/ && \
    echo "Checking for index.html:" && \
    test -f dist/index.html && echo "index.html found" || echo "ERROR: index.html not found"

# Stage 2: Python backend
FROM python:3.11-slim AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy frontend build from builder stage
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Remove default nginx sites and ensure only our config is used
RUN rm -rf /etc/nginx/sites-enabled/* && \
    rm -f /etc/nginx/sites-available/default && \
    rm -f /etc/nginx/conf.d/default.conf && \
    # Comment out sites-enabled include in main nginx.conf to avoid conflicts
    sed -i 's|include /etc/nginx/sites-enabled/\*;|# include /etc/nginx/sites-enabled/*;|g' /etc/nginx/nginx.conf && \
    # Remove any existing daemon directive and add our own
    sed -i '/^daemon /d' /etc/nginx/nginx.conf && \
    echo "daemon off;" >> /etc/nginx/nginx.conf
COPY frontend/nginx.conf /etc/nginx/conf.d/app.conf

# Verify frontend files are present and set correct permissions
RUN chmod -R 755 /usr/share/nginx/html && \
    ls -la /usr/share/nginx/html/ && \
    test -f /usr/share/nginx/html/index.html && echo "✓ index.html found" || echo "✗ ERROR: index.html not found"

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/glossary

# Copy glossary and data files
COPY glossary/ /app/glossary/
COPY data/ /app/data/
COPY prompt*.md /app/

# Expose port
EXPOSE 80

# Copy startup script
COPY docker-start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ANTHROPIC_API_KEY=""

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost/api/health > /dev/null 2>&1 || exit 1

# Start services
CMD ["/app/start.sh"]
