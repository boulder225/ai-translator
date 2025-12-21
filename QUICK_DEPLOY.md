# Quick Deployment Guide - DigitalOcean

## 🚀 Fastest Path: App Platform (5 minutes)

### Step 1: Prepare Your Code

```bash
# 1. Make sure your code is committed
git add .
git commit -m "Ready for deployment"
git push origin main

# 2. Update .do/app.yaml with your GitHub repo URL
# Edit .do/app.yaml and replace "your-username/your-repo-name" with your actual repo
```

### Step 2: Deploy on DigitalOcean

1. **Go to DigitalOcean**: https://cloud.digitalocean.com
2. **Click "Apps" → "Create App"**
3. **Connect GitHub** and select your repository
4. **DigitalOcean will auto-detect** `.do/app.yaml` configuration
5. **Add Environment Variables**:
   - Click **"Edit"** next to "App-Level Environment Variables"
   - Click **"+ Add Variable"** for each:
     - `ANTHROPIC_API_KEY` = `your_actual_api_key` (⚠️ **Toggle "Encrypt" or "Secret"**)
     - `DATA_ROOT` = `/app/data`
     - `DEFAULT_SOURCE_LANG` = `fr`
     - `DEFAULT_TARGET_LANG` = `it`
   - Click **"Save"**
6. **Click "Create Resources"**
7. **Wait 5-10 minutes** for deployment

**📖 Detailed instructions:** See `SET_ENV_VARS.md` for step-by-step guide

### Step 3: Update Frontend API URL

After deployment, update `frontend/src/services/api.js`:

```javascript
// Change from:
const API_BASE_URL = '/api';

// To (use your App Platform backend URL):
const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://backend-lexdeep-translator-xxxxx.ondigitalocean.app';
```

Or add `VITE_API_URL` environment variable in App Platform frontend settings.

### Step 4: Update CORS

Update `src/translator/api.py` CORS settings to include your App Platform URLs:

```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "https://frontend-lexdeep-translator-xxxxx.ondigitalocean.app",
],
allow_origin_regex=r"https://.*\.ondigitalocean\.app",
```

---

## 🖥️ Alternative: Droplet Deployment (15 minutes)

### Step 1: Create Droplet

1. **DigitalOcean** → **Droplets** → **Create Droplet**
2. **Ubuntu 22.04 LTS**, **Basic $6/month** plan
3. **Create Droplet**

### Step 2: Deploy

```bash
# SSH into your droplet
ssh root@your-droplet-ip

# Download and run deployment script
curl -o deploy-droplet.sh https://raw.githubusercontent.com/your-username/your-repo/main/deploy-droplet.sh
chmod +x deploy-droplet.sh

# Set your repository URL and API key
export REPO_URL="https://github.com/your-username/your-repo.git"
export ANTHROPIC_API_KEY="your-api-key-here"

# Run deployment
./deploy-droplet.sh
```

### Step 3: Access Your App

Visit: `http://your-droplet-ip`

---

## ✅ Post-Deployment Checklist

- [ ] Backend is responding: `curl https://your-backend-url/`
- [ ] Frontend loads without errors
- [ ] Can upload a test document
- [ ] Translation completes successfully
- [ ] CORS is configured correctly
- [ ] Environment variables are set

---

## 🆘 Troubleshooting

**Backend not starting?**
- Check logs: App Platform → Runtime Logs, or Droplet → `journalctl -u lexdeep-backend -f`
- Verify `ANTHROPIC_API_KEY` is set correctly

**Frontend can't connect?**
- Check CORS settings in `api.py`
- Verify frontend API URL is correct
- Check browser console for errors

**Need help?**
- See full guide: `DEPLOYMENT_DIGITALOCEAN.md`
- DigitalOcean Docs: https://docs.digitalocean.com
