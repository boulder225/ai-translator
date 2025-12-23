# Backend Restart Required

The backend server needs to be restarted to pick up the new authentication routes.

## Quick Restart

```bash
# Stop the backend (if running)
pkill -f "uvicorn.*api"

# Start the backend
./run_api.sh

# Or manually:
source .venv/bin/activate
uvicorn src.translator.api:app --host 0.0.0.0 --port 8000 --reload
```

## Verify Routes Are Working

After restarting, test the endpoints:

```bash
# Health check (should return {"status":"ok"})
curl http://localhost:8000/api/health

# Login endpoint (should return JWT token)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

## Check Backend Logs

Look for these messages in the backend logs:
- "Loaded X users from environment variables"
- "User: admin, Roles: admin"

If you see these, the routes should be registered correctly.
