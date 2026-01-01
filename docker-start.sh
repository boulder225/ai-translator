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
# Remove default site file and any symlinks
rm -f /etc/nginx/sites-available/default
find /etc/nginx -name "default" -type f -delete 2>/dev/null || true
find /etc/nginx -name "default" -type l -delete 2>/dev/null || true
# Comment out ALL sites-enabled includes in nginx.conf BEFORE testing
# Use multiple sed patterns to catch all variations
sed -i 's|^[[:space:]]*include[[:space:]]*/etc/nginx/sites-enabled/\*;|    # include /etc/nginx/sites-enabled/*;|g' /etc/nginx/nginx.conf
sed -i 's|include.*sites-enabled/\*|# include sites-enabled/*|g' /etc/nginx/nginx.conf
sed -i 's|include.*sites-enabled|# include sites-enabled|g' /etc/nginx/nginx.conf
# Verify the include is commented
echo "Checking if sites-enabled include is commented:"
grep "sites-enabled" /etc/nginx/nginx.conf
# Remove daemon directive from config file since we use -g flag on command line
sed -i '/^[[:space:]]*daemon[[:space:]]/d' /etc/nginx/nginx.conf
echo "Nginx sites-enabled after cleanup:"
ls -la /etc/nginx/sites-enabled/ || echo "sites-enabled directory empty (good)"
echo "Checking for symlinks in sites-enabled:"
find /etc/nginx/sites-enabled -type l -ls || echo "No symlinks found (good)"
echo "Removing any files found in sites-enabled:"
rm -f /etc/nginx/sites-enabled/* 2>/dev/null || true
echo "Final sites-enabled contents:"
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
