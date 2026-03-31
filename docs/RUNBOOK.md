# Orket Operational Runbook

Last reviewed: 2026-03-31

## Purpose
Operator commands for starting Orket, checking health, running core validations, and recovering from common failures.

## Quick Start
1. Install dependencies:
```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```
2. Configure environment:
```bash
copy .env.example .env
```
3. CLI runtime:
```bash
python main.py
```
4. API runtime (safe default profile, local-only bind `http://127.0.0.1:8082`):
```bash
python server.py
```
5. API dev runtime with reload (explicit opt-in):
```bash
python server.py --profile dev
```
6. Webhook runtime (default `http://127.0.0.1:8080`):
```bash
python -m orket.webhook_server
```
Requires webhook credentials in environment or `.env`:
1. `GITEA_WEBHOOK_SECRET`
2. `GITEA_ADMIN_PASSWORD`

## API Launcher Precedence
1. CLI arguments (`--host`, `--port`, `--profile`, `--reload/--no-reload`)
2. Config values from `--config <json-path>`
3. Environment values (`ORKET_HOST`, `ORKET_PORT`)
4. Safe defaults (`host=127.0.0.1`, `port=8082`, `profile=safe`, `reload=false`)
5. Reload can only be enabled when `profile=dev`.

## Logging Context Mode
1. `ORKET_LOGGING_MISSING_CONTEXT_MODE=legacy_default` (default):
   - writes to `workspace/default/orket.log`
   - adds stable markers `logging_context_mode=legacy_default` and `logging_context_marker=workspace_default_fallback`
2. `ORKET_LOGGING_MISSING_CONTEXT_MODE=fail_fast`:
   - raises `E_LOG_WORKSPACE_REQUIRED` when workspace context is omitted

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
python scripts/governance/run_cli_regression_smoke.py --out benchmarks/results/governance/cli_regression_smoke.json
```
4. Release smoke:
```bash
python scripts/governance/release_smoke.py
```
5. Security canary:
```bash
python scripts/security/security_canary.py
```
6. Volatility boundary gate:
```bash
python scripts/benchmarks/check_volatility_boundaries.py
```
7. Published artifact sync check:
```bash
python scripts/governance/sync_published_index.py --check
```

## Terraform Plan Reviewer
Authority: `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`

1. Local governed proof:
```bash
python -m pytest -q tests/application/test_terraform_plan_review_deterministic.py tests/application/test_terraform_plan_review_service.py tests/scripts/test_run_terraform_plan_review_live_smoke.py
```
Use this as the primary acceptance command for the Terraform plan reviewer lane. It proves the fixture corpus, fake adapter pack, governance artifact emission, and explicit violation probes locally.

2. Thin live AWS smoke:
```bash
python scripts/reviewrun/run_terraform_plan_review_live_smoke.py
```
Required environment:
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`
   - `AWS_REGION` or `AWS_DEFAULT_REGION`

Optional environment:
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE`
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_CREATED_AT`
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TRACE_REF`
   - `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_POLICY_BUNDLE_ID`

3. Thin live AWS smoke with explicit flags:
```bash
python scripts/reviewrun/run_terraform_plan_review_live_smoke.py --plan-s3-uri s3://<bucket>/<key> --model-id anthropic.<model_id> --region <aws_region>
```
Optional flags:
   - `--table-name TerraformReviews`
   - `--out .orket/durable/observability/terraform_plan_review_live_smoke.json`
   - `--execution-trace-ref terraform-plan-review-live-smoke`
   - `--policy-bundle-id terraform_plan_reviewer_v1`

4. Canonical smoke output:
   - `.orket/durable/observability/terraform_plan_review_live_smoke.json`
   - exit code `0` means observed result `success`
   - exit code `1` means observed result was not `success`
   - missing env, missing AWS dependencies, or unusable AWS credentials must report an explicit `environment blocker`, not false success

5. Operator interpretation:
   - `publish_decision = normal_publish` means deterministic analysis succeeded and the audit write path was allowed
   - `publish_decision = degraded_publish` means deterministic analysis succeeded and summary generation failed
   - `publish_decision = no_publish` means the run failed closed because deterministic analysis was incomplete, policy blocked execution, or the environment blocked proof
   - `execution_status = blocked_by_policy` must be interpreted as policy enforcement, not generic runtime failure

## Graph Artifacts
Authority: `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`

Available now:
1. `run_graph.json`
   - The existing execution/protocol reconstruction graph.
   - This remains separate from the run-evidence graph family.
   - It materializes under `runs/<session_id>/run_graph.json` through the normal runtime/reconstruction path; there is no separate canonical operator CLI in the active authority docs for emitting it ad hoc.
2. `run_evidence_graph`
   - The shipped V1 evidence-visualization graph family.
   - Canonical operator path:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>
```

How to run the shipped run-evidence graph:
1. Select a covered control-plane `run_id`.
2. Make sure the corresponding `runs/<session_id>/` artifacts are present under your workspace root.
3. Run:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>
```
4. Open or inspect the generated artifacts:
   - `runs/<session_id>/run_evidence_graph.json`
   - `runs/<session_id>/run_evidence_graph.mmd`
   - `runs/<session_id>/run_evidence_graph.html`

Optional flags:
1. Limit rendered views:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --view full_lineage --view closure_path
```
2. Override workspace root:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --workspace-root <workspace_root>
```
3. Override control-plane DB path:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --control-plane-db <sqlite_path>
```
4. Force a known session id:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --session-id <session_id>
```
5. Fix the generation timestamp for deterministic proof runs:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --generation-timestamp <iso_utc_timestamp>
```

Shipped view tokens:
1. `full_lineage`
2. `failure_path`
3. `resource_authority_path`
4. `closure_path`

Operator interpretation:
1. The command prints a JSON result payload to stdout.
2. Exit code `0` means `ok=true`.
3. Exit code `1` means `ok=false`; inspect `error_code`, `detail`, and `graph_result`.
4. `graph_result` may be:
   - `complete`
   - `degraded`
   - `blocked`
5. If Orket cannot truthfully locate the selected run's `runs/<session_id>/` root, the command fails closed with `E_RUN_SESSION_NOT_LOCATED`.

Named graph families that are not separately shipped today:
1. `authority`
2. `decision`
3. `closure`
4. `resource-authority`

These remain Graphs checkpoint vocabulary over the same semantic core, not separate shipped artifact families or dedicated operator CLIs.

Deferred graph families:
1. `workload-composition`
2. `counterfactual/comparison`

## Tech Debt Cycle Reference
1. Execute recurring maintenance cycles using:
   - `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
2. Use the checklist as the command/evidence source of truth for recurring freshness work.
3. Apply techdebt folder archive/closeout semantics from:
   - `docs/projects/techdebt/README.md`

## Gitea CI Helper
Requires `ORKET_GITEA_URL`, `ORKET_GITEA_OWNER`, `ORKET_GITEA_REPO`, and `ORKET_GITEA_TOKEN` in environment or `.env`.

1. Show latest runs:
```bash
python scripts/ci/gitea_ci_easy.py status --limit 10
```
If Actions API is unavailable on your Gitea version, this command automatically falls back to commit-status contexts.
2. Trigger workflow and wait for result:
```bash
python scripts/ci/gitea_ci_easy.py trigger --workflow quality.yml --ref main --wait
```
3. Watch a known run:
```bash
python scripts/ci/gitea_ci_easy.py watch --run-id <run_id>
```
4. Diagnose API compatibility:
```bash
python scripts/ci/gitea_ci_easy.py doctor
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
python scripts/governance/workitem_migration_dry_run.py --in benchmarks/results/governance/workitem_migration_input.json --out benchmarks/results/governance/workitem_migration_dry_run.json
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
   - Verify `GITEA_ADMIN_PASSWORD`.
   - Verify `X-Gitea-Signature` is present.
   - Confirm webhook receiver is on `:8080`.
3. Stalled run:
```bash
python scripts/replay/report_failure_modes.py --log workspace/default/orket.log --out benchmarks/results/replay/failure_modes.json
```

## Companion Key Rotation
1. Preconditions:
   - Companion host and gateway are running and healthy.
   - You can reach `GET /api/v1/companion/status` through the gateway.
2. Stage new host keys first:
   - Set `ORKET_COMPANION_API_KEY=<new_companion_key>` on host.
   - Keep old `ORKET_API_KEY` active during cutover.
   - If enforcing strict least-privilege, set `ORKET_COMPANION_KEY_STRICT=true` only after gateway key update succeeds.
3. Rotate gateway credential second:
   - Update `COMPANION_API_KEY=<new_companion_key>` in extension gateway environment.
   - Restart gateway and verify `GET /api/status` returns `200`.
4. Smoke checks after cutover:
   - `GET /api/status` through gateway is `200`.
   - `POST /api/chat` through gateway returns `200`.
   - `GET /v1/version` with Companion key returns `403` (proves Companion-key scope is preserved).
5. Rollback:
   - Revert gateway `COMPANION_API_KEY` to previous value.
   - If strict mode was enabled and rollback requires core key compatibility, set `ORKET_COMPANION_KEY_STRICT=false`.
   - Re-run smoke checks and keep prior keys active until stability is confirmed.

## Related Docs
1. `docs/SECURITY.md`
2. `docs/TESTING_POLICY.md`
3. `docs/API_FRONTEND_CONTRACT.md`
4. `docs/process/GITEA_WEBHOOK_SETUP.md`
5. `docs/ROADMAP.md`
6. `docs/process/PUBLISHED_ARTIFACTS_POLICY.md`
7. `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
8. `docs/projects/techdebt/README.md`
9. `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
