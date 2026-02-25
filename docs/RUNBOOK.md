# Orket Operational Runbook

Last reviewed: 2026-02-21

## Purpose
This document is the operator path for starting, validating, troubleshooting, and maintaining Orket.

## Fast Path (5 Minutes)
1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Configure env file:
```bash
cp .env.example .env
```
3. Start local CLI conversation mode:
```bash
python main.py
```
4. Start API server (separate shell):
```bash
python server.py
```
5. Optional webhook server (separate shell):
```bash
python -m orket.webhook_server
```
6. Health checks:
- API: `GET /health`
- Webhook: `GET /health`

## First-Time Setup
1. Clone:
```bash
git clone https://github.com/McElyea/Orket.git
cd Orket
```
2. Create `.env` from template and fill required values used by your runtime path.
3. If using Gitea integration, start Gitea:
```bash
cd infrastructure
docker-compose -f docker-compose.gitea.yml up -d
```
4. Run baseline validation:
```bash
python -m pytest tests/test_golden_flow.py -v
```

## Runtime Entry Points
1. `python main.py`
- CLI runtime.
- With no `--epic`, `--card`, or `--rock`, this enters interactive driver mode.

2. `python server.py`
- Starts FastAPI API service.

3. `python -m orket.webhook_server`
- Starts webhook receiver with signature validation.

## Core Operator Commands
1. Show board:
```bash
python -m orket.interfaces.cli --board
```
2. Run an epic:
```bash
python -m orket.interfaces.cli --epic <epic_name>
```
3. Replay one turn:
```bash
python -m orket.interfaces.cli --replay-turn <run_id>:<issue_id>:<turn_index>[:role]
```
4. Archive related cards:
```bash
python -m orket.interfaces.cli --archive-related <token> --archive-reason "manual archive"
```

## Offline Mode (Core Pillars v1)
1. Default network mode is offline for command surface checks:
```bash
python scripts/check_offline_matrix.py --require-default-offline
```
2. Supported offline-first v1 mutation commands:
- `orket init`
- `orket api add`
- `orket refactor`
3. Optional network integrations remain explicit opt-in and outside the v1 offline command guarantee.

## CLI Regression Smoke
1. Run deterministic CLI regression for `init`, `api add`, and `refactor`:
```bash
python scripts/run_cli_regression_smoke.py --out benchmarks/results/cli_regression_smoke.json
```
2. Expected output:
- process exits with `0`
- artifact JSON contains `"status": "PASS"`
- event list includes: `init`, `api_dry_run`, `api_apply`, `api_noop`, `refactor_dry_run`, `refactor_apply`
3. This smoke uses isolated temp fixtures and does not mutate repository files.

## Release and Verification Gates
1. Local smoke:
```bash
python scripts/release_smoke.py
```
2. Security canary:
```bash
python scripts/security_canary.py
```
3. Volatility boundary gate:
```bash
python scripts/check_volatility_boundaries.py
```
4. Failure/non-progress report:
```bash
python scripts/report_failure_modes.py --log workspace/default/orket.log --out benchmarks/results/failure_modes.json
```

## Migrations and Storage
1. Run migrations:
```bash
python scripts/run_migrations.py
```
2. Optional DB path overrides:
```bash
python scripts/run_migrations.py --runtime-db /data/orket_persistence.db --webhook-db /data/webhook.db
```
3. Default durable DB paths:
- `.orket/durable/db/orket_persistence.db`
- `.orket/durable/db/webhook.db`

## Incident Triage
1. API errors / 5xx:
- Check `workspace/default/orket.log`.
- Validate DB paths and permissions.
- Restart service and re-check `/health`.

2. Webhook failures:
- Verify `GITEA_WEBHOOK_SECRET`.
- Verify webhook signature header is present.
- Confirm rate limit behavior (`429`) when expected.

3. Stalled execution:
- Generate report:
```bash
python scripts/report_failure_modes.py --out benchmarks/results/failure_modes.json
```
- Inspect checkpoints under:
`workspace/default/observability/<run_id>/<issue_id>/<turn_index>_<role>/checkpoint.json`
- Replay problematic turn (see command above).

## Skill Contract Troubleshooting
1. Validate a Skill manifest directly:
```bash
python scripts/check_skill_contracts.py --manifest <path_to_skill_manifest.json>
```
2. Common loader error codes:
- `ERR_SCHEMA_INVALID`: missing/invalid required contract fields.
- `ERR_CONTRACT_UNSUPPORTED_VERSION`: unsupported `skill_contract_version`.
- `ERR_RUNTIME_UNPINNED`: entrypoint runtime missing `runtime_version`.
- `ERR_FINGERPRINT_INCOMPLETE`: required argument/result fingerprint fields missing.
- `ERR_PERMISSION_UNDECLARED`: required permissions are not declared in requested permissions.
- `ERR_SIDE_EFFECT_UNDECLARED`: side-effect categories declared without fingerprint coverage.
3. For runtime tool failures in enforced skill mode, inspect:
`workspace/default/observability/<run_id>/<issue_id>/<turn_index>_<role>/memory_trace.json`
4. If runtime-limit violations occur, check orchestrator process rules:
- `skill_max_execution_time`
- `skill_max_memory`

## Security and Secrets
1. Keep secrets in `.env` only.
2. Do not commit `.env`, DB files, or local runtime state.
3. Rotate leaked credentials immediately.

## Policy Knobs (Advanced)
These are optional runtime controls.

1. Architecture mode: `ORKET_ARCHITECTURE_MODE`
- `force_monolith`
- `force_microservices`
- `architect_decides`

2. Frontend framework mode: `ORKET_FRONTEND_FRAMEWORK_MODE`
- `force_vue`
- `force_react`
- `force_angular`
- `architect_decides`

3. Legacy structural governance mode: `ORKET_IDESIGN_MODE`
- `force_idesign`
- `force_none`
- `architect_decides`

Repo default behavior keeps legacy structural governance disabled unless explicitly enabled.

## Related Docs
1. `docs/README.md` (docs index)
2. `docs/SECURITY.md`
3. `docs/QUANT_SWEEP_RUNBOOK.md`
4. `docs/TESTING_POLICY.md`
5. `docs/ROADMAP.md`
