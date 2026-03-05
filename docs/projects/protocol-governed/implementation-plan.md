# Protocol-Governed Runtime Implementation Plan (v5.1)

Last updated: 2026-03-05  
Status: Draft  
Owner: Orket Core

Reference: `docs/projects/protocol-governed/requirements.md`

## Objective

Implement the v5.1 protocol-governed runtime as a deterministic execution path where:

1. The model emits one strict proposal envelope.
2. Runtime validators are the only enforcement authority.
3. Execution, ledger events, receipts, and artifacts are replay-stable.
4. Multi-worker coordination remains idempotent and deterministic under races.

## Success Criteria

Functional:
1. Tool-mode rejects narrative content and malformed envelopes.
2. Unknown proposal keys are rejected at every proposal level.
3. Required tool cardinality and ordering are enforced.

Determinism:
1. Identical inputs produce identical validation outcomes and error codes.
2. Replay reconstructs identical run state from ledger + artifacts only.
3. `operation_id`, `proposal_hash`, `receipt_digest`, and `step_seed` remain stable across reruns.

Operational:
1. Runtime supports large runs without protocol drift (`100k+` steps target in soak tests).
2. Crash recovery never duplicates side effects.
3. Determinism harness fails on any hidden nondeterminism.

## Execution Status (2026-03-05)

Completed slices:
1. PR-01 strict envelope parser is wired (`E_PARSE_JSON` / duplicate-key / markdown fence / strict key set / cap checks).
2. PR-02 deterministic preflight foundation is wired (schema+governance+approval validation before tool execution starts, with strict fail-fast behavior).
3. Protocol context caps are wired into turn context (`protocol_governed_enabled`, `max_response_bytes`, `max_tool_calls`).

Recently completed slices:
1. PR-03 canonical hash framing:
   - Added shared protocol canonicalization utilities and tuple-framed hashing.
   - Parser now stamps strict-mode metadata (`proposal_hash`, `validator_version`, `protocol_hash`, `tool_schema_hash`) into turn raw payload.
   - Dispatcher and artifact writer now consume canonical hashing instead of ad hoc JSON hashing for protocol surfaces.
2. PR-06 deterministic tool execution and idempotency guards:
   - Added deterministic `step_id`, `step_seed`, and `operation_id` derivation in tool execution flow.
   - Added operation-id result cache path and replay/reuse semantics.
   - Added append-only protocol receipt emission per tool call with deterministic digest.
3. PR-02 workspace constraints hardening:
   - Added `Path.is_relative_to()`-based workspace constraint checks in preflight with deterministic `E_WORKSPACE_CONSTRAINT:<detail>` errors.
   - Added path traversal and absolute path checks for path-bearing tools (`read_file`, `write_file`, `list_directory`, `list_dir`).
4. PR-07 network destination allowlist metadata surfaces landed:
   - Added `protocol_network_allowlist` to runtime-policy options/get/update and settings surfaces.
   - Added deterministic `network_allowlist_values` + `network_allowlist_hash` propagation into turn context.
5. PR-07 deterministic clock-source metadata wiring landed:
   - Added `clock_mode` and `clock_artifact_ref` resolution in determinism controls.
   - Added execution capsule fields (`clock_artifact_ref`, `clock_artifact_hash`, `network_allowlist_hash`) and replay receipt inventory exposure.
6. PR-10 enforce-phase checklist publication landed:
   - Added operator checklist at `docs/projects/protocol-governed/enforce-phase-rollout-checklist.md`.

Evidence added:
1. `tests/application/test_protocol_hashing.py`
2. Expanded:
   - `tests/application/test_turn_response_parser.py`
   - `tests/application/test_turn_tool_dispatcher.py`
   - `tests/application/test_turn_path_resolver.py`
   - `tests/application/test_turn_artifact_writer.py`

Latest completed increments:
1. Append-only LPJ-C32 v1 ledger adapter landed:
   - deterministic framing (`uint32_be len | payload | uint32_be crc32c`)
   - 4 MiB payload cap enforcement
   - replay truncation tail tolerance
   - checksum corruption detection (`E_LEDGER_CORRUPT`)
   - monotonic sequence validation (`E_LEDGER_SEQ`)
2. Async protocol run-ledger repository landed:
   - async start/finalize/event append APIs
   - deterministic replay-backed `get_run` projection
   - session-isolated event storage
3. Replay reconstruction engine landed:
   - rebuild run summary from append-only events
   - operation map extraction from event stream
   - artifact digest inventory integration
4. Determinism replay comparator landed:
   - run-vs-run digest comparison
   - deterministic difference surface for status/ops/artifacts
5. CLI replay comparator script landed:
   - `scripts/MidTier/run_protocol_replay_compare.py`
   - strict mode exits non-zero on mismatch
6. Protocol sessions API surfaces landed:
   - `/v1/protocol/runs/{run_id}/replay`
   - `/v1/protocol/replay/compare`
7. Ledger parity comparator landed:
   - runtime parity module comparing SQLite row vs protocol row
   - backend comparison script `scripts/MidTier/compare_run_ledger_backends.py`
   - sessions endpoint `/v1/protocol/runs/{run_id}/ledger-parity`
8. CLI protocol command surface expanded:
   - `orket protocol replay <run_id>`
   - `orket protocol compare <run_a> --protocol-run-b <run_b>`
   - `orket protocol parity <run_id> [--protocol-sqlite-db <path>]`
9. Lease expiry semantics hardened in worker:
   - `E_LEASE_EXPIRED` failure path
   - lease epoch mismatch detection
   - renewal result gate before success commit
10. First-commit-wins operation guard landed:
    - runtime `operation_id` commit registry
    - duplicate commit rejection (`E_DUPLICATE_OPERATION`)
    - winner linkage (`winner_event_seq`, `winner_entry_digest`)
11. Determinism control-surface utility landed:
    - timezone/locale/network mode resolution
    - env allowlist snapshot + hash generation
    - runtime policy helper for deterministic control bundle
12. Run-ledger mode selection and dual-write telemetry landed:
    - runtime `run_ledger_mode` policy resolution (`sqlite` / `protocol` / `dual_write`)
    - factory wiring in orchestration engine + execution pipeline
    - dual-write adapter with parity telemetry (`run_ledger_dual_write_parity`)
13. Protocol receipt materialization landed:
    - deterministic projection from per-turn `protocol_receipts.log` into run-level `runs/<run_id>/receipts.log`
    - operation event cross-linking (`receipt_seq`, `event_seq_range`)
    - idempotent replay-safe rematerialization path
14. Determinism campaign and replay surfaces expanded:
    - runtime campaign comparator module (`protocol_determinism_campaign`)
    - script harness `scripts/MidTier/run_protocol_determinism_campaign.py`
    - CLI command `orket protocol campaign`
    - sessions API endpoint `/v1/protocol/replay/campaign`
    - replay comparator now includes `receipt_inventory` in state digest and diffs
15. Replay campaign output schema lock landed:
    - canonical campaign output contract published at
      `docs/projects/protocol-governed/replay-campaign-schema.md`
16. Fault-injection replay coverage expanded:
    - truncation tail boundaries across multiple byte cuts
    - checksum corruption vectors for first/middle/final records
    - explicit non-monotonic sequence vectors
17. Protocol error-code registry landed:
    - centralized constants/prefix registry in `orket/runtime/protocol_error_codes.py`
    - parser/ledger/replay-facing codes mapped to stable identifiers
    - registry reference published at `docs/projects/protocol-governed/error-code-registry.md`
18. Determinism control-surface settings wiring landed:
    - protocol timezone/locale/network/allowlist controls resolved into turn context
    - settings and runtime-policy surfaces expose protocol determinism knobs
    - control surface contract published at
      `docs/projects/protocol-governed/determinism-control-surface.md`
19. Protocol ledger parity campaign surfaces landed:
    - runtime campaign comparator (`protocol_ledger_parity_campaign`)
    - script harness `scripts/MidTier/run_protocol_ledger_parity_campaign.py`
    - CLI command `orket protocol parity-campaign`
    - sessions API endpoint `/v1/protocol/ledger-parity/campaign`
20. Compatibility telemetry deltas are captured for dual-write parity:
    - campaign-level field delta counts (`field_delta_counts`)
    - value-transition signatures (`delta_signature_counts`)
    - status drift signatures (`status_delta_counts`)
21. Rollout evidence publication harness landed:
    - `scripts/MidTier/publish_protocol_rollout_artifacts.py`
    - versioned + latest bundle artifacts for operator review
22. Error dashboard family aggregation landed:
    - `scripts/MidTier/summarize_protocol_error_codes.py`
    - registry-family aggregation via `error_family(...)`
23. Parser/validator registry adoption expanded:
    - strict parser boundaries now use registry-backed constants/families
    - protocol preflight validator emits registered code families for schema/cardinality/workspace errors
24. Network destination allowlist settings/runtime-policy metadata landed:
    - new setting key `protocol_network_allowlist` exposed via `/v1/system/runtime-policy` and `/v1/settings`
    - deterministic turn context now carries `network_allowlist_values` + `network_allowlist_hash`
25. Clock-source replay metadata wiring landed:
    - turn context now carries `clock_mode`, `clock_artifact_ref`, and `clock_artifact_hash`
    - execution capsule now includes clock/network allowlist hash surfaces
26. Replay receipt inventory now surfaces execution capsule subset:
    - `network_mode`, `network_allowlist_hash`, `clock_mode`, `clock_artifact_ref`, `clock_artifact_hash`, `timezone`, `locale`, `env_allowlist_hash`
27. Enforce-phase rollout checklist published:
    - `docs/projects/protocol-governed/enforce-phase-rollout-checklist.md`
28. Enforce-phase window evidence captured (local quality workspace):
    - `benchmarks/results/protocol_governed/enforce_phase/window_a/*`
    - `benchmarks/results/protocol_governed/enforce_phase/window_b/*`
    - checklist sign-off entries filled for both windows

Validation evidence (new test surfaces):
1. `tests/application/test_protocol_append_only_ledger.py`
2. `tests/application/test_async_protocol_run_ledger.py`
3. `tests/application/test_execution_pipeline_protocol_run_ledger.py`
4. `tests/application/test_runtime_policy_protocol_controls.py`
5. `tests/runtime/test_protocol_replay.py`
6. `tests/runtime/test_operation_commit_registry.py`
7. `tests/runtime/test_determinism_controls.py`
8. `tests/runtime/test_run_ledger_parity.py`
9. `tests/interfaces/test_sessions_router_protocol_replay.py`
10. `tests/interfaces/test_cli_protocol_replay.py`
11. `tests/scripts/test_run_protocol_replay_compare.py`
12. `tests/scripts/test_compare_run_ledger_backends.py`
13. `tests/application/test_async_dual_write_run_ledger.py`
14. `tests/application/test_execution_pipeline_run_ledger_mode.py`
15. `tests/runtime/test_protocol_receipt_materializer.py`
16. `tests/runtime/test_protocol_determinism_campaign.py`
17. `tests/runtime/test_run_ledger_factory.py`
18. `tests/scripts/test_run_protocol_determinism_campaign.py`
19. `tests/runtime/test_protocol_ledger_parity_campaign.py`
20. `tests/scripts/test_run_protocol_ledger_parity_campaign.py`
21. `tests/scripts/test_publish_protocol_rollout_artifacts.py`
22. `tests/scripts/test_summarize_protocol_error_codes.py`
23. Expanded: `tests/runtime/test_protocol_error_codes.py`
24. Expanded: `tests/runtime/test_protocol_error_code_adoption.py`
25. Expanded: `tests/runtime/test_determinism_controls.py`
26. Expanded: `tests/application/test_runtime_policy_protocol_controls.py`
27. Expanded: `tests/application/test_turn_tool_dispatcher.py`
28. Expanded: `tests/runtime/test_protocol_replay.py`
29. Expanded: `tests/interfaces/test_settings_protocol_determinism_controls.py`
30. Expanded: `tests/interfaces/test_api.py`
31. Expanded: `tests/application/test_orchestrator_epic.py`

Verification runs (latest batch):
1. `python -m pytest -q tests/interfaces/test_api.py tests/interfaces/test_settings_protocol_determinism_controls.py tests/runtime/test_protocol_error_codes.py tests/runtime/test_protocol_error_code_adoption.py`
2. `python -m pytest -q tests/application/test_orchestrator_epic.py -k "protocol_governed_defaults or protocol_governed_env_overrides or protocol_determinism_invalid_network_mode"`
3. `python -m pytest -q tests/application/test_state_backend_mode.py tests/application/test_runtime_policy_protocol_controls.py tests/runtime/test_protocol_error_codes.py`
4. `python -m pytest -q tests/interfaces/test_cli_protocol_replay.py tests/interfaces/test_sessions_router_protocol_replay.py tests/runtime/test_protocol_determinism_campaign.py tests/runtime/test_protocol_replay.py tests/scripts/test_run_protocol_determinism_campaign.py tests/scripts/test_run_protocol_replay_compare.py tests/application/test_protocol_append_only_ledger.py tests/runtime/test_run_ledger_factory.py`
5. `python scripts/MidTier/check_docs_project_hygiene.py`
6. `python -m pytest -q tests/runtime/test_protocol_ledger_parity_campaign.py tests/scripts/test_run_protocol_ledger_parity_campaign.py tests/scripts/test_publish_protocol_rollout_artifacts.py tests/scripts/test_summarize_protocol_error_codes.py tests/runtime/test_protocol_error_codes.py tests/runtime/test_protocol_error_code_adoption.py`
7. `python -m pytest -q tests/interfaces/test_cli_protocol_replay.py tests/interfaces/test_sessions_router_protocol_replay.py tests/platform/test_quality_workflow_gates.py`
8. `python scripts/MidTier/publish_protocol_rollout_artifacts.py --workspace-root .ci/protocol_quality_workspace --out-dir benchmarks/results/protocol_governed/rollout_artifacts --baseline-run-id run-a --strict` (CI smoke parity/replay publication path)
9. `python -m pytest -q tests/runtime/test_determinism_controls.py tests/application/test_runtime_policy_protocol_controls.py tests/runtime/test_protocol_replay.py tests/application/test_turn_tool_dispatcher.py -k "protocol_receipt_uses_turn_raw_metadata or idempotency or determinism_controls or receipt_digest_inventory or protocol_replay_engine"`
10. `python -m pytest -q tests/interfaces/test_settings_protocol_determinism_controls.py tests/interfaces/test_api.py -k "runtime_policy_options or runtime_policy_get_uses_precedence or runtime_policy_update_normalizes_and_saves or settings_get_returns_metadata_and_sources or settings_patch_round_trip_persists_normalized_values or settings_patch_rejects_invalid_protocol_network_mode"`
11. `python -m pytest -q tests/application/test_orchestrator_epic.py -k "protocol_governed_defaults or protocol_governed_env_overrides or protocol_determinism_invalid_network_mode"`
12. `python -m pytest -q tests/runtime/test_determinism_controls.py tests/application/test_runtime_policy_protocol_controls.py tests/runtime/test_protocol_replay.py tests/application/test_turn_tool_dispatcher.py tests/interfaces/test_settings_protocol_determinism_controls.py tests/interfaces/test_api.py tests/application/test_orchestrator_epic.py`
13. `python scripts/MidTier/check_docs_project_hygiene.py`
14. `python -m scripts.MidTier.run_protocol_determinism_campaign --runs-root .ci/protocol_quality_workspace/runs --run-id run-a --baseline-run-id run-a --strict --out benchmarks/results/protocol_governed/enforce_phase/window_a/protocol_replay_campaign.json`
15. `python -m scripts.MidTier.run_protocol_ledger_parity_campaign --sqlite-db .ci/protocol_quality_workspace/.orket/durable/db/orket_persistence.db --protocol-root .ci/protocol_quality_workspace --session-id run-a --strict --out benchmarks/results/protocol_governed/enforce_phase/window_a/protocol_ledger_parity_campaign.json`
16. `python -m scripts.MidTier.publish_protocol_rollout_artifacts --workspace-root .ci/protocol_quality_workspace --out-dir benchmarks/results/protocol_governed/enforce_phase/window_a/rollout_artifacts --run-id run-a --session-id run-a --baseline-run-id run-a --strict`
17. `python -m scripts.MidTier.summarize_protocol_error_codes --input benchmarks/results/protocol_governed/enforce_phase/window_a/protocol_replay_campaign.json --input benchmarks/results/protocol_governed/enforce_phase/window_a/protocol_ledger_parity_campaign.json --out benchmarks/results/protocol_governed/enforce_phase/window_a/protocol_error_code_summary.json --strict`
18. `python -m scripts.MidTier.run_protocol_determinism_campaign --runs-root .ci/protocol_quality_workspace/runs --run-id run-b --baseline-run-id run-b --strict --out benchmarks/results/protocol_governed/enforce_phase/window_b/protocol_replay_campaign.json`
19. `python -m scripts.MidTier.run_protocol_ledger_parity_campaign --sqlite-db .ci/protocol_quality_workspace/.orket/durable/db/orket_persistence.db --protocol-root .ci/protocol_quality_workspace --session-id run-b --strict --out benchmarks/results/protocol_governed/enforce_phase/window_b/protocol_ledger_parity_campaign.json`
20. `python -m scripts.MidTier.publish_protocol_rollout_artifacts --workspace-root .ci/protocol_quality_workspace --out-dir benchmarks/results/protocol_governed/enforce_phase/window_b/rollout_artifacts --run-id run-b --session-id run-b --baseline-run-id run-b --strict`
21. `python -m scripts.MidTier.summarize_protocol_error_codes --input benchmarks/results/protocol_governed/enforce_phase/window_b/protocol_replay_campaign.json --input benchmarks/results/protocol_governed/enforce_phase/window_b/protocol_ledger_parity_campaign.json --out benchmarks/results/protocol_governed/enforce_phase/window_b/protocol_error_code_summary.json --strict`

Next execution slices (active):
1. Execute equivalent campaign windows against production traffic and obtain operator approver sign-off using the same checklist artifacts.

## Delivery Strategy

1. Ship behind a runtime flag first (`compat` mode), then enforce as default after parity evidence.
2. Keep changes modular and async-safe; avoid blocking I/O on async-reachable paths.
3. Land as mergeable PR slices with explicit acceptance checks.
4. Introduce integration changes only with live end-to-end proof per `AGENTS.md`.

## Workstreams and PR Sequence

## PR-01: Canonical Proposal Boundary

Goal: Enforce the single-envelope protocol boundary before any downstream logic.

Primary deliverables:
1. Add a strict proposal parser with:
   - one JSON object only
   - one ASCII trim pass
   - duplicate-key rejection
   - no markdown fence acceptance
   - no type coercion
2. Add explicit parser/validator error codes for fail-fast behavior.
3. Wire parser into turn ingestion path.

Likely touchpoints:
1. `orket/application/workflows/turn_response_parser.py`
2. `orket/application/workflows/turn_executor.py`
3. New focused modules under `orket/application/workflows/` for parser boundary logic.
4. `tests/application/test_turn_response_parser.py`

Acceptance checks:
1. Narrative-only tool-mode response is rejected deterministically.
2. Duplicate keys return parse error (`E_PARSE_JSON` path).
3. Unknown envelope/tool/args keys are rejected.

## PR-02: Deterministic Validator Pipeline

Goal: Implement fail-fast validation order exactly as specified in v5.1 Section 10.

Primary deliverables:
1. Deterministic validation pipeline and ordering contract tests.
2. Strict deep validation for proposal envelope and tool call schema.
3. Workspace path constraints (`is_relative_to` checks, symlink escape prevention).

Likely touchpoints:
1. `orket/application/workflows/turn_contract_validator.py`
2. `orket/application/workflows/turn_tool_dispatcher.py`
3. `orket/application/workflows/turn_path_resolver.py`
4. `tests/application/test_turn_contract_validator.py`
5. `tests/application/test_turn_tool_dispatcher.py`

Acceptance checks:
1. Same proposal + versions + schema hash => same validation outcome.
2. First failure short-circuits all later checks.
3. Workspace constraint violations return deterministic `E_WORKSPACE_CONSTRAINT:<detail>`.

## PR-03: Canonical JSON and Hash Framing

Goal: Make all digest surfaces language-independent and collision-safe.

Primary deliverables:
1. Add RFC 8785 canonical JSON utility for digest inputs.
2. Add hash tuple framing helper: `{"v":1,"kind":"...","fields":[...]}`.
3. Migrate `operation_id`, `step_seed`, `proposal_hash`, and receipt digest code paths.

Likely touchpoints:
1. New utility module under `orket/core` or `orket/application` for canonicalization and hash framing.
2. `orket/application/workflows/turn_artifact_writer.py`
3. `orket/application/workflows/turn_executor_ops.py`
4. `tests/application/test_turn_artifact_writer.py`
5. `tests/kernel/v1/test_turn_result_digest_surface.py`

Acceptance checks:
1. Hash outputs are stable across repeated runs and process restarts.
2. Non-finite numeric payloads are rejected before canonicalization.
3. No multi-field hash uses string concatenation.

## PR-04: Ledger Framing and Append-Only Persistence

Goal: Introduce required LPJ-C32 v1 event framing and strict replay read semantics.

Primary deliverables:
1. Append-only ledger writer/reader:
   - `uint32_be len | payload | uint32_be crc32c`
   - 4 MiB max record payload
2. Replay handling:
   - partial tail => end-of-log
   - checksum mismatch => `E_LEDGER_CORRUPT`
   - sequence violations => `E_LEDGER_SEQ`
3. Monotonic `event_seq` allocator and uniqueness checks.

Likely touchpoints:
1. `orket/runtime/execution_pipeline.py`
2. `orket/adapters/storage/` (new append-only ledger adapter)
3. `tests/application/test_execution_pipeline_run_ledger.py`
4. New ledger corruption/recovery tests under `tests/application/`

Acceptance checks:
1. Crash-simulated truncation yields valid replay to last complete record.
2. Corrupt checksum fails replay deterministically.
3. Event ordering during replay uses `event_seq` only.

## PR-05: Immutable Receipts and Content-Addressed Artifacts

Goal: Make receipts and artifact references immutable and replay-authoritative.

Primary deliverables:
1. Append-only receipt log with `receipt_seq` and cross-links to ledger.
2. Content-addressed artifact write path (`sha256/.../<digest>`).
3. Existing-digest behavior verifies bytes and never overwrites.

Likely touchpoints:
1. `orket/extensions/workload_artifacts.py`
2. `orket/interfaces/replay_artifacts.py`
3. `orket/application/workflows/turn_artifact_writer.py`
4. `tests/interfaces/test_replay_artifact_recording.py`
5. New receipt cross-link tests under `tests/application/`

Acceptance checks:
1. `receipt_digest` excludes non-deterministic storage metadata.
2. Artifact digest computed from raw bytes only.
3. Receipt and ledger records are bi-directionally linkable.

## PR-06: Deterministic Tool Execution and Idempotency Guards

Goal: Guarantee validated-then-execute order and duplicate side effect protection.

Primary deliverables:
1. Validate all tool calls before execution starts.
2. Execute strictly in `tool_calls` order.
3. Enforce `operation_id` idempotency guard with cached-result reuse.
4. Record execution capsule fields required by v5.1.

Likely touchpoints:
1. `orket/application/workflows/turn_tool_dispatcher.py`
2. `orket/application/workflows/turn_executor_ops.py`
3. `orket/application/workflows/turn_executor.py`
4. `tests/application/test_turn_executor_replay.py`
5. `tests/application/test_turn_tool_dispatcher.py`

Acceptance checks:
1. Duplicate operation attempts reuse stored results.
2. Mixed valid/invalid tool lists fail before any tool executes.
3. Replay reuses recorded side effects exactly once.

## PR-07: Determinism Control Surface

Goal: Constrain all runtime nondeterminism sources called out in v5.1.

Primary deliverables:
1. Deterministic runtime config:
   - fixed timezone and locale defaults
   - explicit environment allowlist hashing
   - deterministic cwd policy
2. Sorted directory traversal in runtime-owned file iteration paths.
3. Network mode controls:
   - default `off`
   - allowlist when enabled
   - captured request/response artifacts for replay

Likely touchpoints:
1. `orket/runtime/execution_pipeline.py`
2. `orket/runtime/offline_mode.py`
3. `orket/application/services/runtime_policy.py`
4. `tests/application/test_quant_sweep_runtime_env.py`
5. New deterministic env/network tests under `tests/runtime/`

Acceptance checks:
1. Deterministic replay runs with outbound network disabled.
2. Locale/timezone drift does not change outputs.
3. Directory traversal order remains stable across reruns.

Live integration verification (required when changing external integrations):
1. Run the real external flow end-to-end (no dry-run only).
2. Record observed mode/path used (primary vs fallback).
3. Capture failing step/error if failure occurs and either fix or report blocker.

## PR-08: Multi-Worker Lease and Commit Semantics

Goal: Make concurrent worker behavior deterministic under lease expiry and commit races.

Primary deliverables:
1. Lease record contract: `lease_epoch`, `lease_holder`, expiry, grant sequence.
2. CAS-based renewal semantics and explicit expiry handling.
3. First-commit-wins behavior for duplicate `operation_id` races.

Likely touchpoints:
1. `orket/runtime/execution_pipeline.py`
2. `orket/application/services/gitea_state_worker.py`
3. `orket/application/services/gitea_state_worker_coordinator.py`
4. `tests/application/test_runtime_state_interventions.py`
5. New race-condition tests under `tests/runtime/`

Acceptance checks:
1. Expired lease holder cannot commit results.
2. CAS mismatch triggers deterministic `E_LEASE_EXPIRED`.
3. Duplicate commit attempts resolve to first committed `event_seq`.

## PR-09: Replay Engine and Determinism Harness

Goal: Validate production readiness with repeatable replay parity checks.

Primary deliverables:
1. Replay modes:
   - full replay
   - deterministic replay
   - audit replay
2. Determinism harness that repeats workloads and compares:
   - ledger bytes
   - receipt bytes
   - artifact digests
3. CI/automation gates for determinism regressions.

Likely touchpoints:
1. `orket/runtime/execution_pipeline.py`
2. `orket/interfaces/replay_artifacts.py`
3. `tests/kernel/v1/test_replay_stability.py`
4. `tests/kernel/v1/test_replay_vectors.py`
5. New harness scripts under `scripts/`

Acceptance checks:
1. Harness fails on any byte-level divergence in deterministic mode.
2. Replay from ledger + artifacts alone reconstructs run state.
3. Crash recovery parity is proven with fault-injection tests.

## PR-10: Rollout and Enforcement

Goal: Move from compat observation to strict enforcement by default.

Primary deliverables:
1. Feature flag migration:
   - `compat`: collect violations, no hard reject
   - `enforce`: reject invalid turns
2. Migration notes and operator runbook.
3. Production metrics and alarms for retry spikes and validation failures.

Likely touchpoints:
1. `orket/application/services/runtime_policy.py`
2. runtime configuration docs under `docs/`
3. `.gitea/workflows/` (if automation updates are needed)

Acceptance checks:
1. Compat telemetry baseline captured.
2. Enforce mode enabled with no unresolved P0 blockers.
3. Rollback path documented and tested.

## Testing Matrix

Unit:
1. Parser boundary, duplicate-key rejection, strict schema checks.
2. Canonical JSON/hash framing helpers.
3. Ledger frame encode/decode and corruption handling.

Integration:
1. End-to-end turn execution with strict validation and deterministic tool ordering.
2. Replay parity across multiple runs with fixed seeds.
3. Multi-worker lease/commit race scenarios.

Soak:
1. High-step deterministic workloads (`100k+` target).
2. Crash/restart campaigns with tail truncation and replay recovery.

## Risks and Mitigations

1. Risk: Retry volume increases under stricter validation.  
Mitigation: tighten prompts minimally, tune token caps, keep retry payload under 128 bytes.

2. Risk: Throughput drops from stronger validation and logging.  
Mitigation: profile validator hot paths, batch durable writes safely, cap record payload size.

3. Risk: Hidden nondeterminism from environment or network dependencies.  
Mitigation: enforce deterministic runtime config and block network in deterministic replay.

4. Risk: Migration complexity with existing run ledger/repository surfaces.  
Mitigation: dual-write during compat window and add parity comparators before cutover.

## Exit Criteria

1. All PR acceptance checks pass.
2. Determinism harness is green for repeated replay campaigns.
3. Enforce mode is default with documented rollback.
4. Runtime behavior conforms to `docs/projects/protocol-governed/requirements.md` v5.1.
