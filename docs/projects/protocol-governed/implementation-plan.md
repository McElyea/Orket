# Protocol-Governed Runtime Implementation Plan (v5.1)

Last updated: 2026-03-04  
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
