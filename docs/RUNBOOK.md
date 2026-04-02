# Orket Operational Runbook

Last reviewed: 2026-04-01

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
1. API:
```bash
curl http://localhost:8082/health
```
2. API version:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/version
```
3. API heartbeat:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/system/heartbeat
```
4. API metrics:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/system/metrics
```
5. Webhook server:
```bash
curl http://localhost:8080/health
```

## Runtime Control and Run Inspection
1. Start one active run from an operator-selected path:
```bash
curl -X POST http://127.0.0.1:8082/v1/system/run-active -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"path\":\"<project_relative_path>\"}"
```
2. List known runs:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs
```
3. Inspect one run:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs/<session_id>
```
4. Inspect one run's metrics and token summary:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs/<session_id>/metrics
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs/<session_id>/token-summary
```
5. Inspect replay, backlog, and execution graph:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs/<session_id>/replay
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs/<session_id>/backlog
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/runs/<session_id>/execution-graph
```

## Approval Decisions
1. Inspect one approval:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/approvals/<approval_id>
```
2. Resolve one approval on the canonical Packet 1 path:
```bash
curl -X POST http://127.0.0.1:8082/v1/approvals/<approval_id>/decision -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"decision\":\"approve\",\"notes\":\"operator-reviewed\"}"
```
3. The active SupervisorRuntime approval-checkpoint family now admits three shipped bounded slices only: governed kernel `NEEDS_APPROVAL` on the default `session:<session_id>` namespace scope, plus governed turn-tool `write_file` and `create_issue` approval-required continuation on the default `issue:<issue_id>` namespace scope using the existing `tool_approval` plus `approval_required_tool:<tool_name>` request shape.
4. Packet 1 admits `approve` and `deny` only on this surface.
5. `notes` and `edited_proposal` may be sent as optional payload members, but they remain operator metadata and do not create an alternate resume or execution path.
6. On the bounded turn-tool `write_file` and `create_issue` slices, `approve` triggers one runtime-owned same-governed-run continuation on the already-selected `control_plane_target_ref`, while `deny` terminal-stops that same governed turn-tool run; operators do not call a separate resume API.
7. Approval list and detail inspection fail closed if the Packet 1 row carries an unsupported legacy lifecycle status or if payload-versus-reservation/operator-action projection truth drifts.
8. Canonical live proof for the shipped approval slice:
```bash
ORKET_DISABLE_SANDBOX=1 python scripts/nervous_system/run_nervous_system_live_evidence.py
```

## RuntimeOS Session Continuity
Authority: `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`

1. Start one host-owned interaction session:
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/sessions -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"session_params\":{\"reason\":\"operator-start\"}}"
```
2. Begin one subordinate turn on that session:
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/<session_id>/turns -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"workload_id\":\"stream_test_v1\",\"input_config\":{\"prompt\":\"hello\"},\"department\":\"core\",\"workspace\":\"workspace/default\",\"turn_params\":{}}"
```
3. Finalize one subordinate turn when the host has not already finalized it:
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/<session_id>/finalize -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"turn_id\":\"<turn_id>\"}"
```
4. Admitted Packet 1 context-provider inputs on this boundary remain limited to `session_params`, `input_config`, `turn_params`, `workload_id`, `department`, `workspace`, and host-resolved extension-manifest `required_capabilities`.
5. The requested `workspace` must remain under the configured workspace root or the turn request fails closed.
6. The canonical interaction-session context snapshot now exposes:
   - `context_version=packet1_session_context_v1`
   - ordered provider lineage: host continuity, host-validated turn request, and host-resolved extension capability metadata when present
   - the latest inspection-only session-context envelope for the admitted Packet 1 vocabulary
7. Inspect the host-owned session state:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>/status
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>/snapshot
```
8. Inspect replay without claiming continuation authority:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sessions/<session_id>/replay
```
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/sessions/<session_id>/replay?issue_id=<issue_id>&turn_index=<turn_index>&role=<role>"
```
9. Operator interpretation:
   - interaction-session timeline replay is inspection-only lineage for subordinate turns
   - targeted replay with `issue_id` plus `turn_index` remains run-session-only and fails closed on interaction sessions
10. Halt one session on the admitted cleanup-adjacent operator path:
```bash
curl -X POST http://127.0.0.1:8082/v1/sessions/<session_id>/halt -H "X-API-Key: <api_key>"
```
11. Cancel one interaction session or one subordinate turn:
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/<session_id>/cancel -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{}"
```
```bash
curl -X POST http://127.0.0.1:8082/v1/interactions/<session_id>/cancel -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"turn_id\":\"<turn_id>\"}"
```
12. Operator interpretation:
   - session detail, status, snapshot, and replay remain inspection-only surfaces
   - halt and cancel remain cleanup-adjacent operator commands only; they do not imply deletion or workspace cleanup

## Generic Extension Runtime Host API Examples
1. Inspect generic runtime status for the Companion extension:
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
3. Query, write, and clear generic extension memory:
```bash
curl -X POST http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/memory/query -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"scope\":\"profile_memory\",\"query\":\"key:companion_setting.config_json\",\"limit\":1}"
```
```bash
curl -X POST http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/memory/write -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"scope\":\"session_memory\",\"session_id\":\"<session_id>\",\"key\":\"turn.000001.user\",\"value\":\"hello\",\"metadata\":{\"kind\":\"chat_input\"}}"
```
```bash
curl -X POST http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/memory/clear -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"scope\":\"session_memory\",\"session_id\":\"<session_id>\"}"
```
4. Voice and speech examples on the generic host seam:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/voice/state
```
```bash
curl -X POST http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/voice/control -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"command\":\"start\"}"
```
```bash
curl -X POST http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/voice/transcribe -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"audio_b64\":\"UklGRg==\",\"mime_type\":\"audio/wav\"}"
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/tts/voices
```
```bash
curl -X POST http://127.0.0.1:8082/v1/extensions/orket.companion/runtime/tts/synthesize -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"text\":\"hello\",\"voice_id\":\"\"}"
```

## Companion BFF Examples
1. Companion product routes live in the external gateway/BFF, not in Orket core.
2. Inspect BFF status, config, and history:
```bash
curl http://127.0.0.1:3000/api/status
```
```bash
curl "http://127.0.0.1:3000/api/config?session_id=<session_id>"
```
```bash
curl "http://127.0.0.1:3000/api/history?session_id=<session_id>&limit=20"
```
3. Mutating Companion BFF routes require an `Origin` header that matches the gateway origin by default:
```bash
curl -X PATCH http://127.0.0.1:3000/api/config -H "Origin: http://127.0.0.1:3000" -H "Content-Type: application/json" -d "{\"session_id\":\"<session_id>\",\"scope\":\"next_turn\",\"patch\":{\"mode\":{\"role_id\":\"general_assistant\"}}}"
```
```bash
curl -X POST http://127.0.0.1:3000/api/chat -H "Origin: http://127.0.0.1:3000" -H "Content-Type: application/json" -d "{\"session_id\":\"<session_id>\",\"message\":\"hello\"}"
```
4. BFF model, voice, cadence, and clear-memory examples:
```bash
curl "http://127.0.0.1:3000/api/models?provider=ollama"
```
```bash
curl http://127.0.0.1:3000/api/voice/state
```
```bash
curl http://127.0.0.1:3000/api/voice/voices
```
```bash
curl -X POST http://127.0.0.1:3000/api/voice/control -H "Origin: http://127.0.0.1:3000" -H "Content-Type: application/json" -d "{\"command\":\"start\"}"
```
```bash
curl -X POST http://127.0.0.1:3000/api/voice/transcribe -H "Origin: http://127.0.0.1:3000" -H "Content-Type: application/json" -d "{\"audio_b64\":\"UklGRg==\",\"mime_type\":\"audio/wav\"}"
```
```bash
curl -X POST http://127.0.0.1:3000/api/voice/synthesize -H "Origin: http://127.0.0.1:3000" -H "Content-Type: application/json" -d "{\"text\":\"hello\"}"
```
```bash
curl -X POST http://127.0.0.1:3000/api/voice/cadence/suggest -H "Origin: http://127.0.0.1:3000" -H "Content-Type: application/json" -d "{\"session_id\":\"<session_id>\",\"text\":\"hello there\"}"
```
```bash
curl -X POST http://127.0.0.1:3000/api/session/clear-memory -H "Origin: http://127.0.0.1:3000" -H "Content-Type: application/json" -d "{\"session_id\":\"<session_id>\"}"
```

## Marshaller Inspection
1. List marshaller runs:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/marshaller/runs?limit=20"
```
2. Inspect one marshaller run or a specific attempt:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/marshaller/runs/<run_id>
```
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/marshaller/runs/<run_id>?attempt_index=<attempt_index>"
```

## Protocol Replay and Ledger Parity
Authority: `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`

1. Replay one protocol run for inspection:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/protocol/runs/<run_id>/replay
```
2. Compare two protocol runs:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/protocol/replay/compare?run_a=<run_a>&run_b=<run_b>"
```
3. Run one protocol replay campaign:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/protocol/replay/campaign?run_id=<run_a>&run_id=<run_b>&baseline_run=<run_a>"
```
4. Compare one protocol run against one SQLite ledger:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/protocol/runs/<run_id>/ledger-parity?sqlite_db_path=<workspace_relative_sqlite_path>"
```
5. Run one protocol ledger-parity campaign:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/protocol/ledger-parity/campaign?session_id=<session_a>&session_id=<session_b>&sqlite_db_path=<workspace_relative_sqlite_path>"
```
6. Operator interpretation:
   - these replay, comparison, and parity surfaces remain reconstruction or comparison views only
   - caller-provided `runs_root` and `sqlite_db_path` must remain under the configured workspace root or the request fails closed

## Files and System Utilities
1. Explore one allowed project path:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/system/explorer?path=workspace/default"
```
2. Read one allowed file:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/system/read?path=docs/RUNBOOK.md"
```
3. Save one allowed file:
```bash
curl -X POST http://127.0.0.1:8082/v1/system/save -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"path\":\"workspace/default/operator-note.txt\",\"content\":\"operator note\"}"
```
4. Inspect logs:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/logs?session_id=<session_id>&limit=50"
```

## Cards and Sandboxes
1. List cards and inspect one card:
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/cards?limit=20"
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/cards/<card_id>
```
2. Inspect card history and comments:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/cards/<card_id>/history
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/cards/<card_id>/guard-history
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/cards/<card_id>/comments
```
3. Archive selected cards:
```bash
curl -X POST http://127.0.0.1:8082/v1/cards/archive -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"card_ids\":[\"<card_id>\"],\"reason\":\"manual archive\"}"
```
4. List sandboxes, inspect logs, and stop one sandbox:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/sandboxes
```
```bash
curl -H "X-API-Key: <api_key>" "http://127.0.0.1:8082/v1/sandboxes/<sandbox_id>/logs?service=<service_name>"
```
```bash
curl -X POST http://127.0.0.1:8082/v1/sandboxes/<sandbox_id>/stop -H "X-API-Key: <api_key>"
```

## Runtime Policy and Settings
1. Inspect runtime-policy options and the effective runtime policy:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/system/runtime-policy/options
```
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/system/runtime-policy
```
2. Update one runtime-policy field:
```bash
curl -X POST http://127.0.0.1:8082/v1/system/runtime-policy -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"local_prompting_allow_fallback\":false}"
```
3. Inspect effective user settings and update one editable field:
```bash
curl -H "X-API-Key: <api_key>" http://127.0.0.1:8082/v1/settings
```
```bash
curl -X PATCH http://127.0.0.1:8082/v1/settings -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"local_prompting_allow_fallback\":false}"
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
