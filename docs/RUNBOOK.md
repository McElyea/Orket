# Orket Operational Runbook

Last reviewed: 2026-02-27

## Purpose
Operator commands for starting Orket, checking health, running core validations, and recovering from common failures.

## Quick Start
1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Configure environment:
```bash
copy .env.example .env
```
3. CLI runtime:
```bash
python main.py
```
4. API runtime (default `http://localhost:8082`):
```bash
python server.py
```
5. Webhook runtime (default `http://localhost:8080`):
```bash
python -m orket.webhook_server
```

## Health Endpoints
1. API:
```bash
curl http://localhost:8082/health
```
2. Webhook server:
```bash
curl http://localhost:8080/health
```

## CLI Commands
Use `python main.py` for runtime commands.

1. Help:
```bash
python main.py --help
```
2. Show board:
```bash
python main.py --board
```
3. Run an epic:
```bash
python main.py --epic <epic_name>
```
4. Replay one turn:
```bash
python main.py --replay-turn <session_id>:<issue_id>:<turn_index>[:role]
```
5. Archive related cards:
```bash
python main.py --archive-related <token> --archive-reason "manual archive"
```

## Core Validation Commands
1. Full test sweep:
```bash
python -m pytest -q
```
2. Kernel ODR determinism gate (PR tier):
```bash
python -m pytest tests/kernel/v1/test_odr_determinism_gate.py -k gate_pr -q
```
3. CLI regression smoke:
```bash
python scripts/run_cli_regression_smoke.py --out benchmarks/results/cli_regression_smoke.json
```
4. Release smoke:
```bash
python scripts/release_smoke.py
```
5. Security canary:
```bash
python scripts/security_canary.py
```
6. Volatility boundary gate:
```bash
python scripts/check_volatility_boundaries.py
```
7. Published artifact sync check:
```bash
python scripts/sync_published_index.py --check
```

## Gitea CI Helper
Requires `ORKET_GITEA_URL`, `ORKET_GITEA_OWNER`, `ORKET_GITEA_REPO`, and `ORKET_GITEA_TOKEN` in environment or `.env`.

1. Show latest runs:
```bash
python scripts/ci/gitea_ci_easy.py status --limit 10
```
2. Trigger workflow and wait for result:
```bash
python scripts/ci/gitea_ci_easy.py trigger --workflow quality.yml --ref main --wait
```
3. Watch a known run:
```bash
python scripts/ci/gitea_ci_easy.py watch --run-id <run_id>
```

## Runtime Profiles and Migration
1. Set workflow profile:
```bash
set ORKET_WORKFLOW_PROFILE=legacy_cards_v1
```
or
```bash
set ORKET_WORKFLOW_PROFILE=project_task_v1
```
2. Migration dry-run:
```bash
python scripts/workitem_migration_dry_run.py --in benchmarks/results/workitem_migration_input.json --out benchmarks/results/workitem_migration_dry_run.json
```

## Storage Paths
Default durable state:
1. `.orket/durable/db/orket_persistence.db`
2. `.orket/durable/db/webhook.db`
3. `.orket/durable/config/user_settings.json`

Workspace/log paths:
1. `workspace/default/orket.log`
2. `workspace/default/observability/`

## Incident Triage
1. API failures:
   - Check `workspace/default/orket.log`.
   - Verify `ORKET_API_KEY` posture and `/health`.
2. Webhook failures:
   - Verify `GITEA_WEBHOOK_SECRET`.
   - Verify `X-Gitea-Signature` is present.
   - Confirm webhook receiver is on `:8080`.
3. Stalled run:
```bash
python scripts/report_failure_modes.py --log workspace/default/orket.log --out benchmarks/results/failure_modes.json
```

## Related Docs
1. `docs/SECURITY.md`
2. `docs/TESTING_POLICY.md`
3. `docs/API_FRONTEND_CONTRACT.md`
4. `docs/process/GITEA_WEBHOOK_SETUP.md`
5. `docs/ROADMAP.md`
6. `docs/process/PUBLISHED_ARTIFACTS_POLICY.md`
