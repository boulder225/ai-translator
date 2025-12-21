# Testing Locally with Docker

This guide shows you how to test your LexDeep application locally using Docker.

---

## Quick Start

### 1. Start All Services

```bash
cd /Users/enrico/workspace/translator
docker-compose -f docker-compose.local.yml up -d
```

This starts:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost

### 2. Check Services Are Running

```bash
docker ps
```

You should see:
- `translator-backend-1` on port 8000
- `translator-frontend-1` on port 80

### 3. Access the Web App

Open your browser:
```
http://localhost
```

---

## Testing Steps

### Test 1: Backend API Health

```bash
# Test root endpoint
curl http://localhost:8000/

# Should return: {"message":"Legal Translator API","version":"0.1.0"}
```

### Test 2: Custom Prompt Loading

```bash
# Check if custom prompt is loaded
curl http://localhost:8000/api/prompt | python3 -m json.tool | head -20

# Should show your custom prompt starting with "# PROMPT GPT LEGALE"
```

### Test 3: Frontend Access

```bash
# Test frontend HTML
curl http://localhost/ | head -10

# Should return HTML with React app
```

### Test 4: API Proxy Through Frontend

```bash
# Test API through frontend proxy
curl http://localhost/api/glossaries

# Should return: {"glossaries":[]}
```

### Test 5: Full Translation Flow

1. **Open browser**: http://localhost
2. **Upload a test document** (PDF, DOCX, or TXT)
3. **Select languages** (e.g., French → Italian)
4. **Click "Translate Document"**
5. **Wait for translation** (check progress)
6. **Download translated PDF**

---

## Viewing Logs

### Backend Logs

```bash
# View all logs
docker logs translator-backend-1

# Follow logs in real-time
docker logs -f translator-backend-1

# Last 50 lines
docker logs --tail 50 translator-backend-1
```

### Frontend Logs

```bash
# View all logs
docker logs translator-frontend-1

# Follow logs in real-time
docker logs -f translator-frontend-1
```

### Check Prompt Loading

```bash
# Look for prompt loading message
docker logs translator-backend-1 | grep -i prompt

# Should show: [prompt] Loaded custom prompt template from /app/prompt.md
```

---

## Rebuilding After Changes

### Rebuild Backend

```bash
# Rebuild backend (after code changes)
docker-compose -f docker-compose.local.yml build backend

# Restart backend
docker-compose -f docker-compose.local.yml up -d backend
```

### Rebuild Frontend

```bash
# Rebuild frontend (after frontend changes)
docker-compose -f docker-compose.local.yml build frontend

# Restart frontend
docker-compose -f docker-compose.local.yml up -d frontend
```

### Rebuild Everything

```bash
# Rebuild all services
docker-compose -f docker-compose.local.yml build

# Restart all services
docker-compose -f docker-compose.local.yml up -d
```

---

## Environment Variables

### Set API Key

Before starting, set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=your_actual_api_key_here
docker-compose -f docker-compose.local.yml up -d
```

Or create a `.env` file in the project root:

```bash
echo "ANTHROPIC_API_KEY=your_actual_api_key_here" > .env
docker-compose -f docker-compose.local.yml up -d
```

**Note**: `.env` is gitignored, so it won't be committed.

---

## Common Issues & Solutions

### Issue: Port Already in Use

**Error**: `Bind for 0.0.0.0:80 failed: port is already allocated`

**Solution**:
```bash
# Find what's using port 80
lsof -i :80

# Or change port in docker-compose.local.yml
# Change "80:80" to "3000:80" for frontend
```

### Issue: Backend Not Starting

**Check logs**:
```bash
docker logs translator-backend-1
```

**Common causes**:
- Missing `ANTHROPIC_API_KEY` → Set environment variable
- Port conflict → Check if port 8000 is in use
- Build error → Rebuild: `docker-compose -f docker-compose.local.yml build backend`

### Issue: Frontend Can't Connect to Backend

**Check**:
1. Backend is running: `docker ps | grep backend`
2. Backend is healthy: `curl http://localhost:8000/`
3. Nginx config: `docker exec translator-frontend-1 cat /etc/nginx/conf.d/default.conf`

**Fix**: Restart frontend:
```bash
docker-compose -f docker-compose.local.yml restart frontend
```

### Issue: Prompt Not Loading

**Check**:
```bash
# Verify prompt.md is in container
docker exec translator-backend-1 ls -la /app/prompt.md

# Check logs for prompt loading
docker logs translator-backend-1 | grep -i prompt

# Rebuild if needed
docker-compose -f docker-compose.local.yml build backend
docker-compose -f docker-compose.local.yml up -d backend
```

---

## Stopping Services

### Stop All Services

```bash
docker-compose -f docker-compose.local.yml stop
```

### Stop and Remove Containers

```bash
docker-compose -f docker-compose.local.yml down
```

### Stop and Remove Everything (including volumes)

```bash
docker-compose -f docker-compose.local.yml down -v
```

---

## Testing Checklist

- [ ] Backend responds: `curl http://localhost:8000/`
- [ ] Custom prompt loaded: Check logs for `[prompt] Loaded custom prompt template`
- [ ] Frontend loads: `curl http://localhost/` returns HTML
- [ ] API proxy works: `curl http://localhost/api/glossaries`
- [ ] Can upload document in browser
- [ ] Translation completes successfully
- [ ] Can download translated PDF

---

## Quick Test Script

Save this as `test-local.sh`:

```bash
#!/bin/bash
echo "Testing LexDeep Local Deployment..."
echo ""

echo "1. Testing backend..."
curl -s http://localhost:8000/ | python3 -m json.tool
echo ""

echo "2. Testing prompt loading..."
docker logs translator-backend-1 2>&1 | grep -i "prompt\|Loaded custom" | tail -1
echo ""

echo "3. Testing frontend..."
curl -s -I http://localhost/ | head -1
echo ""

echo "4. Testing API proxy..."
curl -s http://localhost/api/glossaries | python3 -m json.tool
echo ""

echo "Done! Open http://localhost in your browser"
```

Make it executable:
```bash
chmod +x test-local.sh
./test-local.sh
```

---

## Next Steps

After local testing works:
1. ✅ Commit and push changes
2. ✅ Deploy to DigitalOcean App Platform
3. ✅ Test production deployment
4. ✅ Monitor logs in App Platform dashboard
