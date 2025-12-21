# Replace DigitalOcean App Spec

## Current Issue
Your current app spec only has one service (`ai-translator`). You need to replace it with the new spec that includes both `backend` and `frontend` services.

## Steps to Replace App Spec

1. **Go to App Spec**:
   - Navigate to: https://cloud.digitalocean.com/apps/22be8a3b-5e71-404f-b914-788dcbf02f6c/settings
   - Click on **App Spec** tab

2. **Edit App Spec**:
   - Click **Edit** button
   - **DELETE** all existing content
   - **PASTE** the new app spec (see below)
   - Click **Save**

3. **Deploy**:
   - DigitalOcean will detect both services
   - It will start building both backend and frontend
   - Monitor the build in **Runtime Logs**

## New App Spec to Paste:

```yaml
name: lexdeep-translator
region: nyc

services:
  - name: backend
    github:
      repo: boulder225/ai-translator
      branch: main
    dockerfile_path: Dockerfile
    docker_context: /
    http_port: 8080
    instance_count: 1
    instance_size_slug: basic-xxs
    routes:
      - path: /api
        preserve_path_prefix: true
    envs:
      - key: ANTHROPIC_API_KEY
        scope: RUN_TIME
        type: SECRET
        value: ${ANTHROPIC_API_KEY}
      - key: DATA_ROOT
        scope: RUN_TIME
        value: /app/data
      - key: DEFAULT_SOURCE_LANG
        scope: RUN_TIME
        value: fr
      - key: DEFAULT_TARGET_LANG
        scope: RUN_TIME
        value: it
      - key: PORT
        scope: RUN_TIME
        value: "8080"

  - name: frontend
    github:
      repo: boulder225/ai-translator
      branch: main
    dockerfile_path: frontend/Dockerfile
    docker_context: /frontend
    http_port: 80
    instance_count: 1
    instance_size_slug: basic-xxs
    routes:
      - path: /
    envs:
      - key: VITE_API_URL
        scope: BUILD_TIME
        value: https://orca-app-kmn9o.ondigitalocean.app
```

## Important Notes:

1. **Region Change**: The new spec uses `region: nyc` instead of `fra`. If you want to keep `fra`, change it to `region: fra`

2. **Environment Variables**: After saving, make sure `ANTHROPIC_API_KEY` is set as a SECRET in the dashboard (Settings → Environment Variables)

3. **Instance Size**: Changed from `apps-s-1vcpu-1gb` to `basic-xxs` (smaller/cheaper). If you prefer the larger size, change `basic-xxs` to `apps-s-1vcpu-1gb`

4. **Instance Count**: Backend changed from 2 to 1. If you want 2 instances, change `instance_count: 1` to `instance_count: 2`

## After Deployment:

- **Components** section should show both `backend` and `frontend`
- Frontend: `https://orca-app-kmn9o.ondigitalocean.app/`
- Backend API: `https://orca-app-kmn9o.ondigitalocean.app/api`
