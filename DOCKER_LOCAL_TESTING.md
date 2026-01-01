# Local Docker Testing

Test the Docker build locally before deploying to DigitalOcean.

## Quick Start

### Option 1: Interactive Mode (see logs in terminal)
```bash
./docker-build-local.sh
```
This will build and run the container, showing all logs. Press Ctrl+C to stop.

### Option 2: Background Mode (run in background)
```bash
./docker-test.sh
```
This will:
- Build the Docker image
- Start the container in background
- Test the health endpoint
- Show you the URLs

Then access:
- **Frontend**: http://localhost:8080
- **API**: http://localhost:8080/api
- **Health Check**: http://localhost:8080/api/health

## Useful Commands

### View logs
```bash
docker logs -f legal-translator-local
```

### Stop container
```bash
docker stop legal-translator-local
```

### Remove container
```bash
docker rm legal-translator-local
```

### Rebuild after changes
```bash
./docker-test.sh
```

### Check if container is running
```bash
docker ps | grep legal-translator-local
```

### Execute commands in running container
```bash
docker exec -it legal-translator-local /bin/bash
```

## Environment Variables

The scripts automatically load `ANTHROPIC_API_KEY` from your `.env` file if it exists.

You can also set it manually:
```bash
export ANTHROPIC_API_KEY="your-key-here"
./docker-test.sh
```

## Troubleshooting

### Port already in use
If port 8080 is already in use, change it in the scripts:
```bash
-p 8080:80  # Change 8080 to another port like 8081
```

### Build fails
Check the build logs for errors. Common issues:
- Missing files (check .dockerignore)
- Frontend build errors (check npm install/build)
- Python dependency issues

### Container won't start
Check logs:
```bash
docker logs legal-translator-local
```

### Nginx shows default page
Check if frontend files are present:
```bash
docker exec legal-translator-local ls -la /usr/share/nginx/html/
```
