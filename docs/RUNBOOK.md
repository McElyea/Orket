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

## Product Repo Publishing (Gitea)
Use this when you want each `<source-dir>/*` project mirrored into Gitea as its own repository and pushed by automation.

### What it does
1. Discovers folders under `<source-dir>/` (default `product/`).
2. Creates repos in Gitea (unless `--no-create`).
3. Uses `git subtree split` and pushes each project to its own repo branch.
4. Can verify parity (remote head SHA + tree manifest).
5. Can optionally delete local project folders after successful parity verification.

### Required env vars
```bash
GITEA_URL=http://localhost:3000
GITEA_ADMIN_USER=admin
GITEA_ADMIN_PASSWORD=your-password
GITEA_PRODUCT_OWNER=Orket
```

### Dry-run first
```bash
python scripts/publish_products_to_gitea.py
```

### Execute publish
```bash
python scripts/publish_products_to_gitea.py --execute --verify-parity --private --force
```

### Flexible source directory
```bash
python scripts/publish_products_to_gitea.py --execute --verify-parity --source-dir bin/projects
```

### Optional local deletion after verification
```bash
python scripts/publish_products_to_gitea.py --execute --verify-parity --delete-local --source-dir product
```

### Publish selected projects only
```bash
python scripts/publish_products_to_gitea.py --execute --projects sneaky_price_watch price_arbitrage
```

Notes:
1. Destination repos are named after folder names by default (set `--repo-prefix` to change).
2. Default branch target is the current local branch; override with `--branch`.
3. `--delete-local` is optional and intentionally gated behind `--verify-parity`.
4. `--force` is recommended on first sync if histories differ.
5. This is a mirror/split workflow; source of truth remains this monorepo unless you choose otherwise.

### Push Automation
Automation is provided by `.gitea/workflows/product_publish.yml`.

Behavior:
1. Triggers on push to `main` with changes in `product/**` or `bin/**`.
2. Runs only when repo variable `ENABLE_PRODUCT_REPO_PUBLISH=true`.
3. Uses `self-hosted` runner (needed for local/private Gitea reachability).
4. Performs publish + parity verification only (no delete in CI).

Branch policy:
1. Standard flow remains: feature branches open PRs and merge to `main`.
2. Publish automation executes after merge-to-main push event.
3. Destination branch defaults to `github.ref_name` unless overridden.

### Governance Ownership
1. Coder owns code changes.
2. Reviewer owns approval via PR merge.
3. Guard owns policy gates (`ENABLE_PRODUCT_REPO_PUBLISH`, required secrets, parity check).
4. Workflow owns execution of push automation.

### Required Repo Configuration (Gitea Actions)
1. Repository variable:
   - `ENABLE_PRODUCT_REPO_PUBLISH=true`
2. Optional repository variables:
   - `PRODUCT_PUBLISH_SOURCE_DIR=product` (or `bin/...`)
   - `PRODUCT_PUBLISH_TARGET_BRANCH=main`
   - `PRODUCT_PUBLISH_REPO_PREFIX=` (blank for folder-name repos)
3. Required repository secrets:
   - `GITEA_URL`
   - `GITEA_ADMIN_USER`
   - `GITEA_ADMIN_PASSWORD`
   - `GITEA_PRODUCT_OWNER`

### Safety Defaults
1. CI job does not pass `--delete-local`.
2. Local deletion remains explicit/manual and requires both:
   - `--verify-parity`
   - `--delete-local`

## Local Space Conservation Policy
Automated cleanup is available for parity-verified published projects.

Defaults:
1. `45 days` unchanged -> move local folder to archive.
2. `90 days` in archive -> permanent delete.
3. Cleanup only considers registry entries with `parity_verified=true`.
4. Cleanup skips dirty git paths by default.

### Registry
Publisher writes registry metadata to:
`/.orket/project_publish_registry.json`

### Manual dry-run
```bash
python scripts/cleanup_published_projects.py
```

### Manual execute (default thresholds)
```bash
python scripts/cleanup_published_projects.py --execute
```

### Custom thresholds
```bash
python scripts/cleanup_published_projects.py --execute --archive-days 30 --hard-delete-days 75
```

### Scheduled automation
Workflow: `.gitea/workflows/project_cleanup.yml`

Required variable:
1. `ENABLE_PROJECT_LOCAL_CLEANUP=true`

Optional variables:
1. `PROJECT_CLEANUP_SOURCE_DIR=product`
2. `PROJECT_CLEANUP_ARCHIVE_DAYS=45`
3. `PROJECT_CLEANUP_HARD_DELETE_DAYS=90`

Safety:
1. Scheduled cleanup is still constrained by parity-verified registry entries.
2. It never acts on folders that were not recorded by publish automation.

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
