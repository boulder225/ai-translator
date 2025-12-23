# Grafana Cloud Loki Setup Guide

## Step 1: Create Access Policy with logs:write Permission

1. Go to Grafana Cloud → Access Policies:
   - https://grafana.com/orgs/YOUR_ORG/accesspolicies
   - Or: Grafana Cloud → Security → Access Policies

2. Click "Create Access Policy"

3. Configure the policy:
   - **Name**: "Loki Write Access" (or any name)
   - **Scopes**: 
     - ✅ Check `logs:write` (REQUIRED - this is what you're missing!)
     - Optionally: `logs:read` for reading logs
   - **Resources**: Select your Loki instance (or leave as "All")

4. Save the policy

## Step 2: Generate API Token from the Policy

1. In Access Policies, find your newly created policy
2. Click "Generate Token" or "Create Token"
3. **Copy the token immediately** (it's shown only once!)
   - Token format: `glc_eyJvIjoi...` (starts with `glc_`)

## Step 3: Get Your Username (Instance ID)

You have two options:

### Option A: Use Loki Instance ID (Recommended)
1. Go to: Grafana Cloud → Loki → Details
2. Find your **Instance ID** (a number)
3. Use this as `LOKI_USERNAME`

### Option B: Use Your User ID
1. Go to: Grafana Cloud → Profile → Preferences
2. Find your **User ID** (a number like `1435429`)
3. Use this as `LOKI_USERNAME`

## Step 4: Update Your `.env` File

```bash
LOKI_URL=https://logs-prod-039.grafana.net/loki/api/v1/push
LOKI_USERNAME=your-instance-id-or-user-id
LOKI_PASSWORD=glc_your-token-from-access-policy
```

**Important:**
- Token must be from an Access Policy with `logs:write` scope
- URL must end with `/loki/api/v1/push`
- No quotes around values

## Step 5: Test Your Credentials

**Important:** Use current timestamp (Loki rejects logs older than a few hours)

```bash
# Get current timestamp in nanoseconds
TIMESTAMP=$(date +%s)000000000

# Test with current timestamp
curl -u 'YOUR_USERNAME:YOUR_TOKEN' \
  -X POST 'https://logs-prod-039.grafana.net/loki/api/v1/push' \
  -H 'Content-Type: application/json' \
  -d "{\"streams\": [{\"stream\": {\"job\": \"test\"}, \"values\": [[\"${TIMESTAMP}\", \"test log from curl\"]]}]}"
```

Or use Python to generate the timestamp:
```python
import time
timestamp = int(time.time() * 1_000_000_000)  # nanoseconds
print(f"Current timestamp: {timestamp}")
```

**Expected results:**
- ✅ `{"streams":[]}` or `{}` = Success!
- ❌ `{"status":"error","error":"authentication error: invalid scope requested"}` = Token missing `logs:write`
- ❌ `{"status":"error","error":"authentication error"}` = Wrong username/token

## Troubleshooting

### "invalid scope requested" Error
- **Cause**: Token doesn't have `logs:write` permission
- **Fix**: Create Access Policy with `logs:write` scope, then generate token from that policy

### 401 Unauthorized Error
- **Cause**: Wrong username or token
- **Fix**: 
  - Try using Loki Instance ID instead of User ID
  - Verify token is correct (copy again from Access Policies)
  - Check URL ends with `/loki/api/v1/push`

### Token Not Working
- Make sure token is from an Access Policy (not just API Keys)
- Access Policy must have `logs:write` scope
- Token should start with `glc_`

## Quick Reference

- **Access Policies**: https://grafana.com/orgs/YOUR_ORG/accesspolicies
- **Loki Details**: Grafana Cloud → Loki → Details (for Instance ID)
- **User ID**: Grafana Cloud → Profile → Preferences
