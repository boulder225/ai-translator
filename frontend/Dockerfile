# Frontend Dockerfile for DigitalOcean App Platform
# Build context is repository root, so we need to copy from frontend/ directory

FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files from frontend directory
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy source files from frontend directory
COPY frontend/ .

# Build the application
# VITE_API_URL will be set at build time by App Platform
# Note: Vite only exposes env vars prefixed with VITE_ to the client
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# Production stage with Nginx
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration for API proxying
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Nginx will serve static files
CMD ["nginx", "-g", "daemon off;"]
