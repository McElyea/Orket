# Gitea Webhook Setup

Last reviewed: 2026-02-27

## Purpose
Configure Gitea to send PR-related events into Orket's webhook service.

## Runtime Targets
1. Webhook server entrypoint: `python -m orket.webhook_server`
2. Default webhook server URL: `http://localhost:8080`
3. Primary endpoint: `POST /webhook/gitea`
4. Health endpoint: `GET /health`

## Required Environment
Set in `.env`:

```bash
GITEA_WEBHOOK_SECRET=<random hex secret>
GITEA_URL=http://localhost:3000
```

Optional for test endpoint auth:

```bash
ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT=true
ORKET_WEBHOOK_TEST_TOKEN=<token>
```

## Start Webhook Server
```bash
python -m orket.webhook_server
```

Verify:
```bash
curl http://localhost:8080/health
```

## Configure Gitea Webhook (UI)
1. Open repository settings in Gitea.
2. Add webhook type `Gitea`.
3. Set payload URL to:
   - `http://host.docker.internal:8080/webhook/gitea` (when Gitea runs in Docker), or
   - `http://<host-ip>:8080/webhook/gitea`.
4. Set content type: `application/json`.
5. Set secret to `GITEA_WEBHOOK_SECRET` value.
6. Enable events:
   - `pull_request`
   - `pull_request_review`
   - `push` (optional if your flow needs it)

## Signature Requirement
`/webhook/gitea` requires `X-Gitea-Signature` HMAC validation.

If the secret is missing or wrong, requests are rejected.

## Manual Test Endpoint
`POST /webhook/test` is disabled by default.

To use it:
1. Set `ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT=true`.
2. Authenticate with either:
   - `X-Webhook-Test-Token` matching `ORKET_WEBHOOK_TEST_TOKEN`, or
   - `X-API-Key` matching `ORKET_API_KEY`.

## Data Persistence
Webhook data is stored in:
1. `.orket/durable/db/webhook.db`

Useful checks:
```bash
sqlite3 .orket/durable/db/webhook.db "SELECT event_type, pr_key, result, created_at FROM webhook_events ORDER BY created_at DESC LIMIT 10;"
sqlite3 .orket/durable/db/webhook.db "SELECT pr_key, cycle_count, status FROM pr_review_cycles ORDER BY updated_at DESC LIMIT 10;"
```

## Common Failures
1. `401/403`:
   - Secret mismatch, missing signature, or invalid test token/API key.
2. Connection refused:
   - Wrong host/port or webhook server not running.
3. DB errors:
   - Missing writable `.orket/durable/db/` path.

## Related Docs
1. `docs/process/PR_REVIEW_POLICY.md`
2. `docs/SECURITY.md`
3. `docs/process/GITEA_STATE_OPERATIONAL_GUIDE.md`
