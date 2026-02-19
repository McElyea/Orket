# Orket Operational Runbook

## Scope
Use this document for active operations and incident response.  
Detailed procedures live in dedicated docs linked below.

## Prerequisites
- Python 3.10+
- `ORKET_API_KEY` set for protected API routes
- `GITEA_WEBHOOK_SECRET` and `GITEA_ADMIN_PASSWORD` set for webhook runtime
- `ORKET_TIMEZONE=MST` (or `America/Denver`) for local-time logs and API timestamps

## First Run Setup
1. Clone:
```bash
git clone https://github.com/McElyea/Orket.git
cd Orket
```
2. Create environment file:
```bash
cp .env.example .env
```
3. Fill required values in `.env`:
- `DASHBOARD_PASSWORD`
- `DASHBOARD_SECRET_KEY`
- `GITEA_ADMIN_USER`
- `GITEA_ADMIN_PASSWORD`
- `GITEA_ADMIN_EMAIL`
- `POSTGRES_PASSWORD`
- `MYSQL_PASSWORD`
- `MONGO_PASSWORD`
4. Install Python dependencies:
```bash
pip install -r requirements.txt
```
5. Start Gitea:
```bash
cd infrastructure
docker-compose -f docker-compose.gitea.yml up -d
```
6. Complete web setup at `http://localhost:3000`.
7. Verify baseline:
```bash
python -m pytest tests/test_golden_flow.py -v
```

## Credential Management
Rule:
1. All secrets belong in `.env`.

Protected by `.gitignore`:
1. `.env`
2. `.orket/durable/config/user_settings.json`
3. `*.db`
4. `infrastructure/gitea/`
5. `infrastructure/mysql/`

Safe to commit:
1. `config/organization.json`
2. `config/*_example.json`
3. `.env.example`

Rotation:
1. Generate a new value.
2. Update `.env`.
3. Restart dependent services.
4. Verify auth/session-dependent flows.

Leak response:
1. Rotate leaked credentials immediately.
2. Remove exposed secrets from git history.
3. Force-push cleaned history if required.
4. Notify collaborators to refresh local state.

## Start Services
API server:
```bash
python server.py
```

Webhook server:
```bash
python -m orket.webhook_server
```

Health checks:
- API: `GET /health`
- Webhook: `GET /health`

## Deploy
```bash
docker build -t orket:latest .
docker run --rm -p 8082:8082 --env-file .env orket:latest
```

## Migrations
```bash
python scripts/run_migrations.py
```

Optional DB overrides:
```bash
python scripts/run_migrations.py --runtime-db /data/orket_persistence.db --webhook-db /data/webhook.db
```

Default durable DB paths:
1. `.orket/durable/db/orket_persistence.db`
2. `.orket/durable/db/webhook.db`

## Architecture Policy Knobs
### Architecture Mode
Controls whether project architecture shape is forced or decided by the architect.

Valid values:
1. `force_monolith`
2. `force_microservices`
3. `architect_decides` (default)

Configuration order (highest wins):
1. Environment variable `ORKET_ARCHITECTURE_MODE`
2. `process_rules.architecture_mode` in organization config
3. Default fallback: `architect_decides`

Examples:
```bash
# Force monolith recommendation
set ORKET_ARCHITECTURE_MODE=force_monolith
python -m orket.interfaces.cli --epic sanity_test
```

```bash
# Force microservices recommendation
set ORKET_ARCHITECTURE_MODE=force_microservices
python -m orket.interfaces.cli --epic sanity_test
```

### Frontend Framework Mode
Controls frontend framework recommendation policy for architect decisions.

Valid values:
1. `force_vue`
2. `force_react`
3. `force_angular`
4. `architect_decides` (default)

Configuration order (highest wins):
1. Environment variable `ORKET_FRONTEND_FRAMEWORK_MODE`
2. `process_rules.frontend_framework_mode` in organization config
3. Default fallback: `architect_decides`

Examples:
```bash
set ORKET_FRONTEND_FRAMEWORK_MODE=force_angular
python -m orket.interfaces.cli --epic sanity_test
```

### Structural Governance Mode (Legacy iDesign Flag)
Controls whether legacy structural-governance enforcement is required, disabled, or delegated.

Valid values:
1. `force_idesign`
2. `force_none`
3. `architect_decides`

Configuration order (highest wins):
1. Environment variable `ORKET_IDESIGN_MODE`
2. `process_rules.idesign_mode` in organization config
3. Default fallback: `force_none`

Examples:
```bash
# Force legacy structural governance for all epics
set ORKET_IDESIGN_MODE=force_idesign
python -m orket.interfaces.cli --epic sanity_test
```

```bash
# Disable legacy structural governance for all epics (repo default)
set ORKET_IDESIGN_MODE=force_none
python -m orket.interfaces.cli --epic sanity_test
```

```bash
# Let epic governance setting decide
set ORKET_IDESIGN_MODE=architect_decides
python -m orket.interfaces.cli --epic sanity_test
```

## Release Gate
Local smoke:
```bash
python scripts/release_smoke.py
```

Security canary only:
```bash
python scripts/security_canary.py
```

Volatility boundary gate:
```bash
python scripts/check_volatility_boundaries.py
```

Failure/non-progress report:
```bash
python scripts/report_failure_modes.py --log workspace/default/orket.log --out benchmarks/results/failure_modes.json
```

Prompt eval metrics:
```bash
python scripts/prompt_lab/eval_harness.py --out benchmarks/results/prompt_eval_metrics.json
```

Real-service stress (no mocks/fakes):
```bash
python scripts/real_service_stress.py --profile heavy
```

Maximum load profile:
```bash
python scripts/real_service_stress.py --profile aggressive
```

Checklist:
1. Quality workflow passes.
2. Volatility boundary gate passes.
3. Docker smoke passes (`/health` probe).
4. Migration smoke passes.
5. Latest load artifact exists in `benchmarks/results/`.

## Incident Playbook
### API 5xx spike
1. Check `workspace/default/orket.log`.
2. Validate DB path/permissions.
3. Restart services and re-check `/health`.

### Webhook storm/abuse
1. Confirm `ORKET_RATE_LIMIT`.
2. Confirm `429` on `/webhook/gitea`.
3. Rotate `GITEA_WEBHOOK_SECRET` if needed.

### Verification stalls
1. Confirm `ORKET_VERIFY_TIMEOUT_SEC`.
2. Check fixtures under `workspace/verification/`.
3. Inspect logs for fixture load failures.

### Stalled Role Pipeline
1. Generate a failure/non-progress report:
   - `python scripts/report_failure_modes.py --out benchmarks/results/failure_modes.json`
2. Inspect per-turn checkpoints:
   - `workspace/default/observability/<run_id>/<issue_id>/<turn_index>_<role>/checkpoint.json`
3. Replay one turn for diagnostics:
   - `python -m orket.interfaces.cli --replay-turn <run_id>:<issue_id>:<turn_index>[:role]`
4. If repeated non-progress is present, run prompt metrics:
   - `python scripts/prompt_lab/eval_harness.py`
5. Resume by rerunning the same epic/session id after stalled cards are re-queued by resume policy.

## Archive Operations
Archive cards related to removed projects (DB history preserved):
```bash
python -m orket.interfaces.cli --archive-related price_arbitrage --archive-related sneaky_price_watch --archive-reason "project removal"
```

Archive by build:
```bash
python -m orket.interfaces.cli --archive-build build-my-project --archive-reason "project removal"
```

## Security Operations
- Keep secrets in environment variables.
- Run workflow gates before merge.
- Track security findings in your current audit artifact/process (the old `docs/SECURITY_AUDIT_2026-02-11.md` file was removed).

## Detailed Procedures
- Product publish/mirroring: `docs/PRODUCT_PUBLISHING.md`
- Local cleanup policy: `docs/LOCAL_CLEANUP_POLICY.md`
- CI lane policy: `docs/TESTING_POLICY.md`
