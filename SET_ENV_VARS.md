# Setting Environment Variables on DigitalOcean

This guide shows you how to set environment variables for both **App Platform** and **Droplet** deployments.

---

## Option 1: App Platform (Recommended)

### Method A: Via DigitalOcean Dashboard (Easiest)

1. **Go to your App**
   - Log in to https://cloud.digitalocean.com
   - Navigate to **Apps** → Select your app

2. **Navigate to Settings**
   - Click on **Settings** tab
   - Scroll down to **App-Level Environment Variables** section

3. **Add Environment Variables**
   - Click **Edit** next to "App-Level Environment Variables"
   - Click **+ Add Variable** for each variable:

   **Required Variables:**
   ```
   ANTHROPIC_API_KEY = your_actual_api_key_here
   ```

   **Optional Variables:**
   ```
   DATA_ROOT = /app/data
   DEFAULT_SOURCE_LANG = fr
   DEFAULT_TARGET_LANG = it
   ```

4. **Mark Secrets as Secure**
   - For `ANTHROPIC_API_KEY`, toggle the **"Encrypt"** or **"Secret"** option
   - This prevents it from being visible in logs

5. **Save Changes**
   - Click **Save** or **Apply**
   - The app will automatically redeploy with new variables

### Method B: Via app.yaml (For Version Control)

If you want to manage env vars in code (not recommended for secrets):

1. **Edit `.do/app.yaml`**
   ```yaml
   services:
     - name: backend
       envs:
         - key: ANTHROPIC_API_KEY
           scope: RUN_TIME
           type: SECRET
           value: ${ANTHROPIC_API_KEY}  # Set in dashboard
         - key: DATA_ROOT
           scope: RUN_TIME
           value: /app/data
   ```

2. **Set Secret Values in Dashboard**
   - Go to App → Settings → Environment Variables
   - Add `ANTHROPIC_API_KEY` as a **SECRET** variable
   - The `${ANTHROPIC_API_KEY}` reference will pull from dashboard

### Method C: Per-Service Environment Variables

If you need different variables for backend vs frontend:

1. **Go to your App** → **Components**
2. **Click on the service** (e.g., "backend")
3. **Click "Settings"** tab
4. **Scroll to "Environment Variables"**
5. **Add variables** specific to that service

**For Frontend Service:**
```
VITE_API_URL = https://backend-lexdeep-translator-xxxxx.ondigitalocean.app
```

**For Backend Service:**
```
ANTHROPIC_API_KEY = your_api_key_here (mark as SECRET)
DATA_ROOT = /app/data
DEFAULT_SOURCE_LANG = fr
DEFAULT_TARGET_LANG = it
```

---

## Option 2: Droplet Deployment

### Method A: Using .env File (Recommended)

1. **SSH into your Droplet**
   ```bash
   ssh root@your-droplet-ip
   ```

2. **Navigate to app directory**
   ```bash
   cd /opt/lexdeep
   ```

3. **Create or edit .env file**
   ```bash
   nano .env
   ```

4. **Add your environment variables**
   ```bash
   ANTHROPIC_API_KEY=your_actual_api_key_here
   DATA_ROOT=/opt/lexdeep/data
   DEFAULT_SOURCE_LANG=fr
   DEFAULT_TARGET_LANG=it
   ```

5. **Save and exit** (Ctrl+X, then Y, then Enter in nano)

6. **Restart the backend service**
   ```bash
   systemctl restart lexdeep-backend
   ```

### Method B: Using Systemd Environment File

1. **Edit the systemd service file**
   ```bash
   nano /etc/systemd/system/lexdeep-backend.service
   ```

2. **Add EnvironmentFile directive** (if not already present)
   ```ini
   [Service]
   EnvironmentFile=/opt/lexdeep/.env
   ExecStart=/opt/lexdeep/.venv/bin/uvicorn src.translator.api:app --host 0.0.0.0 --port 8000
   ```

3. **Reload and restart**
   ```bash
   systemctl daemon-reload
   systemctl restart lexdeep-backend
   ```

### Method C: Export Variables in Shell (Temporary)

**Note:** This only works for the current session. Use .env file for permanent setup.

```bash
export ANTHROPIC_API_KEY="your_api_key_here"
export DATA_ROOT="/opt/lexdeep/data"
export DEFAULT_SOURCE_LANG="fr"
export DEFAULT_TARGET_LANG="it"
```

---

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key for Claude | `sk-ant-...` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DATA_ROOT` | Directory for storing data files | `./data` | `/app/data` |
| `DEFAULT_SOURCE_LANG` | Default source language code | `fr` | `fr`, `de`, `en` |
| `DEFAULT_TARGET_LANG` | Default target language code | `it` | `it`, `en`, `de` |
| `ANTHROPIC_MODEL` | Claude model to use | `claude-sonnet-4-5-20250929` | `claude-opus-3` |

### Frontend Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL (build-time) | `https://backend-xxx.ondigitalocean.app` |

---

## Verifying Environment Variables

### App Platform

1. **Check in Dashboard**
   - Go to App → Settings → Environment Variables
   - All variables should be listed

2. **Check in Logs**
   - Go to App → Runtime Logs
   - Look for startup logs (variables won't show secrets)

3. **Test via API**
   ```bash
   curl https://your-backend-url/
   # Should return API info if variables are set correctly
   ```

### Droplet

1. **Check .env file**
   ```bash
   cat /opt/lexdeep/.env
   ```

2. **Check systemd service**
   ```bash
   systemctl show lexdeep-backend | grep EnvironmentFile
   ```

3. **Check running process**
   ```bash
   ps aux | grep uvicorn
   # Environment variables are loaded but not visible in ps
   ```

4. **Test application**
   ```bash
   curl http://localhost:8000/
   # Should return API info if working
   ```

---

## Security Best Practices

### ✅ DO:

- **Use SECRET type** for sensitive values (API keys, passwords)
- **Never commit** `.env` files to Git
- **Use different keys** for development and production
- **Rotate keys** periodically
- **Use least privilege** - only grant necessary permissions

### ❌ DON'T:

- **Don't hardcode** secrets in code
- **Don't log** sensitive values
- **Don't share** API keys in chat/email
- **Don't use** the same key for multiple environments

---

## Troubleshooting

### Variables Not Working?

1. **App Platform:**
   - Check variable names are correct (case-sensitive)
   - Ensure variables are set at correct scope (RUN_TIME vs BUILD_TIME)
   - Verify app has been redeployed after adding variables
   - Check logs for errors

2. **Droplet:**
   - Verify `.env` file exists and has correct format
   - Check systemd service has `EnvironmentFile` directive
   - Restart service: `systemctl restart lexdeep-backend`
   - Check logs: `journalctl -u lexdeep-backend -f`

### Common Errors

**"ANTHROPIC_API_KEY is required"**
- Variable not set or incorrectly named
- Check spelling (case-sensitive)
- Verify it's marked as SECRET in App Platform

**"Permission denied"**
- Check file permissions: `chmod 600 /opt/lexdeep/.env`
- Verify user running service has access

**"Variable not found"**
- Check variable is exported/loaded before service starts
- Verify EnvironmentFile path is correct

---

## Quick Reference Commands

### App Platform
```bash
# View variables (via dashboard only)
# No CLI command available
```

### Droplet
```bash
# View .env file
cat /opt/lexdeep/.env

# Edit .env file
nano /opt/lexdeep/.env

# Restart service after changes
systemctl restart lexdeep-backend

# Check service status
systemctl status lexdeep-backend

# View logs
journalctl -u lexdeep-backend -f
```

---

## Next Steps

After setting environment variables:

1. ✅ Verify variables are set correctly
2. ✅ Test the application
3. ✅ Check logs for any errors
4. ✅ Update CORS settings if needed
5. ✅ Test file uploads and translations

For more details, see `DEPLOYMENT_DIGITALOCEAN.md`.
