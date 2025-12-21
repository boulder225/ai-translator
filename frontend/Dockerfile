# Frontend Dockerfile for DigitalOcean App Platform
# This is used if you want to deploy frontend as a container
# Alternative: Use static site deployment (recommended for React/Vite)

FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy source files
COPY . .

# Build the application
# VITE_API_URL will be set at build time by App Platform
RUN npm run build

# Production stage with Nginx
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration for API proxying
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Nginx will serve static files
CMD ["nginx", "-g", "daemon off;"]
