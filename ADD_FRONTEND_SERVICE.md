# Add Frontend Service to DigitalOcean App Platform

## Current Status
- ✅ Backend service is deployed
- ❌ Frontend service is missing

## Solution: Add Frontend Service Manually

### Option 1: Update App Spec in Dashboard (Recommended)

1. **Go to App Settings**:
   - Navigate to: https://cloud.digitalocean.com/apps/22be8a3b-5e71-404f-b914-788dcbf02f6c/settings
   - Click on **App Spec** tab

2. **Edit App Spec**:
   - Click **Edit** button
   - Copy the entire content from `.do/app.yaml` file
   - Paste it into the editor
   - Make sure both `backend` and `frontend` services are included
   - Click **Save**

3. **Deploy**:
   - DigitalOcean will automatically detect the new frontend service
   - It will start building the frontend Docker image
   - Monitor the build in **Runtime Logs**

### Option 2: Add Component Manually

1. **Go to Components**:
   - In your app dashboard, scroll to **Components** section
   - Click **Add Component** → **Service**

2. **Configure Frontend Service**:
   - **Name**: `frontend`
   - **Source**: 
     - Type: `GitHub`
     - Repository: `boulder225/ai-translator`
     - Branch: `main`
   - **Dockerfile Path**: `frontend/Dockerfile`
   - **Docker Context**: `/frontend`
   - **HTTP Port**: `80`
   - **Routes**:
     - Path: `/`
   - **Environment Variables**:
     - `VITE_API_URL` = `https://orca-app-kmn9o.ondigitalocean.app` (BUILD_TIME)

3. **Save and Deploy**:
   - Click **Create** or **Save**
   - Wait for build to complete

## Expected Result

After deployment:
- **Components** section should show both `backend` and `frontend`
- Frontend should be accessible at `https://orca-app-kmn9o.ondigitalocean.app/`
- Backend API should be accessible at `https://orca-app-kmn9o.ondigitalocean.app/api`

## Troubleshooting

### If Build Fails
1. Check **Runtime Logs** for the frontend service
2. Common issues:
   - Dockerfile path incorrect
   - Missing files in build context
   - npm install failures

### If Frontend Still Shows Backend
- Verify frontend service is running (check Components → frontend → Status)
- Check routes are configured correctly (`/` for frontend, `/api` for backend)
- Clear browser cache and try again
