# DigitalOcean Deployment Guide - LexDeep Legal Translator

This guide walks you through deploying the LexDeep application on DigitalOcean using **App Platform** (recommended for MVP) or **Droplets** (for more control).

## Quick Start

**Fastest Path (5 minutes):**
1. Push code to GitHub
2. Use DigitalOcean App Platform (see Option 1)
3. Connect repository and deploy

**More Control (15 minutes):**
1. Create a Droplet
2. Run `deploy-droplet.sh` script
3. Configure domain (optional)

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Option 1: App Platform (Recommended)](#option-1-app-platform-recommended)
3. [Option 2: Droplet Deployment](#option-2-droplet-deployment)
4. [Post-Deployment Configuration](#post-deployment-configuration)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- ✅ DigitalOcean account ([sign up here](https://www.digitalocean.com))
- ✅ GitHub/GitLab/Bitbucket account (for code repository)
- ✅ Your code pushed to a Git repository
- ✅ `ANTHROPIC_API_KEY` ready
- ✅ Domain name (optional, but recommended)

---

## Option 1: App Platform (Recommended)

**Best for**: Quick deployment, automatic scaling, managed infrastructure  
**Cost**: ~$12-25/month (Basic plan)

### Step 1: Prepare Your Repository

1. **Push your code to GitHub/GitLab/Bitbucket**
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

2. **Create `.do/app.yaml`** (see below for content)

### Step 2: Create App Platform Application

1. **Log in to DigitalOcean**
   - Go to https://cloud.digitalocean.com
   - Navigate to **Apps** → **Create App**

2. **Connect Repository**
   - Choose your Git provider (GitHub/GitLab/Bitbucket)
   - Select your repository
   - Choose the branch (usually `main` or `master`)

3. **Configure Backend Service**
   - **Name**: `backend` or `api`
   - **Type**: Web Service
   - **Source Directory**: `/` (root)
   - **Build Command**: 
     ```bash
     pip install -e .
     ```
   - **Run Command**: 
     ```bash
     uvicorn src.translator.api:app --host 0.0.0.0 --port $PORT
     ```
   - **Environment**: Python
   - **Python Version**: 3.11
   - **HTTP Port**: `$PORT` (App Platform sets this automatically)

4. **Configure Frontend Service**
   - **Name**: `frontend`
   - **Type**: Static Site
   - **Source Directory**: `/frontend`
   - **Build Command**: 
     ```bash
     npm install && npm run build
     ```
   - **Output Directory**: `dist`

5. **Set Environment Variables** (for backend service)
   - `ANTHROPIC_API_KEY`: Your Anthropic API key
   - `DATA_ROOT`: `/app/data` (or leave default)
   - `DEFAULT_SOURCE_LANG`: `fr` (or your default)
   - `DEFAULT_TARGET_LANG`: `it` (or your default)
   - `PORT`: `$PORT` (automatically set by App Platform)

6. **Configure Routes**
   - Frontend: `/` → `frontend` service
   - Backend API: `/api/*` → `backend` service

7. **Review and Deploy**
   - Review your configuration
   - Click **Create Resources**
   - Wait for deployment (5-10 minutes)

### Step 3: Update Frontend API Configuration

After deployment, update `frontend/src/services/api.js` to use your production API URL:

```javascript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://your-backend-app.ondigitalocean.app';
```

Or configure it via environment variable in App Platform:
- Add `VITE_API_URL` to frontend environment variables

---

## Option 2: Droplet Deployment

**Best for**: Full control, custom configurations, lower cost  
**Cost**: ~$6-12/month (Basic Droplet)

### Step 1: Create Droplet

1. **Create a Droplet**
   - Go to **Droplets** → **Create Droplet**
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic ($6/month minimum, 1GB RAM recommended)
   - **Region**: Choose closest to your users
   - **Authentication**: SSH keys (recommended) or password
   - Click **Create Droplet**

2. **SSH into Droplet**
   ```bash
   ssh root@your-droplet-ip
   ```

### Step 2: Install Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Python 3.11
apt install -y python3.11 python3.11-venv python3-pip

# Install Node.js 18+ (for frontend build)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Install Nginx (reverse proxy)
apt install -y nginx

# Install Git
apt install -y git

# Install system dependencies for PDF processing
apt install -y build-essential libffi-dev libssl-dev
```

### Step 3: Clone and Setup Application

```bash
# Create app directory
mkdir -p /opt/lexdeep
cd /opt/lexdeep

# Clone your repository
git clone https://github.com/your-username/your-repo.git .

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e .

# Install frontend dependencies and build
cd frontend
npm install
npm run build
cd ..
```

### Step 4: Configure Environment Variables

```bash
# Create .env file
cat > .env << EOF
ANTHROPIC_API_KEY=your_api_key_here
DATA_ROOT=/opt/lexdeep/data
DEFAULT_SOURCE_LANG=fr
DEFAULT_TARGET_LANG=it
EOF

# Create data directory
mkdir -p data
```

### Step 5: Create Systemd Service for Backend

```bash
cat > /etc/systemd/system/lexdeep-backend.service << EOF
[Unit]
Description=LexDeep Backend API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lexdeep
Environment="PATH=/opt/lexdeep/.venv/bin"
ExecStart=/opt/lexdeep/.venv/bin/uvicorn src.translator.api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable lexdeep-backend
systemctl start lexdeep-backend
```

### Step 6: Configure Nginx

```bash
cat > /etc/nginx/sites-available/lexdeep << EOF
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Frontend
    location / {
        root /opt/lexdeep/frontend/dist;
        try_files \$uri \$uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/lexdeep /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test and reload Nginx
nginx -t
systemctl restart nginx
```

### Step 7: Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### Step 8: Setup SSL (Optional but Recommended)

```bash
# Install Certbot
apt install -y certbot python3-certbot-nginx

# Get SSL certificate
certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal is set up automatically
```

---

## Post-Deployment Configuration

### 1. Update CORS Settings

If using App Platform, update `src/translator/api.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://your-frontend-app.ondigitalocean.app",  # Add your App Platform URL
    ],
    allow_origin_regex=r"https://.*\.ondigitalocean\.app",  # Allow all App Platform URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Update Frontend API Base URL

In `frontend/src/services/api.js`, ensure it uses the production API URL:

```javascript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://your-backend-app.ondigitalocean.app';
```

### 3. Test Deployment

1. **Test Backend**
   ```bash
   curl https://your-backend-app.ondigitalocean.app/
   # Should return: {"message":"Legal Translator API","version":"0.1.0"}
   ```

2. **Test Frontend**
   - Visit your frontend URL
   - Try uploading a test document
   - Check browser console for errors

### 4. Monitor Logs

**App Platform:**
- Go to your app → **Runtime Logs**

**Droplet:**
```bash
# Backend logs
journalctl -u lexdeep-backend -f

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

---

## Troubleshooting

### Backend Not Starting

**Check logs:**
```bash
# App Platform: Check Runtime Logs in dashboard
# Droplet:
journalctl -u lexdeep-backend -n 50
```

**Common issues:**
- Missing environment variables → Check App Platform env vars or `.env` file
- Port conflict → Ensure backend uses `$PORT` (App Platform) or `8000` (Droplet)
- Python version → Ensure Python 3.11 is installed

### Frontend Can't Connect to Backend

**Check:**
1. CORS configuration includes your frontend URL
2. Frontend API base URL is correct
3. Backend is running and accessible
4. Network/firewall rules allow connections

### File Upload Issues

**Check:**
1. `DATA_ROOT` directory exists and is writable
2. Sufficient disk space
3. File size limits (App Platform: 100MB default, Droplet: configure in Nginx)

### Performance Issues

**Optimize:**
1. Enable gzip compression in Nginx
2. Use CDN for static assets (App Platform does this automatically)
3. Consider upgrading Droplet plan if memory is low

---

## Cost Estimation

### App Platform
- **Basic Plan**: $12/month (512MB RAM, 1GB storage)
- **Professional Plan**: $25/month (1GB RAM, 2GB storage) - Recommended for production
- **Bandwidth**: Included (1TB/month)

### Droplet
- **Basic Droplet**: $6/month (1GB RAM, 1 vCPU, 25GB SSD)
- **Regular Droplet**: $12/month (2GB RAM, 1 vCPU, 50GB SSD) - Recommended
- **Bandwidth**: Included (1TB/month)

### Additional Costs
- Domain name: ~$10-15/year (optional)
- SSL certificate: Free (Let's Encrypt)

---

## Next Steps

1. ✅ Set up monitoring (DigitalOcean Monitoring)
2. ✅ Configure backups (App Platform: automatic, Droplet: manual)
3. ✅ Set up CI/CD (GitHub Actions for auto-deploy)
4. ✅ Configure custom domain
5. ✅ Set up error tracking (Sentry, etc.)

---

## Support Resources

- [DigitalOcean App Platform Docs](https://docs.digitalocean.com/products/app-platform/)
- [DigitalOcean Droplets Docs](https://docs.digitalocean.com/products/droplets/)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Vite Production Guide](https://vitejs.dev/guide/build.html)
