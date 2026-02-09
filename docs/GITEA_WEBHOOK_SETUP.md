# Gitea Webhook Setup Guide

## Overview

This guide explains how to configure Gitea webhooks to trigger Orket's automated PR review and sandbox deployment system.

## Architecture

```
Gitea (PR Events) → Webhook → Orket FastAPI Server → Review Handler → Sandbox Orchestrator
```

## Prerequisites

1. Gitea running (http://localhost:3000)
2. Orket webhook server running (http://localhost:8080)
3. Webhook secret configured in .env

## Step 1: Configure Environment Variables

Add these to your `.env` file:

```bash
# Gitea Webhook Configuration
GITEA_WEBHOOK_SECRET=your-random-secret-here
GITEA_URL=http://localhost:3000
GITEA_ADMIN_USER=admin
GITEA_ADMIN_PASSWORD=your-admin-password
```

Generate a secure webhook secret:

```bash
# Windows (PowerShell)
python -c "import secrets; print(secrets.token_hex(32))"

# Linux/Mac
openssl rand -hex 32
```

## Step 2: Start Orket Webhook Server

```bash
# Start the webhook server
python orket/webhook_server.py

# Or use the startup script
./scripts/start_webhook_server.sh
```

The server will start on http://localhost:8080

Verify it's running:

```bash
curl http://localhost:8080/health
# Should return: {"status": "healthy"}
```

## Step 3: Configure Webhook in Gitea

### Option 1: Via Web UI

1. Go to your repository in Gitea (http://localhost:3000/Orket/your-repo)
2. Click Settings → Webhooks
3. Click "Add Webhook" → "Gitea"
4. Configure:
   - **Payload URL**: `http://host.docker.internal:8080/webhook/gitea`
     - Use `host.docker.internal` to reach host from Docker container
     - Or use your machine's IP address (e.g., `http://192.168.1.100:8080/webhook/gitea`)
   - **HTTP Method**: POST
   - **POST Content Type**: application/json
   - **Secret**: (paste your GITEA_WEBHOOK_SECRET from .env)
   - **Trigger On**:
     - ☑ Pull Request
     - ☑ Pull Request Review
     - ☑ Push
   - **Active**: ☑ Checked
5. Click "Add Webhook"

### Option 2: Via Gitea API

```bash
# Replace with your values
GITEA_URL="http://localhost:3000"
REPO_OWNER="Orket"
REPO_NAME="test-project"
WEBHOOK_SECRET="your-secret-here"
ADMIN_USER="admin"
ADMIN_PASSWORD="your-password"

# Create webhook
curl -X POST "$GITEA_URL/api/v1/repos/$REPO_OWNER/$REPO_NAME/hooks" \
  -u "$ADMIN_USER:$ADMIN_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "gitea",
    "config": {
      "url": "http://host.docker.internal:8080/webhook/gitea",
      "content_type": "json",
      "secret": "'"$WEBHOOK_SECRET"'"
    },
    "events": [
      "pull_request",
      "pull_request_review",
      "push"
    ],
    "active": true
  }'
```

## Step 4: Test Webhook

### Test Connection

1. In Gitea, go to Settings → Webhooks → Your webhook
2. Scroll to "Recent Deliveries"
3. Click "Test Delivery" → "Pull Request"
4. Check the response:
   - Status Code: 200 OK
   - Response Body: `{"status": "ignored", "message": "..."}`

### Test Real PR Flow

1. Create a test PR in Gitea
2. Add a comment with review (approve or request changes)
3. Check Orket webhook server logs for activity
4. Check webhook database: `.orket/webhook.db`

```bash
# View webhook events
sqlite3 .orket/webhook.db "SELECT * FROM webhook_events ORDER BY created_at DESC LIMIT 5;"

# View PR review cycles
sqlite3 .orket/webhook.db "SELECT * FROM pr_review_cycles;"
```

## Webhook Event Handling

### Pull Request Review (Approved)

```
Event: pull_request_review
Action: approved
→ Auto-merge PR
→ Trigger sandbox deployment
→ Add comment with sandbox URLs
```

### Pull Request Review (Changes Requested)

```
Event: pull_request_review
Action: changes_requested
→ Increment review cycle count
→ Store failure reason

Cycle 3: Escalate to lead_architect
Cycle 4+: Auto-reject PR, create Requirements Issue
```

### PR Merged

```
Event: pull_request
Action: closed (merged=true)
→ Deploy sandbox
→ Start Bug Fix Phase monitoring
```

## Troubleshooting

### Webhook not triggering

**Issue**: Gitea shows 500 error or connection refused

**Solutions**:
1. Verify webhook server is running:
   ```bash
   curl http://localhost:8080/health
   ```

2. Check Docker networking:
   ```bash
   # From inside Gitea container
   docker exec -it gitea sh
   wget -O- http://host.docker.internal:8080/health
   ```

3. Use host IP instead of localhost:
   ```bash
   # Find your IP
   ipconfig  # Windows
   ifconfig  # Linux/Mac

   # Update webhook URL
   http://192.168.1.100:8080/webhook/gitea
   ```

### Signature validation failing

**Issue**: Webhook returns 401 Unauthorized

**Solutions**:
1. Verify secret matches in both places:
   - Gitea webhook config
   - .env file (GITEA_WEBHOOK_SECRET)

2. Check webhook server logs for signature validation errors

3. Test without signature:
   ```bash
   curl -X POST http://localhost:8080/webhook/test \
     -H "Content-Type: application/json" \
     -d '{"event": "pull_request_review", "action": "approved"}'
   ```

### Database errors

**Issue**: SQLite errors in webhook handler

**Solutions**:
1. Check database exists: `.orket/webhook.db`
2. Reset database:
   ```bash
   rm .orket/webhook.db
   # Restart webhook server (will recreate schema)
   ```

3. Check permissions:
   ```bash
   ls -la .orket/
   ```

## Production Deployment

For production use:

1. Use HTTPS (not HTTP) for webhook URL
2. Use strong webhook secret (32+ bytes)
3. Run webhook server as systemd service
4. Configure firewall to allow webhook traffic
5. Use dedicated database (not SQLite)
6. Enable webhook request logging
7. Set up monitoring/alerts

## Monitoring

### Webhook Server Logs

```bash
# View real-time logs
tail -f workspace/default/orket.log

# Filter webhook events
grep "webhook" workspace/default/orket.log
```

### Database Queries

```bash
# Active PRs in review
sqlite3 .orket/webhook.db \
  "SELECT pr_key, cycle_count, status FROM pr_review_cycles WHERE status='active';"

# Recent failures
sqlite3 .orket/webhook.db \
  "SELECT pr_key, cycle_number, reviewer, reason FROM review_failures ORDER BY created_at DESC LIMIT 10;"

# Webhook event history
sqlite3 .orket/webhook.db \
  "SELECT event_type, pr_key, result, created_at FROM webhook_events ORDER BY created_at DESC LIMIT 20;"
```

## Next Steps

After webhook is configured:

1. Test PR review cycle (see docs/PR_REVIEW_POLICY.md)
2. Verify sandbox deployment works
3. Configure Bug Fix Phase thresholds
4. Set up monitoring/alerts
