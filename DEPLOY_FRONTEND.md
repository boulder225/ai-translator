# Deploy Frontend on DigitalOcean App Platform

## Issue
Backend is deployed at `https://orca-app-kmn9o.ondigitalocean.app/` but frontend is not visible.

## Solution Steps

### Option 1: Update App Spec in Dashboard (Recommended)

1. **Go to DigitalOcean Dashboard**:
   - Navigate to: https://cloud.digitalocean.com/apps
   - Click on your app: `lexdeep-translator`

2. **Edit App Spec**:
   - Go to **Settings** → **App Spec**
   - Click **Edit** button
   - Copy the entire content from `.do/app.yaml` file
   - Paste it into the editor
   - Click **Save**

3. **Deploy**:
   - DigitalOcean will automatically detect the frontend service
   - It will start building the frontend Docker image
   - Monitor the build in **Runtime Logs**

### Option 2: Force Redeploy from GitHub

1. **Make a small commit** to trigger redeploy:
   ```bash
   git commit --allow-empty -m "Trigger frontend deployment"
   git push origin main
   ```

2. **Check DigitalOcean**:
   - Go to your app dashboard
   - Check **Activity** tab for new deployment
   - Check **Components** section - you should see both `backend` and `frontend` services

### Option 3: Manual Service Addition

If the frontend service doesn't appear:

1. **Go to Components**:
   - In your app dashboard, scroll to **Components** section
   - Click **Add Component** → **Service**

2. **Configure Frontend**:
   - **Name**: `frontend`
   - **Source**: GitHub (`boulder225/ai-translator`, branch `main`)
   - **Dockerfile Path**: `frontend/Dockerfile`
   - **Docker Context**: `/frontend`
   - **HTTP Port**: `80`
   - **Route**: `/`
   - **Environment Variables**:
     - `VITE_API_URL` = `https://orca-app-kmn9o.ondigitalocean.app` (BUILD_TIME)

3. **Deploy**:
   - Click **Create** or **Save**
   - Wait for build to complete

## Expected Result

After deployment, both services should be accessible:
- **Frontend**: `https://orca-app-kmn9o.ondigitalocean.app/` (or separate URL)
- **Backend API**: `https://orca-app-kmn9o.ondigitalocean.app/api`

If routes are configured correctly, both should be on the same domain with frontend at `/` and backend at `/api`.

## Troubleshooting

### Check Build Logs
1. Go to **Runtime Logs** tab
2. Select `frontend` component
3. Look for build errors (Dockerfile issues, npm install failures, etc.)

### Verify Frontend Service Exists
1. Go to **Components** section
2. You should see both `backend` and `frontend` listed
3. If only `backend` exists, use Option 3 above

### Check Routes
- Frontend route: `/` 
- Backend route: `/api`
- These should work on the same domain
