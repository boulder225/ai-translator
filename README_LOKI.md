# Loki Logging Setup

## How `.env` File Works

The application automatically loads environment variables from `.env` file when it starts. The `.env` file is loaded **before** logging is configured, so your Loki credentials will be available.

## `.env` File Format

Make sure your `.env` file has these variables:

```bash
LOKI_URL=https://logs-prod-XXX.grafana.net/loki/api/v1/push
LOKI_USERNAME=your-username-or-user-id
LOKI_PASSWORD=your-api-token
```

**Important:** 
- No quotes needed around values
- No spaces around `=`
- One variable per line

## How to Verify It's Working

### Option 1: Check Startup Logs

When you start the backend, look for this message:
- ✅ `"Loki logging handler enabled"` = Success!
- ❌ `"python-logging-loki-v2 not installed"` = Package missing
- ❌ `"Failed to setup Loki handler: {error}"` = Configuration error

### Option 2: Test Locally

1. Make sure you have a virtual environment activated:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. Start the backend:
   ```bash
   uvicorn src.translator.api:app --reload
   ```

3. Check the startup logs for `"Loki logging handler enabled"`

### Option 3: Check Grafana Cloud

1. Go to your Grafana Cloud dashboard
2. Navigate to **Explore** → Select **Loki** data source
3. Query: `{application="legal-translator"}`
4. You should see logs appearing in real-time

## Troubleshooting

### `.env` file not loading?

- Make sure `.env` is in the project root (same directory as `pyproject.toml`)
- Check file permissions: `ls -la .env`
- Verify format: no extra spaces, one variable per line

### Loki handler not enabled?

- Check all three variables are set: `LOKI_URL`, `LOKI_USERNAME`, `LOKI_PASSWORD`
- Verify values are correct (no typos)
- Check package is installed: `pip list | grep logging-loki`

### Logs not appearing in Grafana?

- Verify your API token is valid
- Check Loki URL is correct (should end with `/loki/api/v1/push`)
- Try querying with: `{application="legal-translator", environment="production"}`
