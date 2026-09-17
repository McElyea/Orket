# Orket Operational Runbook

Last reviewed: 2026-09-13

## Purpose
Operator commands for starting Orket, checking health, running core validations, and recovering from common failures.
Exact HTTP route and payload catalog authority lives in `docs/API_FRONTEND_CONTRACT.md`; this runbook keeps only high-signal operator examples and ownership notes.

## Quick Start

Run the CLI from the intended project directory. Discovery and the driver select
that directory's `model/` and `config/` assets; `--workspace` selects execution
output and does not select another project. Existing explicit application/driver
project roots retain precedence. Missing board assets still report reconciliation
failure. Root selection never moves existing project files or databases. See
`docs/specs/RUNTIME_PROJECT_ROOTS.md` for the installed-runtime contract.
Core installation includes `tzdata` for scheduled wake admission on hosts without
a system IANA timezone database; API admission still requires explicit schedule
evaluations or authenticated webhook deliveries, not an automatic scheduler.

API shutdown waits for active HTTP/WebSocket invocations, their awaited connector
work, registered background tasks, resources and engine. Admission stops with HTTP
503 (including health) or WebSocket close. A response already streaming may be
truncated; a received 200 header alone is not proof of a completed response.
Repeated caller cancellation waits for the same teardown; failure is reported
and retained. An app with failed teardown rejects new work and does not report
`closed=True`. Inspect the owner failure and durable run/effect state before
restarting; close does not authorize replay of uncertain effects. Scope and
remaining untracked-work/deadline limits: `docs/specs/API_RUNTIME_LIFECYCLE.md`.

Local-provider prompting uses the core-packaged registry at
`orket/runtime/config/local_prompt_profiles.json`; installed inference does not
require a checkout-local `model/core/contracts/` directory. To use an
operator-managed registry, set `ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH` to
its explicit path. A missing override fails closed, without reverting to the
packaged default.

1. Install dependencies:
```bash
python -m pip install --upgrade pip
python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]"
```
2. Configure environment:
```bash
copy .env.example .env
```
3. CLI runtime:
```bash
orket runtime
```
4. Named card runtime:
```bash
orket runtime --card <card_id>
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
orket runtime
```
2. Run one named card:
```bash
orket runtime --card <card_id>
```
3. API runtime:
```bash
python server.py
```

Compatibility-only source wrapper:
`python main.py [runtime arguments]` remains supported through `0.6.x`. The hidden
`--rock <rock_name>` alias remains accepted by that wrapper and `orket runtime`, but
new callers must use `--card`; removal requires an explicit `0.7.0` contract delta.

## Epic Publication Recovery

Runtime composition freezes relative database paths against the invocation
directory and uses the runtime database's sibling `control_plane_records.sqlite3`.
The execution workspace cannot choose another approval store. If startup reports
`E_RUNTIME_STORE_MIGRATION_REQUIRED`, stop old runtime owners and make SQLite-aware
backups of the runtime DB, epic journal and original control-plane DB. Preserve
artifacts and native continuation-lock files at their original paths. Then run:

```text
python -m orket.interfaces.runtime_store_cli --runtime-db <absolute-runtime-db> --legacy-control-plane-db <original-control-plane-db> --legacy-invocation-root <original-project> --actor-ref <operator-reference> --owners-stopped
```

The command copies one checked control-plane history, retains a binding in both
stores and preserves original request scopes. It refuses active owners, unrelated
source sessions, conflicting targets or damaged history. An interrupted binding
blocks runtime admission; rerun the same command to finish its checked cutover.
Do not remove a conflict to obtain success or restart an old writer afterward.
See `docs/specs/RUNTIME_STORE_BINDING.md` for supported migration and restart scope.

The standard Python runtime entrypoints `run_epic(..., session_id=...)` and
`run_card(..., session_id=...)` resume retained publication for a matching session
and request before resetting cards or dispatching work. Use a new session ID for
a fresh execution after any conflicting reservation has released. Recovery confirms the retained acceptance and the published
ledger, session, snapshot and success rows; a failed workload still raises after
its failure publication finishes.

Preserve `<runtime_db>.epic-publications.sqlite3` alongside the runtime DB,
control-plane DB and acceptance evidence. Use SQLite-aware backups that include
committed WAL content. The journal stores run/resource admissions, workload outcomes, preparation inputs, export-attempt state
and publication progress; it is not a disposable cache. Changed configuration/storage scope, damaged or
missing history, or lost completed effects are rejected. Do not clear the journal
to force reentry or reconstruct a plan from current output.

New standard entries reserve their workspace, build and card IDs in that journal
before session/card initialization. `E_EPIC_ADMISSION_RESOURCE_BUSY` identifies a
conflicting retained session; `E_EPIC_ADMISSION_OUTCOME_UNCERTAIN` means a previous
claim cannot authorize another initialization. The owner may still be running, or
may have stopped before any ledger exists. Claims have no expiry. Changing the
session ID does not bypass shared reservations. Explicit recovery before
initialization is described below; elapsed time or process death is not permission.
Verified complete publication releases resources and retains admission history.
Missing/damaged admission evidence refuses further preparation/publication.
Separately configured journals and arbitrary external writers are not fenced by
this standard-entry gate.

For an active admission v2 with `initialization_started=false`, a trusted local
operator can replace its owner through the canonical Python epic `run_card` call.
Inspect the existing journal using its validated repository read shown below.
Retain the observation and copy `owner_id`, `fencing_generation` and
`claim_ref()["digest"]` into a request; the stored row digest includes progress
and is not the claim reference. Supply a stable request ID, operator reference
and reason/evidence reference:

```python
from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository

journal = SQLiteEpicPublicationRepository(runtime_db)
async with journal.transaction(session_id) as transaction:
    retained = await transaction.get_admission()
if retained is None:
    raise ValueError("No retained admission to recover")
recovery = {
    "schema_version": "epic_admission_recovery_request.v1",
    "session_id": session_id,
    "request_id": "operator-recovery-1",
    "expected_owner_id": retained.owner_id,
    "expected_fencing_generation": retained.fencing_generation,
    "expected_claim_digest": retained.claim_ref()["digest"],
    "operator_ref": "operator:<identity>",
    "reason_ref": "evidence:<retained-observation>",
}
await engine.run_card(epic_id, **original_args, admission_recovery=recovery)
```

Use the original arguments, including the explicit matching `session_id`, and
the same workspace, databases, configuration and export settings. The application
checks the retained precondition atomically, records the replacement and common
`OperatorActionRecord` in admission history, then consumes initialization once.
A paused original owner fails its fence before session/card/control-plane writes.
Repeating the identical request observes that replacement; it may resume later
retained publication, but cannot start a second workload. Changed or superseded
requests reject. `E_EPIC_ADMISSION_RECOVERY_REQUIRES_PRE_INITIALIZATION` means this
operation cannot transfer ownership, even if the ledger is absent. Preserve the
initialization marker and all evidence. Admission v1 cannot prove this precondition
and is rejected without migration or digest backfill. This operation is available
on the Python epic `run_card` surface; no CLI or remote recovery endpoint exists.

Recovery begins at a retained workload outcome, before completion inspection and
initial preparation persistence. It preserves the original transcript, effective
configuration and failure identity; current acceptance still gates success.
Pending local stages can repeat without redispatching accepted cards.
`E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN` means a started invocation has no retained
termination result. Reentry refuses card reset and dispatch, even when cards have
acceptance receipts. Preserve the existing invocation and effects for owner
recovery; choosing a new session does not resolve the old uncertain work.
Enabled exports retain a Git commit intent before repository creation or push.
Automatic lost-result recovery reads the selected remote branch and confirms the commit,
subtree and manifest before completing publication. It does not push again.
`E_EPIC_EXPORT_OUTCOME_UNCERTAIN` means that confirmation is missing; automatic
retry and success publication remain refused. Preserve the attempt, local Git
objects and external evidence. Transport/integrity failures
also leave the attempt retained. Preparation v1 and insufficient old bindings
are rejected rather than backfilled. Export details and changed path convention:
`docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`.
For a new marked v2 preparation, the trusted local Python operator may explicitly
invoke `engine.run_card(original_epic, session_id=original_session,
export_recovery=request)` using the original build/configuration arguments. The
`epic_export_recovery_request.v1` object requires `session_id`, a stable
`request_id`, current `expected_owner_id`, `expected_fencing_generation`,
`expected_claim_digest`, `expected_intent_digest`, `operator_ref`, `reason_ref`,
and `resolution="retry_exact_commit"`. Read these owner values from the retained
`epic_export_dispatch.v1` record; the claim digest is its `claim_ref()["digest"]`.
Do not derive them from current workspace files or change stored evidence.
The operation records the replacement and confirms remote state before allowing
that caller one exact-commit push. It does not reset cards or execute workload.
Reusing the same request observes its disposition without another dispatch grant;
another uncertain attempt needs a new explicit request using the current owner.
Stale/superseded evidence and conflicting request reuse reject. A changed remote
branch may refuse the normal push; do not force-push or regenerate the intent to
clear the error. Unmarked older preparations cannot gain this retry permission.
This input is mutually exclusive with `admission_recovery` and `approval_recovery` and is not exposed by
a CLI command or authenticated remote recovery endpoint.
Changed build or full epic/team/environment definitions also
reject same-session reentry; old insufficient bindings are not backfilled.

For a newly marked consumed approval pause, the trusted local Python operator
may invoke `engine.run_card(original_epic, **original_args,
approval_recovery=request)`. Preserve the original explicit session, build,
configuration, workspace and database paths. Read the original claimed pause and
its recovery history from the publication journal; use this request shape:

```python
request = {
    "session_id": pause.session_id,
    "sequence": pause.sequence,
    "request_id": "operator-approval-recovery-1",
    "expected_pause_digest": pause.digest(),
    "expected_recovery_digest": latest_recovery.digest() if latest_recovery else None,
    "operator_ref": "operator:<identity>",
    "reason_ref": "evidence:<retained-interruption>",
    "resolution": "continue_resolved_pause",
}
await engine.run_card(original_epic, **original_args, approval_recovery=request)
```

Use a new stable request ID for each explicit grant. Repeating an identical
request observes its disposition and cannot dispatch the continuation again.
An interrupted grant needs a new request with the current recovery digest.
Recovery acquires the retained native lock before validating the original
decisions, admission, parent and pre-effect checkpoint. `owner_busy` preserves
the active holder. Missing/replaced lock files, unmarked old claims, completed
approved children, recorded steps/effects and orphan operations refuse this
operation. Preserve `<publication-journal>.continuations/` with the journal;
never delete a lock file, clear history, or reset a claimed pause to bypass a
refusal. A denial continues only the existing stop/failure path. Durable outcome
or next-pause retention precedes lock release; the continuing caller releases
before export, and other callers may finalize a retained outcome independently.
Export has its separate owner.
This input is mutually exclusive with `admission_recovery` and `export_recovery`
and has no CLI or remote endpoint. It does not resolve an arbitrary interrupted
workload, remote effects, or ownership in another journal.

Unknown post-initialization workload owner recovery, arbitrary custom writers and relocation to a
different installation remain required remediation work.
Durable behavior is specified in
`docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

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

The current BT-5 candidate exposes `authority_state` and shared `final_truth` on
outward status and summary. Generation-one history from earlier builds reports
`migration_required` until explicitly adopted. Stop old owners, retain a backup
of the database and its evidence, and inspect each run before adoption:

```powershell
python -m orket.interfaces.outward_authority_cli --db <outward.sqlite3> --run-id <run_id> --inspect
python -m orket.interfaces.outward_authority_cli --db <outward.sqlite3> --run-id <run_id> --expected-run-digest <digest-from-inspection> --actor-ref <operator-reference> --owners-stopped
```

Adoption accepts the reviewed current inputs; it cannot authenticate an old
instruction's original submission. It preserves existing workspace/target paths,
bindings, model/effect records and recovery fences, and does not dispatch work.
Claimed or uncertain work still requires its existing recovery disposition.
Generation-zero history stays quarantined. Source copied-history and composed
continuation/recovery and native migration interruption proof pass; installed
cutover acceptance remains open in
`docs/specs/OUTWARD_RUN_AUTHORITY.md`.

Native retained ledgers now use `docs/specs/OUTWARD_LEDGER_STORAGE_V2.md`.
`orket ledger summary <run_id>` performs live read-only integrity/completeness
inspection. `orket ledger verify <file>` checks only the exported file; its
`valid` result does not authenticate retained storage. Export preserves the v1
format and adds a separate `retained.anchor`. Keep a prior anchor independently
if later history must be compared against it. Authenticated
`POST /v1/runs/<run_id>/ledger/verify` takes
`{"external_anchor": <that complete anchor object>}` and reports `matched_prefix`
or an explicit mismatch; it does not authenticate the anchor's source or suffix.

Verification and ordinary export never seal hashes, migrate a database or create
a missing database. PII export commits its required audit before opening the
response snapshot. Native snapshots reject more than 100,000 events or 64 MiB of
aggregate payload JSON bytes instead of returning a prefix marked complete.
Unsealed legacy histories require explicit disposition. Stop incompatible workers
and already-authorized calls, retain the original database and v1 exports, then
rehearse the copied BT-2 migration from the repository root with new paths:

```bash
python -m scripts.governance.migrate_outward_ledger --source retained.sqlite3 --backup retained-backup.sqlite3 --destination candidate.sqlite3 --writers-stopped --out benchmarks/staging/outward_ledger_migration.json
```

Add `--allow-unsealed` only to explicitly import missing original hash cells.
Every available hash is still checked; mismatches are refused and never repaired.
The retained SQLite backup includes committed WAL pages, and its digest anchors
imported history. Existing v1 cells and execution generations remain unchanged;
generation-0 runs stay quarantined. The candidate remains inactive. This command
does not automatically fence processes or establish historical authenticity.

Review the report and preserve the backup independently. `started` or `failed`
does not admit a candidate. After refusal or interruption, retain every copy and
retry with new backup/destination paths after resolving the cause. Do not restore
old hash-repair behavior or delete evidence to obtain a green result. The BT-1
approval-copy command below does not perform ledger migration; the ledger command
does not promote unbound proposals or grant execution permission. Staging report
maintenance follows `docs/CONTRIBUTOR.md`.
The Phase 4 outward ledger path uses API-backed export and offline verification:

```bash
orket ledger export <run_id> --out ledger.json
orket ledger export <run_id> --types proposals,decisions --out ledger.partial.json
orket ledger verify ledger.json
orket ledger summary <run_id>
```

`orket ledger verify <file.json>` is offline and does not require a running Orket instance. Filtered exports verify as partial views anchored to the canonical ledger hash; they do not claim omitted event payload verification.

## Trust Handoff Packet 1 Proof
Packet 1 handoff proof packages are host-issued local packages over one committed approved outward source run and one target B run id. The verifier is offline and consumes package bytes only.

```bash
python scripts/proof/emit_trust_handoff_envelope.py --source-run-id <source_run_id> --target-agent-id <target_run_id> --scope-id <scope_id> --out benchmarks/results/proof/trust_handoff_envelope_package.v1
python scripts/proof/verify_trust_handoff_envelope.py --package benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_verifier_report.json
python scripts/proof/run_trust_handoff_corruption_suite.py --base benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_corruption_report.json
```

B-side admission is enabled with `task.acceptance_contract.handoff_required=true`. The contract must also include `handoff_policy_compatibility_scope_id`, `handoff_envelope_package_path`, and `expected_source_agent_id`. The submitted B `run_id` is the target agent identity for Packet 1, so it must match the package `target_agent_id`.

## Live Governed Run Evidence Bundle
Use this workflow when you need public proof that the outward pipeline invoked a live model provider, derived a governed connector proposal from model output, gated the connector effect on approval, and verified ledger integrity offline.

1. Start the API with a fresh outward pipeline DB, sandbox disabled for routine local proof, and a real configured provider/model:
```powershell
$env:ORKET_DISABLE_SANDBOX="1"
$env:ORKET_OUTWARD_PIPELINE_DB_PATH=".tmp/live_governed_run_bundle_v1.sqlite3"
$env:ORKET_LLM_PROVIDER="llama_cpp"
$env:ORKET_MODEL_STREAM_REAL_PROVIDER="llama_cpp"
$env:ORKET_MODEL_STREAM_REAL_MODEL_ID="<model_id>"
python server.py --host 127.0.0.1 --port 8082
```
2. Confirm `/health` returns `{ "status": "ok" }` and capture `X-Orket-Version` from an authenticated `/v1/*` response using case-insensitive header lookup.
3. Submit `POST /v1/runs` with `task.acceptance_contract.governed_tool_call` as the single governed-tool-family gate, or `task.acceptance_contract.governed_tool_sequence` for ordered multi-turn proof. For public proof, include an intentional synthetic-shortcut probe when useful: make the acceptance-contract tool args differ from the model-requested tool args in the task instruction.
4. Capture the submitted request body as `submitted_request.json`. Redact secrets, but preserve the acceptance contract, task instruction, and hashes proving the contract args differ from the model-requested args.
5. Capture model evidence from `workspace/<namespace>/runs/<run_id>/`:
   - `model_invocation.json` plus `model_invocation_turn_<n>.json` for each model turn
   - `model_prompt_redacted.json` plus `model_prompt_redacted_turn_<n>.json`
   - `model_response_redacted.json` plus `model_response_redacted_turn_<n>.json`
   - `proposal_extraction.json` plus `proposal_extraction_turn_<n>.json`
6. Capture workspace state before approval, pending approval payload, approval decision, workspace state after approval, produced artifact, final run status, run events, and run summary.
7. Emit the outward pipeline evidence graph directly from the outward `run_id`:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --workspace-root <workspace_root> --outward-pipeline-db <sqlite_path>
```
The expected graph result is `graph_kind=outward_pipeline`, with JSON and SVG artifacts under `workspace/<namespace>/runs/<run_id>/`. Do not substitute legacy ProductFlow or `runs/<session_id>/` graphs for this proof.
8. Export and verify ledgers:
```bash
orket ledger export <run_id> --out ledger_full.json
orket ledger export <run_id> --types proposals,decisions --out ledger_partial_decisions.json
orket ledger verify ledger_full.json
orket ledger verify ledger_partial_decisions.json
```
The full export must verify as `valid`; the filtered export must verify as `partial_valid`, not `valid`.
9. Copy the full ledger, mutate exactly one disclosed payload character, then verify the tampered copy offline. The expected result is `invalid`.
10. Redact secrets before hashing, write `manifest.json` with SHA-256 hashes for emitted artifacts, and write `bundle_verification_report.md`.

Public claim boundaries to preserve in the report:
1. This proves one local live outward pipeline run.
2. It does not prove replay stability, cross-run determinism, cloud readiness, third-party connector auto-discovery, or model-output reproducibility.
3. It proves governance of the effect, not reproducibility of the model content.

For denial-path proof, use the public approval denial endpoint and verify `proposal_denied`, no `tool_invoked` event for the denied proposal, terminal run status `completed`, and absence of the target effect. For out-of-scope path proof, verify `proposal_policy_rejected` appears in the ledger before any human approval proposal and that the attempted path is visible in policy-safe proposal artifacts.

## Outward Pipeline Connectors
Connector results now report measured monotonic `duration_ms` with `timing`
provenance, or null with an unavailable reason. The scope is the awaited connector
invocation, including cleanup actually awaited. It excludes approval/publication
and does not establish remote-effect or descendant lifetime. Old provenance-free
zeros are unmeasured history; do not use them for capacity claims. Runtime log
envelopes use v2 and preserve null/fractional durations. See
`docs/specs/CONNECTOR_INVOCATION_TIMING.md` for receipt recovery and migration.

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
4. Submit one outward-facing run that gates a model-produced governed `write_file` proposal:
```bash
curl -X POST http://127.0.0.1:8082/v1/runs -H "Content-Type: application/json" -H "X-API-Key: <api_key>" -d "{\"run_id\":\"demo-write\",\"task\":{\"description\":\"Write approved file\",\"instruction\":\"Call write_file\",\"acceptance_contract\":{\"governed_tool_call\":{\"tool\":\"write_file\",\"args\":{\"path\":\"approved.txt\",\"content\":\"approved content\"}}}},\"policy_overrides\":{\"approval_required_tools\":[\"write_file\"]}}"
```
The acceptance contract selects and constrains the governed tool family; the outward execution service invokes the configured model and creates the approval proposal from the validated model-produced tool call.
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
15. The outward-facing approval surface admits `approve` and `deny` only for stored outward proposals. Inspect the returned approval status: a repeated or contradictory request returns the original decision, and a request reaching the serialized decision boundary at or after expiry returns `expired`. Proposal, run projection and event writes are atomic when their SQLite paths match; configuration with different paths fails closed. New approvals bind complete calls and persist one effect claim before dispatch. Stale approvals cannot select another turn; HTTP 409 with `E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN` means the owner may still execute or an effect lacks a conclusive receipt. Do not retry the command manually to clear that state. A saved receipt can finish publication on retry without execution. Use the explicit pre-intent recovery operation below for a claim without intent. Legacy runs remain quarantined; reconciliation/replacement is unsupported; ready or observed model admission can resume through run reentry below, and claimed model work has the explicit recovery path described there. Do not treat this checkpoint as acceptance of concurrent or multi-turn outward autonomy. The active lifecycle contract is `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`.
16. The active approval-checkpoint family admits four bounded shipped slices only: governed kernel `NEEDS_APPROVAL` on the default `session:<session_id>` namespace scope, plus governed turn-tool `write_file`, `create_directory`, and `create_issue` approval-required continuation on the default `issue:<issue_id>` namespace scope.
17. Packet 1 admits `approve` and `deny` only on this surface. `notes` and `edited_proposal` remain bounded operator metadata and do not create an alternate resume path.
18. The bounded turn-tool `write_file`, `create_directory`, and `create_issue` contract requires `approve` to continue the same governed run on the already-selected `control_plane_target_ref`, while `deny` terminal-stops it. The 2026-09-13 BT-3 candidate retains a pending epic as unfinished execution with its admission, original request and child identity. The existing decision route resumes that request after all pause decisions resolve; repeated identical decisions are idempotent and a concurrent continuation cannot consume the pause again. Preserve the runtime DB, sibling control-plane store, epic journal, continuation lock files and artifacts together. Relative paths freeze at composition; historical relative scopes require the explicit offline migration described above. Previously published failures are not reopened and old split custom/global stores are not merged. Automatic redispatch of a consumed pause remains refused; new marked pre-effect pauses support the explicit local `approval_recovery` operation described above after the retained native lock becomes available. Unmarked or post-effect continuation remains outside that recovery grant. Scoped restart and live write-file proof pass; the full BT-3 gate stays open.
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
Use `orket runtime` for runtime commands.

1. Help:
```bash
orket runtime --help
```
2. Show board:
```bash
orket runtime --board
```
3. Run an epic:
```bash
orket runtime --epic <epic_name>
```
4. Replay one turn:
```bash
orket runtime --replay-turn <session_id>:<issue_id>:<turn_index>[:role]
```
5. Archive related cards:
```bash
orket runtime --archive-related <token> --archive-reason "manual archive"
```

## Native verification cleanup

Native `RuntimeVerifier` commands carry `process_lifetime` observations under
`docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`. A completed command requires
confirmed descendant cleanup and complete capture before it can pass. Timeout is
exit 124; failed supervision or excess output is exit 125. An exit code alone does
not establish that every process stopped. Later commands are not admitted after a
command failure.

On cancellation, inspect `verification_process_cancelled` and the
`CommandProcessCancelled.lifetime` observation. `cleanup_confirmed=false`
means termination remains unconfirmed. Preserve the reason, backend, supervisor
and command IDs, and diagnostics for investigation. These historical PIDs are not
safe authority to kill a later process with a reused PID. Do not clear retained
run ownership or replay commands merely because cancellation returned.

The native implementation covers Windows jobs and Linux subreapers. Abrupt host
death recovery and hostile-code containment remain unproved. Propagating uncertain lifetime into
every epic terminal/admission consumer remains BT-4 work. Raw stream retention is
bounded at 4 MiB each; excess output fails and cannot satisfy acceptance.

The outward `run_command` connector uses the same native supervisor. Its results
and `result_summary` carry `process_lifetime`; raw stdout/stderr counts describe
captured bytes before replacement decoding, with 256-character previews and the
same 4 MiB per-stream limit. Connector return codes are actual nullable codes,
not verifier exit projections. Inspect `outward_command_cancelled` and
`outward_connector_interrupted` for cancellation observations. Missing cleanup
acknowledgement raises `E_COMMAND_EXECUTION_UNCERTAIN` (HTTP 409 on the governed
API); the retained dispatch remains fenced with
`E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN` on later approval. Preserve that intent
and evidence. Terminated processes may already have caused external effects;
neither cleanup nor timeout authorizes replay. Historical receipts without
lifetime evidence remain historical. Supporting logs are not recovery authority.

Fixture callers use `await FixtureVerificationService(workspace).verify(verification)`
or public `Orchestrator.verify_issue`. The old synchronous fixture entrypoints
raise a migration error before execution. Production native fixtures still require
the explicit unsafe override; path containment is not a hostile-code sandbox.
Docker fixtures retain `owned_container.v1` in `VerificationResult.process_lifetime`.
The owner removes only its inspected immutable ID and requires successful daemon
absence observation. A lost create response may remain uncertain even when an
immediate listing is empty. Inspect `fixture_verification_cancelled` or
`fixture_verification_uncertain`; keep the name, owner ID, immutable ID and command
observations for recovery. Cancellation/uncertainty does not replace `last_run`.

Explicit live container acceptance:
`ORKET_DISABLE_SANDBOX=1 python scripts/acceptance/verify_fixture_container_lifetime.py`.
It requires Docker and the selected verification image, creates disposable
`orket-verification-*` containers, and confirms teardown in the same execution.
The stable result is `benchmarks/results/acceptance/fixture_container_lifetime.json`.
This command is separate from general pytest and retains rerun differences.

Named runtime execution now projects a typed result, including session/run IDs,
retained evidence references, observed lifecycle, classification and a diagnostic
reason. `--card`, `--epic` and legacy `--rock` share the same exit policy: 0 only
for verified success after cleanup, 1 for other returned outcomes, 130 for caller
interruption. Typed cancellation reports the retained run observation and evidence
references after cleanup; it does not mark the durable run cancelled. A
required-source-attribution failure remains `terminal_failure`
and exits 1. Approval waits and unresolved recovery remain open authority; retry
with the original request and retained identity rather than starting replacement
work that bypasses admission. Collection members use distinct session/build IDs
with `-member-<1-based index>` suffixes; the group result preserves all declared
members and the outcomes observed before any stop. Python callers consume the
explicit `transcript` field for history and `succeeded` for continuation gates.
See `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md` and the architectural-truth
plan for compatibility changes and current proof limits.

## llama.cpp provider verification

All provider-neutral runtime and tool entrypoints default to llama.cpp, with
`orcarouter_qwen3.8-27b-uncensored-q4_k_l` as the shared local model. Explicit
settings override these defaults. Keep the operator-managed server running;
an unavailable llama.cpp endpoint never selects another provider. Local Ollama
installation is not required. Development/testing order is llama.cpp, LM Studio,
then Ollama, with compatibility providers selected explicitly.

From the repository root, run:

```text
python scripts/proof/run_llama_cpp_integration.py --model orcarouter_qwen3.8-27b-uncensored-q4_k_l --extension-root C:/Source/OrketExtensions/GoverenedAgentLoop
```

This executes real governed-agent CLI/API/approval flows and streaming/ODR paths,
with sandbox creation disabled, and writes
`benchmarks/results/providers/llama_cpp_integration.json` with rerun history.
It proves the source-worktree integration, separately from installed-release
acceptance. Published core 0.6.0 artifacts predate this integration.

For streaming, set `ORKET_MODEL_STREAM_PROVIDER=real`,
`ORKET_MODEL_STREAM_REAL_PROVIDER=llama_cpp`, and
`ORKET_MODEL_STREAM_REAL_MODEL_ID` to the same exact alias. Set
`ORKET_MODEL_STREAM_OPENAI_USE_STREAM=true` for SSE. llama.cpp endpoint overrides
use `ORKET_LLAMA_CPP_BASE_URL` or `ORKET_LLM_LLAMA_CPP_BASE_URL`; LM Studio endpoint
settings do not redirect llama.cpp. The streaming gate, consistency runner, model
listing, and quant tuning wrapper accept `llama_cpp` directly. ODR role providers
also accept `llama_cpp`; its model residency is reported as `operator_managed`,
with no unload attempted. Full quant sweeps and multi-model residency need the
operator to serve each selected model.

## Governed-Agent Bounded CLI

Future provider development and live testing follow the
[contributor provider policy](CONTRIBUTOR.md#local-provider-development-and-testing):
llama.cpp, then LM Studio, then Ollama, with llama.cpp as the preferred live-test
provider. Use `--model <exact-served-model>` for llama.cpp, or select
`--provider llama_cpp|lmstudio|ollama|openai_compat` explicitly. Override its endpoint
with `--provider-base-url <url>`. Existing Ollama-specific flags remain available;
combining them with another provider is rejected.

The admitted agent CLI requires a persisted extension catalog and a validated
initial `agent_iteration_request.v1` JSON. Select exactly one provider posture.

For staged ticket-report acceptance, include only batch A in that request and
add `--continuation-inputs <json>`. The separate JSON object maps `"2"` to a
list containing batch B's digest-bound `authoritative_context` materialization.
For API/manual/scheduled/webhook wakes, supply that object as
`dispatch.continuation_inputs`. It stays host-owned, binds the configuration,
and reaches the next child only after host authorization. Exact retries retain
the same plan. Inspection shows A on iteration 1 and B plus the accepted prior
result on iteration 2. The effect demo uses `proposal_iteration=2` and a
three-iteration run budget so approval can resume one final verification step.

```bash
orket agent submit <workload_id> --db <sqlite_path> --catalog <catalog_json> --request <request_json> --creation-timestamp-utc <timestamp> --decision-timestamp-utc <timestamp> --decision-timestamp-utc <timestamp> --next-lease-expires-at-utc <timestamp> --deterministic-fixture --json
```

For the preferred live llama.cpp run, replace `--deterministic-fixture` with
`--provider llama_cpp --model orcarouter_qwen3.8-27b-uncensored-q4_k_l`.
Start an operator-owned `llama-server` first, serving that exact alias at
`http://127.0.0.1:8080/v1`. Its alias must match the lowercase GGUF filename stem
under `ORKET_LLAMA_CPP_GGUF_MODEL_ROOT` (default `D:/models/GGUF`) and an admitted
prompt profile. The Qwen3.8 text profile uses an 8192-token context and the
packaged `qwen38_text_chatml.jinja` template. The verified server is upstream
`b10809` (`5266f24da`), with prompt caching enabled. On this workstation:

```powershell
$qwenTemplate = python -c "from importlib.resources import files; print(files('orket.runtime.config').joinpath('qwen38_text_chatml.jinja'))"
& D:/llama.cpp-releases/b10809/llama-server.exe `
  --model D:/Models/GGUF/bartowski/orcarouter_Qwen3.8-27B-Uncensored-GGUF/orcarouter_Qwen3.8-27B-Uncensored-Q4_K_L.gguf `
  --alias orcarouter_qwen3.8-27b-uncensored-q4_k_l `
  --host 127.0.0.1 --port 8080 --n-gpu-layers 99 --flash-attn on `
  --ctx-size 8192 --parallel 1 --jinja --reasoning off `
  --cache-prompt --cache-ram 8192 --chat-template-file $qwenTemplate
```

The operator owns this process. The profiled adapter verifies actual template
bytes, native rendered prompts and token budgets before generation. A template
mismatch fails closed. The old `dd7cad7` no-cache workaround is superseded by
this pinned setup; retain its evidence only for rollback investigation. All
roles may use this model; additional models require their own served aliases
and admission proof.

Rerun bounded cache/cancellation, stop/sampling and repair checks with:

```text
python scripts/proof/run_qwen38_runtime_readiness.py
python scripts/proof/run_qwen38_repair_readiness.py
```

Canonical evidence is under
`benchmarks/results/protocol/local_prompting/qwen38_promotion/`. The larger
promotion corpus uses `scripts/protocol/run_local_prompting_conformance.py`
with `--provider llama_cpp --model orcarouter_qwen3.8-27b-uncensored-q4_k_l
--suite promotion --strict --out-root benchmarks/results/protocol/local_prompting/qwen38_promotion`.
Template audit and readiness gates remain mandatory; volume alone is not promotion.

For a live single-model Ollama run, replace `--deterministic-fixture` with
`--ollama-model <exact-installed-model>`. For fixed multi-model roles, add
`--planner-model`, `--actor-model`, and `--critic-model`; omitted role overrides
use the exact default model. Model auto-selection and auto-load are disabled.

```bash
orket agent submit <workload_id> --db <sqlite_path> --catalog <catalog_json> --request <request_json> --creation-timestamp-utc <timestamp> --decision-timestamp-utc <timestamp> --decision-timestamp-utc <timestamp> --next-lease-expires-at-utc <timestamp> --ollama-model qwen2.5:7b --actor-model qwen2.5-coder:7b --json
```

Inspect durable state and compare recorded continuation decisions:

```bash
orket agent inspect <run_id> --db <sqlite_path> --json
orket agent replay <run_id> --db <sqlite_path> --json
```

Replay uses one read-only database snapshot and does not create or initialize a
store. Its V2 response reports expected, retained, compared and matched counts.
Only `status=matched` exits successfully; `no_decisions` means no evaluation,
`insufficient_evidence` identifies missing history/inputs, and `mismatch` identifies
invalid or differing evidence. Historical decisions without an input digest stay
insufficient through schema initialization. Preserve their original records.
A match covers recorded continuation decisions against the retained step
inventory; it does not verify objective satisfaction or external effects.

To request pause or terminal stop after the current iteration, inspect its
invocation id and submit a stable operator action:

```bash
orket agent pause <run_id> --db <sqlite_path> --invocation-id <invocation_id> --action-id <stable_id> --actor-ref <operator_ref> --timestamp-utc <UTC> --json
orket agent stop <run_id> --db <sqlite_path> --invocation-id <invocation_id> --action-id <stable_id> --actor-ref <operator_ref> --timestamp-utc <UTC> --json
```

The authenticated API equivalent is `POST /v1/agent-runs/{run_id}/controls`
with `command`, `invocation_id`, `action_id`, `actor_ref`, and `timestamp_utc`.
The acknowledgement says `requested`; inspect the persisted decision to confirm
the boundary was reached. Late commands return conflict. A verified paused
result resumes through `POST /v1/agent-runs/{run_id}/resume` with the same
timing fields as effect resume. An independent cancellation CLI cannot confirm
that another process's child was reaped; residual uncertainty stays explicit.

Optional reference-extension objective memory requires both `memory.query` and
`memory.write` in the request's admitted capabilities and
`extension_config.objective_memory=true`. Only earlier verified results in that
run are eligible. The returned context remains advisory, with one query per
iteration and host provenance. Other memory scopes are refused.

After an approved write loses its process before journaling, repeat the same
resolution. Matching report bytes are observed and reconciled without another
write. Missing/different bytes or existing uncertainty remain blocked for
recovery; approval replay does not blindly retry a mutation.

Publish an immediate cancellation request:

```bash
orket agent cancel <run_id> --db <sqlite_path> --action-id <id> --actor-ref <ref> --timestamp-utc <timestamp> --reason <reason> --cancellation-epoch <n> --json
```

The CLI prints `proof_posture=deterministic_fixture_not_live_model` or
`proof_posture=live_local_model`, plus observed path/result, resolved targets,
and durable iteration/model receipts. A model-target failure or invalid model
JSON fails explicitly; it does not fall back silently.

The currently proven agent effect path is application-owned, not a separate
extension or generic CLI executor. It admits only exact issue-scoped `read_file`
observation and approval-required `write_file`, and resumes only after observed
or reconciled receipts plus an accepted checkpoint and explicit operator action.
Cancellation invoked in a later CLI process cannot reap a child owned by an
already-exited process; in-process operator cancellation owns child cancel/reap,
while the CLI command durably fences and closes the recorded run.

## Governed-Agent Durable Wakes

The API runtime always composes the durable wake and inspection services, but
continuous dispatch is disabled by default. Authenticated `POST
/v1/agent-wakes` remains useful while disabled: it persists work for a later
explicitly configured supervisor lifecycle.

Set these host-owned values before `python server.py` to activate dispatch:

```text
ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED=1
ORKET_GOVERNED_AGENT_DB_PATH=<sqlite_path>              # optional; canonical control-plane DB by default
ORKET_GOVERNED_AGENT_PROVIDER=llama_cpp
ORKET_GOVERNED_AGENT_MODEL=orcarouter_qwen3.8-27b-uncensored-q4_k_l
ORKET_GOVERNED_AGENT_BASE_URL=http://127.0.0.1:8080/v1
ORKET_GOVERNED_AGENT_CAPACITY_LIMIT=1
```

Exact role overrides are
`ORKET_GOVERNED_AGENT_PLANNER_MODEL`,
`ORKET_GOVERNED_AGENT_ACTOR_MODEL`, and
`ORKET_GOVERNED_AGENT_CRITIC_MODEL`. `deterministic_fixture` is also an explicit
provider posture for deterministic verification; it is not live-model proof.
Claim timing can be bounded with
`ORKET_GOVERNED_AGENT_CLAIM_LEASE_SECONDS`,
`ORKET_GOVERNED_AGENT_CLAIM_RENEWAL_SECONDS`, and
`ORKET_GOVERNED_AGENT_IDLE_WAIT_SECONDS`. Renewal must be shorter than the
lease. Inventory timeout uses `ORKET_GOVERNED_AGENT_INVENTORY_TIMEOUT_SECONDS`.
The generic base URL overrides provider defaults. Existing
`ORKET_GOVERNED_AGENT_OLLAMA_MODEL` and `ORKET_GOVERNED_AGENT_OLLAMA_BASE_URL`
apply only with explicit `ORKET_GOVERNED_AGENT_PROVIDER=ollama`. With no
provider set, llama.cpp is selected even if legacy Ollama model variables remain.
Set the provider explicitly when switching an existing environment. Existing runs retain their configuration
digest; switching providers requires a new run.

The JSON body uses one caller-stable occurrence id, either a `new_run` workload
or an `existing_run` target, and a `governed_agent_wake_dispatch.v1` object. The
dispatch object carries the same fully validated `agent_iteration_request.v1`
and explicit timestamps used by the bounded CLI. A repeated occurrence with
identical content is idempotent; contradictory reuse is `409`.

Manual ingress uses the same dispatch envelope and database without starting a
second runtime owner:

```text
orket agent wake enqueue --db <sqlite_path> --workload-id governed-agent-loop --occurrence-id <stable_id> --request <request.json> --creation-timestamp-utc <UTC> --decision-timestamp-utc <UTC> --next-lease-expires-at-utc <UTC> --json
orket agent wake list --db <sqlite_path> --json
orket agent wake inspect <wake_id> --db <sqlite_path> --json
orket agent wake cancel <wake_id> --db <sqlite_path> --action-id <stable_action_id> --actor-ref <operator_ref> --timestamp-utc <UTC> --reason <reason> --expected-cancellation-epoch <current> --cancellation-epoch <next> --json
orket agent wake recover <wake_id> --db <sqlite_path> --action-id <stable_action_id> --actor-ref <operator_ref> --timestamp-utc <UTC> --reason <reason> --expected-fencing-generation <current> --resolution requeue|confirm_cancelled --child-confirmed-stopped --effect-uncertainty-cleared --evidence-ref <receipt_ref> --json
orket agent wake actions <wake_id> --db <sqlite_path> --json
```

Repeat `--decision-timestamp-utc` and `--next-lease-expires-at-utc` as required
by the request budget. Use `--run-id <run_id>` instead of `--workload-id` for an
existing run. The CLI persists `source=manual` and exits; an explicitly enabled
supervisor using the same database owns all later provider and child work.

Operator reads are:

```text
GET /v1/agent-runtime/status
GET /v1/agent-wakes
GET /v1/agent-wakes/<wake_id>
GET /v1/agent-wakes/<wake_id>/actions
GET /v1/agent-schedules/<schedule_id>/evaluations
GET /v1/agent-webhooks/<issuer_ref>/deliveries
GET /v1/agent-runs/<run_id>
GET /v1/agent-runs/<run_id>/replay
```

Authenticated wake mutations are `POST /v1/agent-wakes/<wake_id>/cancel` and
`POST /v1/agent-wakes/<wake_id>/recover`; their JSON bodies use the same fields
as the CLI flags above. These control wake ownership only. Run-level
`orket agent cancel` remains a separate operator authority.

When run inspection reports `effect_approval_required`, resolve the listed
write approval through authenticated `POST
/v1/agent-runs/<run_id>/effects/<approval_id>/resolve`. Denial requires
`decision=denied`, `actor_ref`, and a canonical UTC `timestamp_utc`; it closes
the run without a write or resume wake. Approval additionally requires
`next_lease_expires_at_utc`, enough `decision_timestamps_utc` entries for the
remaining run budget, and `next_lease_expiries_utc` entries for any iterations
after the resumed one. Safe approval returns `status=resume_queued`. Exact
retry is idempotent. The run remains `operator_blocked` until the returned wake
is claimed; the claimed worker validates the aggregate effect checkpoint,
every safe receipt, and the exact request-bound operator action before changing
the run to `executing`. An unobserved write returns `recovery_required`, moves
the run to recovery pending, and queues no resume.

A paused result containing only safely observed reads has no write approval.
Continue it through authenticated `POST
/v1/agent-runs/<run_id>/effects/resume` with the approval timing fields above,
but without `decision`. It applies the same complete checkpoint, operator
authorization, durable wake, and claimed-wake activation checks.

Authenticated scheduled ingress is `POST
/v1/agent-schedules/<schedule_id>/evaluations`. Each request supplies a stable
`evaluation_id`, IANA `timezone`, UTC `observed_at_utc`, bounded
`misfire_grace_seconds`, `missed_policy` of `skip` or `fire_once`, the fixed
`coalescing_policy` value `latest`, and one to 100 due `occurrences`. Each
occurrence supplies naive `scheduled_for_local`, explicit DST `fold` (`0` or
`1`), target fields, and the normal dispatch envelope. Future occurrences,
nonexistent local times, noncanonical folds, unknown fields, and unsupported
policies fail closed. The selected wake and durable evaluation receipt commit
atomically; exact request replay is idempotent and contradictory evaluation-id
reuse returns `409`. A fully skipped evaluation still persists its receipt.
Submit stable, non-overlapping evaluation windows.

Authenticated webhook ingress is `POST
/v1/agent-webhooks/<issuer_ref>/deliveries/<delivery_id>`. It is disabled unless
all three host-owned values are configured:

```text
ORKET_GOVERNED_AGENT_WEBHOOK_ISSUER_REF=<exact-issuer>
ORKET_GOVERNED_AGENT_WEBHOOK_KEY_ID=<exact-key-id>
ORKET_GOVERNED_AGENT_WEBHOOK_SECRET=<shared-secret>
ORKET_GOVERNED_AGENT_WEBHOOK_REPLAY_WINDOW_SECONDS=300  # optional, 1..3600
```

The request must carry `X-API-Key`, `X-Orket-Webhook-Key-Id`, a canonical UTC
`X-Orket-Webhook-Timestamp` such as `2026-09-07T18:00:00.000000Z`, and
`X-Orket-Webhook-Signature: sha256=<lowercase-hex>`. Compute HMAC-SHA256 over
these newline-separated UTF-8 fields:

```text
orket-governed-agent-webhook.v1
<issuer_ref>
<delivery_id>
<canonical_timestamp>
sha256:<raw_body_sha256_lowercase_hex>
```

The JSON body is limited to 1 MiB and contains `target_kind`, the corresponding `target_run_id` or
`workload_id`, and the normal `dispatch` envelope; delivery identity derives
the occurrence id. Exact signed raw-content retry is idempotent. Changed
content or signed metadata under a retained issuer/delivery id returns `409`.
Stale/future timestamps, issuer/key mismatch, invalid signatures, and malformed
content fail closed. The signing secret and raw signature are never retained or
projected. Rotate by changing key id and secret together during a bounded
caller/host cutover; this first increment configures one active issuer/key.

All `/v1` routes retain the canonical API-key boundary. A queued wake does not
itself authorize continuation, model work, effects, or reopening a terminal
run. The dispatcher reuses the catalog-resolved bounded loop and consumes a
durable capacity claim. It rechecks that claim before broker/result/effect
publication and after external effect observation. A resume wake also requires
the exact operator authorization, full safe receipt coverage, and accepted
aggregate checkpoint. Scheduled and webhook ingress use the same queue and
supervisor after their durable evaluation or delivery receipt commits.

All supervisors sharing one governed-agent database must use the same
`ORKET_GOVERNED_AGENT_CAPACITY_LIMIT` value. A cancelled or expired claim
with unresolved provider-call uncertainty continues to consume one capacity
slot until explicit recovery; do not delete or blindly requeue it to restore
throughput. Recovery requires the current fencing generation, an explicit
`requeue` or `confirm_cancelled` resolution, confirmation that the prior child
stopped, confirmation that effect uncertainty is cleared, and at least one
evidence reference. Failed preconditions retain wake state and publish a durable
conflict receipt. Reusing an action id with different content also conflicts.

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
1. Select a covered control-plane or outward pipeline `run_id`.
2. For legacy control-plane/session graphs, make sure the corresponding `runs/<session_id>/` artifacts are present under your workspace root.
3. For outward pipeline graphs, provide the outward pipeline SQLite path with `--outward-pipeline-db`; a legacy `runs/<session_id>/` root is not required.
4. Run:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>
```
5. Open or inspect the generated artifacts:
   - `runs/<session_id>/run_evidence_graph.json`
   - `runs/<session_id>/run_evidence_graph.mmd`
   - `runs/<session_id>/run_evidence_graph.html`
   - `workspace/<namespace>/runs/<run_id>/run_evidence_graph.json` for outward pipeline graphs
   - `workspace/<namespace>/runs/<run_id>/run_evidence_graph.svg` for outward pipeline graphs

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
4. Override outward pipeline DB path:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --outward-pipeline-db <sqlite_path>
```
5. Force a known session id:
```bash
python scripts/observability/emit_run_evidence_graph.py --run-id <run_id> --session-id <session_id>
```
6. Fix the generation timestamp for deterministic proof runs:
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
5. For outward pipeline runs, `graph_kind=outward_pipeline` means the graph was generated from outward run records, run events, proposal records, tool invocation events, summary, and ledger references.
6. If Orket cannot truthfully locate either the selected run's `runs/<session_id>/` root or a matching outward run in the outward pipeline store, the command fails closed with `E_RUN_SESSION_NOT_LOCATED`.

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

## Outward approval store upgrade (BT-1)

Approved filesystem operations use the retained resolved target through an opened
handle. Replacing a symlink after approval cannot redirect the bound call. The
binding commits a pathname, not a prior file-content or historical file-ID
precondition. Windows currently requires local drive paths; POSIX requires
descriptor-relative no-follow primitives. Missing primitives fail closed. A target
conflict after intent remains unresolved; restarting or repeating the command
cannot establish that no earlier effect occurred. Cancellation waits for the
owning filesystem operation to finish before releasing its handles, including
repeated cancellation. A connector timeout also waits for that worker to finish;
the deadline is not a hard interrupt of filesystem I/O. Its timeout receipt does
not imply that the file was unchanged and cannot authorize another invocation.

The outward planner selects tool transport from the resolved prompt profile.
The admitted llama.cpp profile uses the JSON wrapper; native profiles retain
native schemas and tool choice. Explicit unsupported native requests still fail.
For bounded live approval/write proof, with an already running admitted server:

```powershell
$env:ORKET_DISABLE_SANDBOX = '1'
python scripts/proof/run_outward_write_file_approved_proof.py --provider llama_cpp --model orcarouter_qwen3.8-27b-uncensored-q4_k_l --json
```

The stable report is
`benchmarks/results/proof/outward_write_file_approved_proof_run.json`; inspect its
observed result and verifiers. This proof does not certify broad BT-1 migration,
multi-turn acceptance or an authenticated deployed API listener.

Populated legacy approval stores fail startup with
`E_OUTWARD_OFFLINE_APPROVAL_MIGRATION_REQUIRED`. Stop every old API/worker and
any already authorized command before migration; a schema gate cannot stop a
worker that already read its approval. Keep the original store and evidence.

Rehearse on new, nonexisting backup/destination paths:

```text
python -m scripts.governance.migrate_outward_approvals --source <old.sqlite3> --backup <backup.sqlite3> --destination <candidate.sqlite3> --writers-stopped
```

The command backs up through SQLite, upgrades a second copy, preserves decisions
and events, and records a rerunnable inventory in
`benchmarks/staging/outward_approval_migration.json` (`--out` overrides the report
path). It never switches the active database. Keep this inventory with the copy.
The new schema retires the old approval table name so old readers and writers
fail closed. New code preserves unbound legacy statuses for history, but denies
new approval/dispatch authority with `E_OUTWARD_AUTHORIZATION_REQUIRED`.

Do not reconstruct bindings or erase pending legacy history. Generation-0 run
reentry, direct start and denial continuation return
`E_OUTWARD_LEGACY_RUN_QUARANTINED`; status inspection remains available. Unbound
pending rows keep their original status even after the old deadline. Queue reads
and expiry sweeps leave them untouched; new decision attempts return
`E_OUTWARD_AUTHORIZATION_REQUIRED`. Retained unbound rows do not consume the
expiry sweep limit for bound proposals. Fresh independently submitted work still
requires its own approval; a new namespace does not establish target isolation.
Quarantine is the selected legacy disposition; old-run reconciliation and
replacement remain unsupported. This candidate is not a production upgrade acceptance. Rollback must keep dispatch
disabled and retain possible effects, claims, receipts and journals.

## Recover an outward claim before intent

Inspect `GET /v1/approvals/<proposal_id>/effect` with the normal API authentication.
For `state=claimed`, an operator may request replacement using the returned owner
and fencing generation:

```text
POST /v1/approvals/<proposal_id>/effect/recover
{"request_id":"operator-recovery-1","expected_owner_id":"<observed-owner>","expected_fencing_generation":1}
```

Use a distinct request ID for a new recovery operation and the identical body when
retrying that operation. The server derives operator identity from authentication;
a client cannot supply a different actor. Recovery can execute the original bound
effect. It persists the replacement owner and shared recovery/operator records
before intent, so a still-running previous owner fails its mandatory fence check.
If the replacement is interrupted while still claimed, the same recovery request
can resume that claim; ordinary approval retries do not replace it.

`dispatching` without a conclusive receipt remains uncertain and returns conflict.
Process death or time elapsed cannot authorize another command. `observed` receipts
can finish publication without another invocation. A changed actor/body for an old
request key, a superseded recovery, or missing/contradictory recovery evidence
returns conflict. The operation does not recover a legacy unbound run. An old
approval retry also does not start another model turn; use the run reentry path
below for durable ready or observed model admission.


## Resume retained outward model admission

Initial submission commits the run, admission event and ledger head together.
Concurrent applications admit one active run per namespace; a competing new run
receives HTTP 409. A retry with the same run ID returns the retained submission,
without replacing its task or policy. If initial publication fails or its process
dies before commit, retry may submit again. `E_OUTWARD_ADMISSION_EVENT_MISSING`
means an older run lacks its initial event: retain it for inspection and do not
backfill history to resume it. Contract: `docs/specs/OUTWARD_RUN_ADMISSION.md`.

Resubmit the same run ID through authenticated `POST /v1/runs` with its valid
original submission envelope. Run start and successful effect advancement commit
ready model admission with the turn projection. Reentry may claim ready work or
publish a previously retained model result without calling the provider again.
The next file or command still requires its own bound approval.

`E_OUTWARD_MODEL_ADMISSION_UNRESOLVED` means an owner claimed the model call but
no publishable result is retained. The process may still be running, or its
response may have been lost. Ordinary retry cannot replace it. Keep its evidence
and provider-cost uncertainty; use explicit recovery below when another model
computation is intended.
Missing legacy admission (`E_OUTWARD_MODEL_ADMISSION_MISSING`), changed input, or
missing/corrupt model artifacts also block reentry. Do not reconstruct admission
from mutable model output, rewrite artifacts, or clear claims to obtain a retry.

Extraction artifacts remain the original extraction observation. The admission,
approval row and ledger publication establish proposal acceptance; an immutable
`extracted_pending_proposal` artifact is not the current approval queue status.


Inspect `GET /v1/runs/<run_id>/model-admission`. To supersede the latest claimed
attempt, copy its scope, owner and fence into an authenticated recovery request:

```text
POST /v1/runs/<run_id>/model-admission/recover
{"request_id":"model-recovery-1","execution_generation":1,"turn":1,"step_index":0,"expected_owner_id":"<observed-owner>","expected_fencing_generation":1}
```

This admits a ready replacement and retains the previous claimed attempt. It does
not invoke a provider. Resubmit the original run envelope to claim ready work.
The new output still needs its own approval before any governed connector runs.
Two remote provider calls may finish or be billed; recovery does not cancel a
remote request or assert it never ran. Only the current attempt can publish.

Retry the identical recovery request after a lost response. It returns the same
attempt, even if that attempt has since become claimed or published, and never
increments its fence again. If the replacement also loses its response, another
replacement requires a new request ID with its current owner/fence. An old request
cannot supersede a newer recovery or start a later turn. Observed results must be
published, not discarded through owner replacement. Missing/contradictory recovery
records block inspection and continuation without repairing history.

New artifacts live under the run evidence directory's
`model_attempts/<scope-digest>/`, with no shared latest aliases. Follow the
persisted model/proposal references. Model-admission schema v2 migrates legacy
rows without modifying their artifact refs/digests and retires the old table
name against incompatible writers. Rehearse on a database copy with writers
stopped; preserve the original and all evidence. Rollback must disable admission,
not erase attempts or revive superseded owners.

Sealed outward proof fixtures preserve exact manifest-committed bytes under
`.gitattributes`; do not normalize their line endings or reseal a changed package.
For the frozen September source fixtures, the original CRLF ledger/bundle bytes
match the retained digests. Verify those commitments before restoring bytes;
an unexplained mismatch remains corruption, not permission to change its anchor.
