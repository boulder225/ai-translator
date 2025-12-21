# Fix: prompt.md Missing in DigitalOcean Deployment

## Problem

DigitalOcean build fails with:
```
error: failed to get fileinfo for /.app_platform_workspace/prompt.md: no such file or directory
```

**Root Cause**: `prompt.md` is in `.gitignore`, so it's not in the repository. When DigitalOcean clones your repo, the file doesn't exist, causing the Docker build to fail.

## Solution Options

### Option 1: Remove prompt.md from .gitignore (Recommended)

This is the simplest solution:

1. **Edit `.gitignore`**:
   ```bash
   # Remove or comment out this line:
   # prompt.md
   ```

2. **Commit prompt.md**:
   ```bash
   git add prompt.md
   git commit -m "Add prompt.md to repository for deployment"
   git push
   ```

3. **Redeploy on DigitalOcean** - The build will now succeed.

**Pros**: Simple, prompt.md is version controlled  
**Cons**: prompt.md will be visible in the repository

### Option 2: Use Build Argument (Advanced)

Inject prompt content at build time:

1. **Update Dockerfile** to accept build arg:
   ```dockerfile
   ARG PROMPT_CONTENT=""
   RUN if [ -n "$PROMPT_CONTENT" ]; then echo "$PROMPT_CONTENT" > prompt.md; fi
   ```

2. **Set build arg in DigitalOcean App Platform**:
   - Go to App → Settings → Environment Variables
   - Add build-time variable: `PROMPT_CONTENT` with your prompt text

**Pros**: Keeps prompt.md out of repository  
**Cons**: More complex, need to manage prompt as env var

### Option 3: Use Default Prompt (Current)

The app already handles missing `prompt.md` gracefully - it uses a default prompt from `claude_client.py`. 

**Current Dockerfile** uses wildcard `COPY prompt.md* ./` which works if at least one file matches. Since `prompt.md` is gitignored, the build will fail.

**Quick Fix**: Comment out the COPY line:
```dockerfile
# COPY prompt.md* ./  # Commented out - file is gitignored
```

**Pros**: Build succeeds immediately  
**Cons**: You lose your custom prompt in production

## Recommended Action

**Remove `prompt.md` from `.gitignore`** and commit it. Your custom prompt is valuable IP and should be version controlled for consistent deployments.
