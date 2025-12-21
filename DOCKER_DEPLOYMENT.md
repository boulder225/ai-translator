# Docker Deployment Guide for DigitalOcean App Platform

This guide shows you how to dockerize your application for auto-deployment on DigitalOcean App Platform.

---

## ✅ Why Dockerize?

1. **Auto-Detection**: App Platform automatically detects `Dockerfile` in your repo
2. **Reproducible**: Same environment locally and in production
3. **Portable**: Can deploy to any Docker-compatible platform
4. **Isolated**: No conflicts with system dependencies
5. **Version Control**: Dockerfile is versioned with your code

---

## 📁 Files Created

1. **`Dockerfile`** - Backend container (auto-detected by App Platform)
2. **`frontend/Dockerfile`** - Frontend container (optional, static site is better)
3. **`.dockerignore`** - Excludes unnecessary files from build
4. **`docker-compose.yml`** - For local testing (already exists)

---

## 🚀 Quick Start

### Step 1: Commit Docker Files

```bash
git add Dockerfile .dockerignore frontend/Dockerfile
git commit -m "Add Docker configuration for App Platform"
git push origin main
```

### Step 2: Deploy on DigitalOcean

1. **Go to DigitalOcean**: https://cloud.digitalocean.com
2. **Apps** → **Create App**
3. **Connect GitHub** → Select your repository
4. **App Platform will auto-detect** the `Dockerfile`
5. **Configure**:
   - **Service Name**: `backend`
   - **Type**: Web Service (Docker)
   - **Source Directory**: `/` (root)
   - **Dockerfile Path**: `Dockerfile` (auto-detected)
   - **HTTP Port**: `8080` (or use `$PORT` env var)

6. **Add Environment Variables**:
   - `ANTHROPIC_API_KEY` (SECRET)
   - `DATA_ROOT` = `/app/data`
   - `DEFAULT_SOURCE_LANG` = `fr`
   - `DEFAULT_TARGET_LANG` = `it`
   - `PORT` = `8080` (App Platform sets this automatically)

7. **Click "Create Resources"**

### Step 3: Frontend (Static Site - Recommended)

For React/Vite apps, **static site deployment is better** than Docker:

1. **Add Static Site Component**:
   - **Name**: `frontend`
   - **Type**: Static Site
   - **Source Directory**: `/frontend`
   - **Build Command**: `npm install && npm run build`
   - **Output Directory**: `dist`

2. **Add Build-Time Environment Variable**:
   - `VITE_API_URL` = `https://backend-${_APP_NAME}.ondigitalocean.app`

---

## 🧪 Test Locally

### Option 1: Docker Compose (Recommended)

```bash
# Build and run both services
docker-compose up --build

# Backend: http://localhost:8000
# Frontend: http://localhost:80
```

### Option 2: Individual Docker Commands

```bash
# Build backend image
docker build -t lexdeep-backend .

# Run backend
docker run -p 8000:8080 \
  -e ANTHROPIC_API_KEY=your_key \
  -e DATA_ROOT=/app/data \
  lexdeep-backend

# Build frontend (if using container)
cd frontend
docker build -t lexdeep-frontend .
docker run -p 80:80 lexdeep-frontend
```

---

## 📋 Dockerfile Explanation

### Backend Dockerfile (`Dockerfile`)

```dockerfile
FROM python:3.11-slim          # Base image
WORKDIR /app                   # Working directory
RUN apt-get update...          # Install system deps for PDF processing
COPY pyproject.toml ./        # Copy dependencies first (caching)
RUN pip install -e .          # Install Python packages
COPY src/ ./src/              # Copy application code
RUN mkdir -p /app/data        # Create data directory
EXPOSE 8080                    # Expose port
CMD uvicorn ...                # Run command
```

**Key Points:**
- Uses `python:3.11-slim` for smaller image size
- Installs system dependencies for PDF processing
- Copies dependencies first for better Docker layer caching
- Uses `$PORT` environment variable (App Platform sets this)
- Includes health check for App Platform monitoring

### Frontend Dockerfile (`frontend/Dockerfile`)

**Note**: For React/Vite apps, **static site deployment is recommended** over Docker.

If you use Docker:
- Multi-stage build (Node for build, Nginx for serving)
- Smaller production image
- But static site is simpler and faster

---

## 🔧 Configuration

### Environment Variables

Set these in App Platform dashboard:

| Variable | Value | Notes |
|----------|-------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | **Mark as SECRET** |
| `DATA_ROOT` | `/app/data` | Data directory |
| `DEFAULT_SOURCE_LANG` | `fr` | Default source language |
| `DEFAULT_TARGET_LANG` | `it` | Default target language |
| `PORT` | `8080` | Auto-set by App Platform |

### Port Configuration

App Platform automatically sets `PORT` environment variable. The Dockerfile uses:
```dockerfile
ENV PORT=8080
CMD uvicorn src.translator.api:app --host 0.0.0.0 --port ${PORT}
```

This ensures compatibility with App Platform's port assignment.

---

## 🐛 Troubleshooting

### Build Fails

**Error**: `ModuleNotFoundError` or `pip install` fails
- **Fix**: Check `pyproject.toml` dependencies are correct
- **Fix**: Ensure `Dockerfile` copies `pyproject.toml` before installing

**Error**: `COPY failed: file not found`
- **Fix**: Check `.dockerignore` isn't excluding needed files
- **Fix**: Verify file paths in `Dockerfile` are correct

### Container Won't Start

**Error**: `Port already in use`
- **Fix**: App Platform sets `PORT` automatically, don't hardcode it

**Error**: `Permission denied` on `/app/data`
- **Fix**: Dockerfile already sets permissions with `chmod 755`

### App Platform Auto-Detection

**Issue**: App Platform doesn't detect Dockerfile
- **Fix**: Ensure `Dockerfile` is in repository root
- **Fix**: Check file is committed and pushed to GitHub
- **Fix**: Manually select "Docker" as build type in App Platform

---

## 📊 Image Size Optimization

Current Dockerfile optimizations:

1. ✅ Uses `python:3.11-slim` (smaller than full Python image)
2. ✅ Removes apt cache (`rm -rf /var/lib/apt/lists/*`)
3. ✅ Uses `--no-cache-dir` for pip
4. ✅ Multi-stage build for frontend (if used)
5. ✅ `.dockerignore` excludes unnecessary files

**Current size**: ~200-300MB (backend)

---

## 🔄 CI/CD Integration

### GitHub Actions (Optional)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to DigitalOcean

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to App Platform
        uses: digitalocean/app_action@v1
        with:
          app_name: lexdeep-translator
          token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
```

**Note**: App Platform auto-deploys on push, so this is optional.

---

## ✅ Checklist

Before deploying:

- [ ] `Dockerfile` is in repository root
- [ ] `.dockerignore` excludes unnecessary files
- [ ] Dockerfile uses `$PORT` environment variable
- [ ] Environment variables are configured in App Platform
- [ ] Tested locally with `docker-compose up`
- [ ] Code is pushed to GitHub
- [ ] App Platform is connected to repository

---

## 📚 Additional Resources

- [DigitalOcean Docker Deployment](https://docs.digitalocean.com/products/app-platform/how-to/use-dockerfile/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Docker Guide](https://fastapi.tiangolo.com/deployment/docker/)

---

## 🎯 Next Steps

1. ✅ Commit Docker files to GitHub
2. ✅ Create App Platform app
3. ✅ Configure environment variables
4. ✅ Deploy and test
5. ✅ Monitor logs and performance

For detailed App Platform setup, see `DEPLOYMENT_DIGITALOCEAN.md`.
