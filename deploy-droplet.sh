#!/bin/bash
# Deployment script for DigitalOcean Droplet
# Run this script on your Droplet after initial setup

set -e

echo "=========================================="
echo "LexDeep Droplet Deployment Script"
echo "=========================================="

# Configuration
# IMPORTANT: Update REPO_URL with your actual repository URL
APP_DIR="/opt/lexdeep"
REPO_URL="${REPO_URL:-https://github.com/boulder225/ai-translator.git}"  # CHANGE THIS
BRANCH="${BRANCH:-main}"

# Update system
echo "Updating system packages..."
apt update && apt upgrade -y

# Install dependencies
echo "Installing dependencies..."
apt install -y python3.11 python3.11-venv python3-pip nodejs nginx git build-essential libffi-dev libssl-dev

# Create app directory
echo "Setting up application directory..."
mkdir -p $APP_DIR
cd $APP_DIR

# Clone repository
if [ ! -d ".git" ]; then
    echo "Cloning repository..."
    git clone -b $BRANCH $REPO_URL .
else
    echo "Updating repository..."
    git pull origin $BRANCH
fi

# Setup Python virtual environment
echo "Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# Setup frontend
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Create data directory
mkdir -p data

# Setup environment variables
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-your_api_key_here}
DATA_ROOT=$APP_DIR/data
DEFAULT_SOURCE_LANG=fr
DEFAULT_TARGET_LANG=it
EOF
fi

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/lexdeep-backend.service << EOF
[Unit]
Description=LexDeep Backend API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/.venv/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/uvicorn src.translator.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/lexdeep << EOF
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        root $APP_DIR/frontend/dist;
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
ln -sf /etc/nginx/sites-available/lexdeep /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Enable and start services
echo "Starting services..."
systemctl daemon-reload
systemctl enable lexdeep-backend
systemctl restart lexdeep-backend
systemctl restart nginx

# Configure firewall
echo "Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Backend service: systemctl status lexdeep-backend"
echo "Nginx service: systemctl status nginx"
echo "Backend logs: journalctl -u lexdeep-backend -f"
echo "Nginx logs: tail -f /var/log/nginx/access.log"
echo ""
echo "Your app should be available at: http://$(curl -s ifconfig.me)"
