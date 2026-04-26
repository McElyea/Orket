# Orket Operational Runbook

Last reviewed: 2026-04-25

## Purpose
Operator commands for starting Orket, checking health, running core validations, and recovering from common failures.
Exact HTTP route and payload catalog authority lives in `docs/API_FRONTEND_CONTRACT.md`; this runbook keeps only high-signal operator examples and ownership notes.

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
4. Named card runtime:
```bash
python main.py --card <card_id>
```
5. API runtime (safe default profile, local-only bind `http://127.0.0.1:8082`):
```bash
python server.py
```
6. API dev runtime with reload (explicit opt-in):
```bash
python server.py --profile dev
```
7. Webhook runtime (default `http://127.0.0.1:8080`):
```bash
python -m orket.webhook_server
```
Requires webhook credentials in environment or `.env`:
1. `GITEA_WEBHOOK_SECRET`
2. `GITEA_ADMIN_PASSWORD`
3. `GITEA_URL=https://...`

`ORKET_GITEA_ALLOW_INSECURE=true` is only for local plaintext Gitea. Without that explicit override, the webhook handler rejects `http://` Gitea API URLs before constructing the authenticated client.

## Engine Launch Examples
1. Default CLI runtime:
```bash
python main.py
```
2. Run one named card:
```bash
python main.py --card <card_id>
```
3. API runtime:
```bash
python server.py
```

Compatibility-only CLI alias:
`python main.py --rock <rock_name>` remains accepted for older callers, but it is hidden from `python main.py --help` and routes to the canonical named card runtime.

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
1. API liveness:
```bash
curl http://localhost:8082/health
```

Expected default body:
```json
{ "status": "ok" }
```
2. API version:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/version
```
All authenticated `/v1/*` HTTP responses include `X-Orket-Version`.
3. API heartbeat and metrics:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/system/heartbeat
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/system/metrics
```
4. Webhook server:
```bash
curl http://localhost:8080/health
```

## Outward Pipeline Ledger
The Phase 4 outward ledger path uses API-backed export and offline verification:

```bash
orket ledger export <run_id> --out ledger.json
orket ledger export <run_id> --types proposals,decisions --out ledger.partial.json
orket ledger verify ledger.json
orket ledger summary <run_id>
```

`orket ledger verify <file.json>` is offline and does not require a running Orket instance. Filtered exports verify as partial views anchored to the canonical ledger hash; they do not claim omitted event payload verification.

## Outward Pipeline Connectors
The Phase 5 built-in connector harness is local and uses the same registry-backed invocation rules as outward execution:

```bash
orket connectors list
orket connectors show write_file
orket connectors test create_directory --args "{\"path\":\"demo-dir\"}"
```

HTTP connectors require exact-host allowlisting:

```bash
set ORKET_CONNECTOR_HTTP_ALLOWLIST=example.com
orket connectors test http_get --args "{\"url\":\"https://example.com\"}"
```

## Outward Pipeline Policy Gate
The outbound policy gate can be configured with environment variables:

```bash
set ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS=items.*.args_preview.path
set ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS=BLOCKME
set ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS={"proposal_made":["event_type","payload"]}
```

Or use a JSON config file and point API startup at it:

```bash
set ORKET_OUTBOUND_POLICY_CONFIG_PATH=config/outbound_policy.json
python server.py
```

If configured redaction touches stored ledger event payload bytes, default ledger export returns a partial verified view instead of a false full ledger.

## HTTP Surface Scope
Authority: `docs/API_FRONTEND_CONTRACT.md`

1. Use this runbook for operator startup, health checks, core proof commands, and a small number of high-signal HTTP examples.
2. Use `docs/API_FRONTEND_CONTRACT.md` for the exact `/v1/*` route list, payload notes, query parameters, and bounded surface ownership.
3. Companion product routes remain BFF-owned and are not a core Orket host route family.

## Runtime Control and Approval Examples
1. Submit one outward-facing queued run:
```bash
orket run submit --description "Write a CSV parser" --instruction "Implement and test the parser"
```
2. Inspect one outward-facing run:
```bash
orket run status <run_id>
```
3. List queued outward-facing runs:
```bash
orket run list --status queued
```
4. Submit one outward-facing run with an explicit governed `write_file` proposal:
```bash
curl -X POST http://127.0.0.1:8082/v1/runs -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"run_id\":\"demo-write\",\"task\":{\"description\":\"Write approved file\",\"instruction\":\"Call write_file\",\"acceptance_contract\":{\"governed_tool_call\":{\"tool\":\"write_file\",\"args\":{\"path\":\"approved.txt\",\"content\":\"approved content\"}}}},\"policy_overrides\":{\"approval_required_tools\":[\"write_file\"]}}"
```
5. List pending outward-facing approval proposals:
```bash
orket approvals list
```
6. Review one outward-facing approval proposal:
```bash
orket approvals review <proposal_id>
```
7. Approve one outward-facing approval proposal:
```bash
orket approvals approve <proposal_id> --note "operator-reviewed"
```
8. Deny one outward-facing approval proposal:
```bash
orket approvals deny <proposal_id> --reason "operator rejected"
```
9. Inspect outward-facing run events:
```bash
orket run events <run_id> --types proposal_pending_approval,proposal_approved
```
10. Inspect the derived outward-facing run summary:
```bash
orket run summary <run_id>
```
11. Watch outward-facing run events:
```bash
orket run watch <run_id>
```
12. Start one active run from an operator-selected path:
```bash
curl -X POST http://127.0.0.1:8082/v1/system/run-active -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"path\":\"<project_relative_path>\"}"
```
13. Inspect one governed run:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs/<session_id>
```
14. Inspect one approval and resolve it on the canonical Packet 1 path:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/approvals/<approval_id>
```
```bash
curl -X POST http://127.0.0.1:8082/v1/approvals/<approval_id>/decision -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"decision\":\"approve\",\"notes\":\"operator-reviewed\"}"
```
15. The outward-facing approval surface admits `approve` and `deny` only for stored outward proposals. It does not expose approve-and-pause; the outward execution slice continues explicit registered governed connector calls after approval.
16. The active approval-checkpoint family admits four bounded shipped slices only: governed kernel `NEEDS_APPROVAL` on the default `session:<session_id>` namespace scope, plus governed turn-tool `write_file`, `create_directory`, and `create_issue` approval-required continuation on the default `issue:<issue_id>` namespace scope.
17. Packet 1 admits `approve` and `deny` only on this surface. `notes` and `edited_proposal` remain bounded operator metadata and do not create an alternate resume path.
18. On the bounded turn-tool `write_file`, `create_directory`, and `create_issue` slices, `approve` continues the same governed run on the already-selected `control_plane_target_ref`, while `deny` terminal-stops that same governed turn-tool run.
19. Canonical live proof for the shipped approval slice:
```bash
ORKET_DISABLE_SANDBOX=1 python scripts/nervous_system/run_nervous_system_live_evidence.py
```

## Session and Replay Examples
Authority: `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`

1. Start one host-owned interaction session:
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/sessions -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"session_params\":{\"reason\":\"operator-start\"}}"
```
2. Begin one subordinate turn on that session:
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/<session_id>/turns -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"workload_id\":\"stream_test_v1\",\"input_config\":{\"prompt\":\"hello\"},\"department\":\"core\",\"workspace\":\"workspace/default\",\"turn_params\":{}}"
```
3. Inspect the host-owned session state:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>/status
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>/snapshot
```
4. Inspect replay without claiming continuation authority:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>/replay
```
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/sessions/<session_id>/replay?issue_id=<issue_id>&turn_index=<turn_index>&role=<role>"
```
5. Halt one session on the admitted cleanup-adjacent operator path:
```bash
curl -X POST http://127.0.0.1:8082/v1/sessions/<session_id>/halt -H "X-API-Key: <api_key>"
```
6. Cancel one interaction session or one subordinate turn:
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/<session_id>/cancel -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{}"
```
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/<session_id>/cancel -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"turn_id\":\"<turn_id>\"}"
```
7. Packet 1 context-provider inputs remain limited to `session_params`, `input_config`, `turn_params`, `workload_id`, `department`, `workspace`, and host-resolved extension-manifest `required_capabilities`.
8. Session detail, status, snapshot, and replay remain inspection-only surfaces. `halt` and `cancel` remain cleanup-adjacent operator commands only; they do not imply deletion or workspace cleanup.

## Extension Runtime and Companion Ownership
1. Inspect generic runtime status for a host extension:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/status
```
2. List available models and run one generic generation call:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/models?provider=ollama"
```
```bash
curl -X POST http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/llm/generate -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"system_prompt\":\"You are a helpful assistant.\",\"user_message\":\"hello\"}"
```
3. Companion product routes live only in the external gateway/BFF under `/api/*`, not in Orket core. Use `docs/API_FRONTEND_CONTRACT.md` for the host/gateway ownership split and route catalog.
4. Use `docs/API_FRONTEND_CONTRACT.md` for the full generic extension runtime surface, marshaller inspection routes, file utilities, card and sandbox routes, and runtime policy/settings endpoints.

## Protocol Replay and Parity Examples
Authority: `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`

1. Replay one protocol run for inspection:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/protocol/runs/<run_id>/replay
```
2. Compare two protocol runs:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/protocol/replay/compare?run_a=<run_a>&run_b=<run_b>"
```
3. Compare one protocol run against one SQLite ledger:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/protocol/runs/<run_id>/ledger-parity?sqlite_db_path=<workspace_relative_sqlite_path>"
```
4. Operator interpretation:
   - these replay, comparison, and parity surfaces remain reconstruction or comparison views only
   - caller-provided `runs_root` and `sqlite_db_path` must remain under the configured workspace root or the request fails closed

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

## External Extension Package, Publish, and Validation
Authority: `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`, `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`, `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`

1. Canonical host-side Packet 1 validation path:
```bash
orket ext validate <extension_root> --strict --json
```
2. Packet 1 admits only `manifest_version: v0`.
3. Any other manifest family must fail closed with `E_SDK_MANIFEST_VERSION_UNSUPPORTED`.
4. When `src/` exists, host import-isolation scanning stays scoped to that source tree.
5. Validation success is installability evidence only; it does not grant runtime authority.
6. Canonical maintainer build path:
```bash
./scripts/build-release.sh
```
```powershell
./scripts/build-release.ps1
```
7. Canonical release verification path:
```bash
./scripts/verify-release.sh v<extension_version>
```
```powershell
./scripts/verify-release.ps1 v<extension_version>
```
8. The authoritative published artifact family is one source distribution: `dist/<normalized_project_name>-<version>.tar.gz`.
9. The canonical release tag is `v<extension_version>`.
10. Canonical operator intake from the published artifact:
   - retrieve the tagged source distribution artifact produced by `.gitea/workflows/release.yml`
   - extract the `.tar.gz` into a local staging directory
   - run `orket ext validate <extracted_root> --strict --json`
   - treat success as admissible for execution consideration only

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

## Trust Kernel Conformance Pack
Authority: `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`, `docs/specs/PORTABLE_TRUST_CONFORMANCE_PACK_V1.md`, `docs/guides/TRUST_KERNEL_CONFORMANCE_PACK_GUIDE.md`

1. Canonical local conformance command:
```powershell
$env:ORKET_DISABLE_SANDBOX='1'
python scripts/proof/run_trust_conformance_pack.py
```
2. Supplied-fixture verification mode:
```powershell
$env:ORKET_DISABLE_SANDBOX='1'
python scripts/proof/run_trust_conformance_pack.py --verify-fixture --packet <path-to-governed-change-packet.json>
```
3. Canonical output artifacts:
   - `benchmarks/results/proof/trust_conformance_summary.json`
   - `benchmarks/results/proof/finite_trust_kernel_model.json`
   - `benchmarks/results/proof/governed_repo_change_packet.json`
   - `benchmarks/results/proof/governed_repo_change_packet_verifier.json`
4. Operator interpretation:
   - the admitted compare scope is `trusted_repo_config_change_v1` only
   - the claim ceiling is `verdict_deterministic`
   - the command does not use AWS, remote providers, network services, or sandbox resource creation
   - the command does not prove replay determinism, text determinism, or a new compare scope
   - the conformance summary and finite-model report are claim-supporting derived evidence; they do not replace witness, validator, offline-verifier, or packet-verifier authority

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
python scripts/reviewrun/run_terraform_plan_review_live_smoke.py --plan-s3-uri s3://<bucket>/<key> --model-id <bedrock_model_or_inference_profile_id> --region <aws_region>
```
Optional flags:
   - `--table-name TerraformReviews`
   - `--out .orket/durable/observability/terraform_plan_review_live_smoke.json`
   - `--execution-trace-ref terraform-plan-review-live-smoke`
   - `--policy-bundle-id terraform_plan_reviewer_v1`
Supported smoke model families are defined in `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`; current examples include Anthropic Claude, Amazon Nova, Writer Palmyra X4 (`writer.palmyra-x4-v1:0` or `us.writer.palmyra-x4-v1:0`), and Writer Palmyra X5 (`writer.palmyra-x5-v1:0` or `us.writer.palmyra-x5-v1:0`).

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
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --view authority --view decision
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

Admitted view tokens:
1. `full_lineage`
2. `failure_path`
3. `authority`
4. `decision`
5. `resource_authority_path`
6. `closure_path`

Default emitted views when `--view` is omitted:
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

Filtered-view vocabulary over the same semantic core, not separate artifact families:
1. `authority`
2. `decision`
3. `closure`
4. `resource-authority`

`authority` and `decision` are now admitted additional `run_evidence_graph` view tokens selected through `--view`.
`closure` and `resource-authority` remain descriptive filtered-view labels for the shipped `closure_path` and `resource_authority_path` surfaces, not separate dedicated operator CLIs.

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

## Companion Host Credential Rotation
1. Preconditions:
   - Orket host and Companion gateway are running and healthy.
   - This repo does not define a repo-level canonical Companion gateway startup command.
   - If you are using the external extension template gateway, its local launchers live under `docs/templates/external_extension/scripts/`.
   - You can reach `GET /api/status` through the gateway.
   - You can reach `GET /v1/extensions/orket.companion/runtime/status` on the host.
2. Orket currently admits one host API key, not a Companion-scoped secondary key.
3. Rotate host and gateway credentials together:
   - Set `ORKET_API_KEY=<new_host_key>` on host.
   - Set `COMPANION_API_KEY=<new_host_key>` in the Companion gateway environment, or set `ORKET_API_KEY=<new_host_key>` in that process and let the gateway reuse it.
   - Restart host and gateway.
4. Smoke checks after cutover:
   - `GET /api/status` through gateway is `200`.
   - `POST /api/chat` through gateway with `Origin: http://127.0.0.1:3000` returns `200`.
   - `GET /v1/version` with the previous host key returns `403`.
5. Rollback:
   - Revert `ORKET_API_KEY` on host to the previous value.
   - Revert `COMPANION_API_KEY` or gateway-local `ORKET_API_KEY` to the previous value.
   - Restart host and gateway, then re-run smoke checks.

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
