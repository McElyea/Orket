# Orket Operational Runbook

## Scope
This runbook covers day-to-day operations for the Orket API/webhook runtime.

## Prerequisites
- Python 3.10+
- `ORKET_API_KEY` configured for protected API routes
- `GITEA_WEBHOOK_SECRET` and `GITEA_ADMIN_PASSWORD` configured for webhook server

## Start/Stop
### API server
```bash
python server.py
```

### Webhook server
```bash
python -m orket.webhook_server
```

### Health checks
- API: `GET /health`
- Webhook: `GET /health`

## Deploy with Docker
```bash
docker build -t orket:latest .
docker run --rm -p 8082:8082 --env-file .env orket:latest
```

The container health check probes `http://127.0.0.1:8082/health`.

## Database Migrations
Run schema/index migrations before rolling forward:
```bash
python scripts/run_migrations.py
```

Optional DB overrides:
```bash
python scripts/run_migrations.py --runtime-db /data/orket_persistence.db --webhook-db /data/webhook.db
```

## Load/Performance Validation
Run pre-release load harness:
```bash
python benchmarks/phase5_load_test.py \
  --webhook-base-url http://127.0.0.1:8080 \
  --api-base-url http://127.0.0.1:8082 \
  --ws-url ws://127.0.0.1:8082/ws/events \
  --webhook-total 100 \
  --epic-total 10 \
  --ws-clients 50 \
  --out benchmarks/results/<timestamp>_phase5_load.json
```

Track and archive:
- p50/p95/p99 latency
- error rate

Archived evidence:
- `benchmarks/results/2026-02-11_phase5_load.json`

## Release Checklist
Before release, verify:

1. Quality pipeline passes (`quality` job).
2. Docker smoke passes (`docker_smoke` job builds image and probes `/health`).
3. Migration smoke passes (`migration_smoke` job validates runtime and webhook DB migration tables).
4. Latest load artifact exists under `benchmarks/results/` and is linked in release notes.

### One-command local smoke
Run a local pre-release smoke in one command:
```bash
python scripts/release_smoke.py
```

Optional:
```bash
python scripts/release_smoke.py --skip-docker
```

## Incident Playbook
### 1. Elevated 5xx from API
1. Check `workspace/default/orket.log`.
2. Validate DB availability (`orket_persistence.db` path and permissions).
3. Restart service and verify `/health`.

### 2. Webhook storm or abuse
1. Confirm `ORKET_RATE_LIMIT` value.
2. Verify `429` responses on `/webhook/gitea`.
3. Rotate `GITEA_WEBHOOK_SECRET` if signature anomalies occur.

### 3. Verification hangs or stalls
1. Confirm subprocess timeout (`ORKET_VERIFY_TIMEOUT_SEC`, default `5`).
2. Check verification fixture path under `workspace/verification/`.
3. Inspect logs for `FATAL ERROR loading fixture`.

## Security Operations
- Keep secrets in environment variables; do not commit them.
- Run CI quality workflow on each PR.
- Review `docs/SECURITY_AUDIT_2026-02-11.md` for open risks before release.
