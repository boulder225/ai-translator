#!/bin/bash
set -e
echo "Starting services..."
echo "Frontend files in /usr/share/nginx/html:"
ls -la /usr/share/nginx/html/ || echo "WARNING: No files found"
echo "Nginx config files:"
ls -la /etc/nginx/conf.d/
echo "Removing any remaining default sites..."
# Aggressively remove everything related to default sites
rm -rf /etc/nginx/sites-enabled
mkdir -p /etc/nginx/sites-enabled
rm -f /etc/nginx/sites-available/default
# Remove any symlinks that might exist
find /etc/nginx -type l -delete 2>/dev/null || true
# Comment out ALL sites-enabled includes in nginx.conf BEFORE testing
sed -i 's|include /etc/nginx/sites-enabled/\*;|# include /etc/nginx/sites-enabled/*;|g' /etc/nginx/nginx.conf
sed -i 's|include.*sites-enabled|# include sites-enabled|g' /etc/nginx/nginx.conf
# Also check and comment in http block
sed -i '/http {/,/^}/ s|include /etc/nginx/sites-enabled|# include /etc/nginx/sites-enabled|g' /etc/nginx/nginx.conf
# Remove daemon directive from config file since we use -g flag on command line
sed -i '/^[[:space:]]*daemon[[:space:]]/d' /etc/nginx/nginx.conf
echo "Nginx sites-enabled after cleanup:"
ls -la /etc/nginx/sites-enabled/ || echo "sites-enabled directory empty (good)"
echo "Checking for any default site files:"
find /etc/nginx -name "default" -type f 2>/dev/null || echo "No default files found (good)"
echo "Checking nginx.conf for sites-enabled include:"
grep -n "sites-enabled" /etc/nginx/nginx.conf || echo "No sites-enabled references found (good)"
echo "Verifying no default server blocks exist..."
grep -r "default_server" /etc/nginx/conf.d/ || echo "No default_server in conf.d (good)"
echo "Testing nginx config..."
nginx -t
echo "Starting backend..."
cd /app
uvicorn src.translator.api:app --host 0.0.0.0 --port 8080 &
echo "Backend started, PID: $!"
echo "Starting nginx..."
nginx -g "daemon off;"
