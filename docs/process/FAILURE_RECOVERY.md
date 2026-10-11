# Failure Recovery

Last reviewed: 2026-10-10

## Purpose
Operational recovery guide for API, CLI, webhook, and run-state failures.

## Recovery Principles
1. Recover from durable state and logs first; do not patch blind.
2. Prefer replay/trace artifacts before rerunning work.
3. Keep remediation deterministic and auditable.

## Primary Artifacts
1. Runtime log: `workspace/default/orket.log`
2. Observability traces: `workspace/default/observability/`
3. Runtime DB: `.orket/durable/db/orket_persistence.db`
4. Webhook DB: `.orket/durable/db/webhook.db`

## Failure Classes and Actions

### 1) API unavailable
Checks:
1. `python server.py` running on expected port (`ORKET_PORT`, default `8082`).
2. `curl http://localhost:8082/health`.

Actions:
1. Inspect `workspace/default/orket.log` for startup/auth errors.
2. Check the launching process and selected `.env` authentication settings against
   [Security](../SECURITY.md#1-api-auth-policy-v1). A bypass flag alone does not
   enable anonymous access; shell values take precedence and the API captures
   its configuration at startup.
3. Restart server after correcting env or path issues.

### 2) Webhook failures
Checks:
1. `python -m orket.webhook_server` is running (`:8080`).
2. `GITEA_WEBHOOK_SECRET` matches Gitea webhook config.
3. Requests include `X-Gitea-Signature`.

Actions:
1. Inspect webhook logs in `workspace/default/orket.log`.
2. Query `.orket/durable/db/webhook.db` for event results.
3. Re-test with Gitea test delivery after fixes.

### 3) Run stalls or non-progress
Checks:
1. Generate failure report:
```bash
python scripts/replay/report_failure_modes.py --log workspace/default/orket.log --out benchmarks/results/replay/failure_modes.json
```
2. Inspect per-turn checkpoint files in `workspace/default/observability/...`.

Actions:
1. Replay problematic turn from CLI:
```bash
python main.py --replay-turn <session_id>:<issue_id>:<turn_index>[:role]
```
2. Validate gate and policy constraints before rerun.

### 4) Schema/migration mismatch
Checks:
1. DB path permissions and schema state.
2. Migration drift after updates.

Actions:
1. Run migrations:
```bash
python scripts/governance/run_migrations.py
```
2. Re-run the CLI smoke and current security controls:
```bash
python scripts/governance/run_cli_regression_smoke.py --out benchmarks/results/governance/cli_regression_smoke.json
python -m pytest -q tests/interfaces/test_api.py -k "health_check or version or insecure or websocket_events"
python -m pytest -q tests/interfaces/test_webhook_factory.py
```
These checks do not establish migration correctness or whole-release acceptance.
The legacy `security_canary.py` and its `release_smoke.py` caller still depend on
removed app singletons. Their migration remains tooling debt; see
[Testing policy](../TESTING_POLICY.md#cli-and-security-smoke).

## Post-Recovery Verification
1. `python -m pytest -q`
2. `python scripts/benchmarks/check_volatility_boundaries.py`
3. `python scripts/governance/run_cli_regression_smoke.py --out benchmarks/results/governance/cli_regression_smoke.json`

## Escalation Rule
If the same failure repeats after one clean recovery pass, create a tracked project item with:
1. Failure signature.
2. Repro command.
3. Root-cause hypothesis.
4. Proposed guard/test to prevent recurrence.
