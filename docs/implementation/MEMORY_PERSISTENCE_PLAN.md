# Memory Persistence Plan

Last updated: 2026-02-21
Owner: Orket Core
Status: Draft (active refinement)

## Scope
This document is the implementation plan for the deterministic memory/persistence layer in Orket.

Primary goals:
1. Make determinism claims mechanically testable.
2. Define and implement snapshot-safe memory visibility (`off`, `read_only`, `buffered_write`, `live_read_write`).
3. Add retrieval/tool/output tracing required for replay and equivalence checks.
4. Add commit/idempotency/recovery semantics for buffered writes.

Non-goals for first implementation:
1. Vendor-specific vector DB optimization.
2. Semantic or intent equivalence scoring inside the deterministic contract.
3. Automatic trust promotion workflows beyond explicit policy hooks.

## Working Name
Internal program name: Deterministic Memory Persistence Layer (DMPL).

## Ratified Contract Decisions (v1)
1. Event `index` is authoritative for equivalence; `event_id` is run-local linkage metadata.
2. Determinism is structural + behavioral only; intent is not part of determinism.
3. Deterministic runs must use `off`, `read_only`, or `buffered_write` (never `live_read_write`).
4. Canonical normalization is required and versioned (`normalization_version`, initial `json-v1`).
5. Tool profiles own argument/result/side-effect fingerprint field selection and are versioned.
6. Retrieval ranking is deterministic: score descending, then `record_id` ascending.
7. Retrieval query preprocessing is explicit and versioned (`query_normalization_version`, `query_fingerprint`, `retrieval_mode`).
8. `memory_snapshot_id` is unique and totally ordered over committed states.
9. Commits are atomic, serialized, and idempotent with payload verification.
10. Buffer state machine and abort reason codes are required (`buffer_open`, `commit_pending`, `commit_applied`, `commit_aborted`).
11. Core contracts are versioned and logged:
`normalization_version`, `determinism_trace_schema_version`, `retrieval_trace_schema_version`, `tool_profile_version`.

## Determinism Contract v1 (Implementation Target)
Deterministic run eligibility:
1. Same `workflow_id`.
2. Same `model_config_id`.
3. Same `policy_set_id`.
4. Same start `memory_snapshot_id`.
5. Non-live visibility mode only.

Required run trace envelope:
1. `run_id`
2. `workflow_id`
3. `memory_snapshot_id`
4. `visibility_mode`
5. `model_config_id`
6. `policy_set_id`
7. `determinism_trace_schema_version`

Per-event trace fields:
1. `event_id` (linkage only)
2. `index` (authoritative order)
3. `role`
4. `interceptor`
5. `decision_type`
6. `tool_calls` (with normalized args + tool profile metadata)
7. `guardrails_triggered`
8. `retrieval_event_ids`

Equivalence rules:
1. Same number of events and same per-index `role`, `interceptor`, `decision_type`.
2. Same tool call count per event; same `tool_name` and normalized args per call.
3. Same guardrail IDs per event.
4. Same retrieval behavior (record IDs and rank order under same retrieval policy version).
5. Same per-call `tool_result_fingerprint` and, where required, `side_effect_fingerprint`.
6. Same `output_type` and `output_shape_hash`.

`event_id` does not need to match across equivalent runs.

## Canonicalization and Fingerprints
Canonical JSON `json-v1` rules:
1. UTF-8 encoding.
2. JSON-only values (objects/arrays/scalars).
3. Object keys sorted lexicographically.
4. Floats rounded to fixed precision (6 decimals unless overridden by spec).
5. NaN/Infinity rejected or pre-normalized to strings.
6. Minified output (no whitespace formatting).

Normalized tool args:
1. Serialize with `json-v1`.
2. Log `normalized_args` and `normalization_version`.
3. Inclusion field set comes from the active tool profile version.

`output_shape_hash`:
1. Computed from structural output representation, not raw text.
2. Structural object serialized by `json-v1`.
3. Hash algorithm `sha256` for v1.
4. Log with `normalization_version`.
5. The determinism trace schema must include at least three canonical structural examples used for hashing:
`{ "type": "text", "sections": ["intro", "body", "conclusion"] }`
`{ "type": "plan", "steps": [ { "id": 1, "action": "analyze" }, { "id": 2, "action": "generate" } ] }`
`{ "type": "code_patch", "files": [ { "path": "foo.py", "changes": [...] } ] }`

## Model Configuration Identity
`model_config_id` must include:
1. `provider_name`
2. `model_name`
3. `model_revision` or deployment version when available
4. Decoding params (`temperature`, `top_p`, `max_tokens`, penalties if used)
5. Seed controls (`seed` or `stochastic_unseeded=true`)
6. Tool runtime profile hash (includes tool profile versions)

Deterministic runs require fixed seed or provider/runtime deterministic guarantees under fixed config.

## Retrieval Trace and Ranking
Each retrieval trace event must include:
1. `retrieval_event_id`
2. `run_id`, `event_id` linkage
3. `policy_id`, `policy_version`
4. `query_normalization_version`
5. `query_fingerprint`
6. `retrieval_mode` (`text_to_vector`, `vector_direct`, etc.)
7. `candidate_count`
8. `selected_records` with `record_id`, `record_type`, `score`, `rank`
9. Applied filters (namespace/tags/trust/scope/TTL)

Deterministic equivalence requires:
1. Same retrieval event count.
2. Same `policy_id` and `policy_version`.
3. Same `query_fingerprint`, `query_normalization_version`, and `retrieval_mode`.
4. Same selected record IDs in same rank order.

Ranking tie-break:
1. Primary sort `score` descending.
2. Secondary sort `record_id` ascending.

## Tool Profiles and Side Effects
Each tool must have a versioned tool profile defining:
1. Fields included in `normalized_args`.
2. Fields included in `tool_result_fingerprint`.
3. Fields included in `side_effect_fingerprint` (if side effects are in scope).

Per tool call, log:
1. `tool_profile_version`
2. `tool_result_fingerprint`
3. `side_effect_fingerprint` where applicable

Deterministic run side-effect policy:
1. Prefer mocked/no-side-effect tools.
2. If side effects exist, they must be captured by profile-defined `side_effect_fingerprint` and must match across equivalent runs.

## Snapshot, Commit, and Recovery Semantics
Snapshot semantics:
1. At run start, capture committed `memory_snapshot_id`.
2. All run reads use this snapshot only.
3. Snapshot IDs are unique and totally ordered over committed states.

Buffered write isolation:
1. Writes go to per-run buffer tagged by `run_id`.
2. Buffered writes are invisible to all readers, including same run reads.
3. Commit policy decides apply/discard at run end.

Commit identity and payload verification:
1. `commit_id = hash(run_id + memory_snapshot_id + policy_set_id)`.
2. `commit_payload_fingerprint` computed over canonical buffered write set.
3. Re-applying same `commit_id`:
matching payload fingerprint -> idempotent no-op
different payload fingerprint -> hard error (`payload_mismatch`)

Buffer state machine:
1. `buffer_open`
2. `commit_pending`
3. `commit_applied`
4. `commit_aborted`

`commit_aborted` requires `reason_code`:
1. `policy_rejected`
2. `validation_failed`
3. `storage_apply_failed`
4. `payload_mismatch`

Crash semantics:
1. Crash in `buffer_open` -> discard buffer.
2. Crash in `commit_pending` -> recover by atomically applying commit or marking `commit_aborted` with storage failure reason.
3. Partial commit application is forbidden.
4. A `commit_id` may be owned by exactly one recovery worker at a time; ownership must be lease-based with explicit timeout and renewal, and expired leases become eligible for reassignment.

## Open Decisions (Must close before code freeze)
1. Canonicalization edge behavior:
Unicode form, datetime normalization, and missing vs `null` policy.
2. Per-output-type structural schema definitions for `output_shape_hash`.
3. Backend constraints for deterministic ANN retrieval across vendors.
4. Ownership/lease timeout semantics for `commit_pending` recovery workers.
5. Trace retention and sampling limits for high-volume runs.

## Phase 0 Gate Clarifications
Before Phase 0 exit, the following must be explicitly resolved in specs:
1. Canonicalization edge behavior for:
Unicode normalization form, datetime normalization, and missing vs `null`.
2. `output_shape_hash` schema examples:
At least the canonical text/plan/code-patch structural examples in the determinism trace schema.
3. Retrieval backend deterministic-mode contract:
Either backend-native deterministic mode requirements or deterministic wrapper/re-ranking constraints.
4. Recovery worker ownership model:
Single-owner lease behavior with timeout and renewal semantics.
5. Trace retention baseline:
Minimum retention window for deterministic runs plus per-run hard trace-size cap/truncation rules.

## Architecture Delta (Target)
1. New memory contracts package:
`orket/core/contracts/memory/`
2. New runtime services:
`orket/application/services/memory/`
3. New deterministic trace artifacts:
`workspace/.../observability/.../memory_trace.json`
4. New policy documents:
`model/core/contracts/memory/*.json`
5. New implementation docs:
`docs/implementation/`

## Phase Plan

### Phase 0: Contract Freeze
Deliverables:
1. Determinism trace schema and versioning.
2. Retrieval trace schema and versioning.
3. Tool profile schema (`tool_profile_version`) and fingerprint field ownership.
4. Buffer/commit state machine schema with abort reason codes.
5. Canonical JSON normalization spec `json-v1`.

Exit criteria:
1. Schemas checked into repo.
2. Fixture examples for pass/fail equivalence cases.
3. Review sign-off from runtime + policy owners.
4. Phase 0 gate clarifications resolved and documented in schema artifacts.

### Phase 1: Instrumentation
Deliverables:
1. Emit run envelope, event trace, retrieval trace, and output descriptors.
2. Emit query fingerprints and normalization versions.
3. Emit tool profile versions and result/side-effect fingerprints.
4. Emit all contract version fields in run artifacts.

Exit criteria:
1. Trace emitted for all deterministic-mode runs.
2. No missing required fields in CI contract tests.

### Phase 2: Buffered Write Isolation
Deliverables:
1. Start-snapshot capture and read isolation enforcement.
2. Per-run write buffer and visibility guarantees.
3. Atomic commit apply/discard behavior.
4. Total-order snapshot progression on commit.

Exit criteria:
1. Concurrency tests prove no cross-run leakage.
2. Crash tests prove no partial commit states.

### Phase 3: Idempotent Commit + Recovery
Deliverables:
1. `commit_id` + `commit_payload_fingerprint` implementation.
2. Idempotent replay handling and payload mismatch errors.
3. Recovery workflow for `commit_pending`.
4. Durable commit ledger for replay diagnostics.

Exit criteria:
1. Replay of same commit is no-op only when payload matches.
2. Recovery tests pass for process death in all states.

### Phase 4: Determinism Equivalence Engine
Deliverables:
1. Comparator for deterministic-equivalent runs.
2. Strict per-index event diffing and retrieval rank diffing.
3. Fingerprint and output descriptor checks with clear fail reasons.
4. CLI/report integration to gate deterministic claims.

Exit criteria:
1. Positive fixtures pass.
2. Intentional divergences fail with deterministic diagnostics.

### Phase 5: Rollout and Guardrails
Deliverables:
1. Feature flags for visibility modes by environment.
2. Safe defaults (`off`/`read_only`) and explicit opt-in for `buffered_write`.
3. Runbook updates and operator diagnostics.

Exit criteria:
1. Production-safe default mode enforced.
2. Runbook covers triage for memory determinism failures.

## Backlog (Remaining Work)
1. Emit `memory.determinism_trace.v1` artifacts from runtime execution paths.
2. Emit `memory.retrieval_trace.v1` artifacts with deterministic linkage to event trace.
3. Add runtime integration tests for trace emission in deterministic modes.
4. Add equivalence comparator implementation and failure-diff diagnostics.
5. Add persistence-backed (non in-memory) isolation/idempotency/recovery integration tests.
6. Add retention and truncation enforcement tests for memory trace artifacts.
7. Integrate memory determinism check into release/report pipelines beyond quality workflow smoke.

## Risks and Controls
1. Risk: false determinism failures due to unstable normalization.
Control: pinned normalization spec + golden vectors.
2. Risk: retrieval nondeterminism from backend ANN behavior.
Control: deterministic retrieval settings + strict tie-break ordering.
3. Risk: commit deadlocks in recovery.
Control: lease ownership + timeout + explicit abort path.
4. Risk: excessive trace volume.
Control: bounded artifacts + per-lane retention policy.

## Definition of Done (v1)
1. Deterministic claim is rejected unless full trace contract is present.
2. Buffered write semantics pass isolation, crash, replay, and payload-mismatch tests.
3. Equivalence checker can prove deterministic-equivalent vs non-equivalent runs.
4. Policies and runbook are updated and linked from docs index.

## Refinement Notes
This is a living implementation plan. Update this file first when:
1. contracts change,
2. scope changes,
3. phase exit criteria change,
4. new blocking risks are discovered.
