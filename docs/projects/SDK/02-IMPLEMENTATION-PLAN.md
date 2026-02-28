# Extension SDK v0 Implementation Plan

## Objective

Implement the SDK v0 public seam under `docs/projects/SDK` constraints, while preserving current extension behavior through a dual-path runtime bridge.

## Strategy

1. Add SDK contracts and helpers first.
2. Add runtime adapter path for SDK workloads.
3. Preserve legacy `RunPlan` extension execution during transition.
4. Ship external reference demo and conformance tests.
5. Keep Layer-0 lock authoritative; gameplay tuning can pause while SDK seam work proceeds.

## Current Status Sync (2026-02-28)

1. Gameplay-kernel foundational work is substantially complete in TextMystery and should be treated as input constraints, not open redesign.
2. Immediate priority is SDK seam hardening and migration docs, with minimal new gameplay churn.
3. Companion/disambiguation policy should be treated as deterministic runtime policy, not model-driven behavior.

## Phase 0: Lock and Extract (Near-Term Focus)

### Deliverables

1. Freeze Layer-0 seam decisions from `00-IMPLEMENTATION-PLAN-SDK-LAYER-0.md` into SDK-facing docs and interfaces.
2. Define extraction-ready boundaries from TextMystery:
   - manifest contract
   - capability registry/provider interface
   - workload context/result models
   - artifact/trace helpers
3. Confirm local SDK workspace lock:
   - `c:\Source\OrketSDK`
   - package: `orket-extension-sdk`
   - development consumption: editable installs.

### Exit Criteria

1. No unresolved naming/path decisions remain for SDK repo bootstrap.
2. All docs under `docs/projects/SDK` are mutually consistent.
3. Extraction backlog is ordered and can proceed without reopening architecture questions.

## Phase 1: SDK Package and Contracts

### Deliverables

1. `orket_extension_sdk.manifest`
   - `Manifest`
   - `load_manifest(path)`
   - `validate_manifest(manifest)`
2. `orket_extension_sdk.capabilities`
   - `CapabilityId`
   - `CapabilityProvider`
   - capability interfaces (`AudioInput`, `AudioOutput`, `Console`, `Clock`, `KVStore`)
   - `CapabilityRegistry`
3. `orket_extension_sdk.workload`
   - `WorkloadContext`
   - `Workload` protocol (`run(ctx, input) -> WorkloadResult`)
4. `orket_extension_sdk.result`
   - `WorkloadResult`, `ArtifactRef`, `Issue`
5. `orket_extension_sdk.testing`
   - `FakeCapabilities`, `DeterminismHarness`, `GoldenArtifact`

### Engineering Tasks

1. Define pydantic models for manifest/result contracts.
2. Add semantic manifest validation with stable issue codes.
3. Define interface protocols for capabilities and workload.
4. Implement deterministic artifact digest helper APIs in testing utilities.
5. Add unit tests for each module.

### Exit Criteria

1. SDK package imports cleanly and has minimal surface only.
2. Contract models and validation tests pass.

## Phase 2: Runtime Dual-Path Bridge

### Deliverables

1. Runtime detection of extension contract style (legacy vs SDK v0).
2. SDK run path:
   - manifest parse and validation
   - required capability preflight
   - `WorkloadContext` construction
   - workload invocation
   - `WorkloadResult` validation
3. Internal mapping from `WorkloadResult` into engine runtime internals.
4. Existing legacy `RunPlan` path unchanged and still supported.

### Engineering Tasks

1. Extend extension manager loader to branch on contract type.
2. Implement capability preflight fail-closed checks.
3. Wire `ctx.artifacts` writer and `ctx.trace.emit` collection.
4. Reuse deterministic artifact manifest hashing and provenance logic.
5. Add integration tests for mixed catalogs (legacy + v0).

### Exit Criteria

1. v0 SDK workload runs end-to-end in runtime.
2. legacy workload runs unchanged.
3. Missing capability and invalid result errors are deterministic.

## Phase 3: External Demo Extension Integration

### Deliverables

1. External repo: `orket-extension-mystery-game-demo`.
2. `extension.yaml` with declared capability requirements and workload entrypoint.
3. `mystery_game.py` implementing `run(ctx, input)`.
4. Artifact production:
   - `transcript.jsonl`
   - `session_summary.json`
   - `pattern_used.json`

### Engineering Tasks

1. Publish reference manifest and workload contract usage.
2. Add install and execution flow validation from separate repository source.
3. Add deterministic replay test using saved transcript.

### Exit Criteria

1. Third-party install and run works through extension manager path.
2. Required artifacts produced and validated.
3. Deterministic replay assertions pass.

## Phase 4: Documentation and Deprecation Gates

### Deliverables

1. Public docs updated to SDK v0 seam language.
2. Explicit statement: `TurnResult` is internal-only.
3. Migration note for legacy path with deprecation readiness criteria.

### Engineering Tasks

1. Update extension docs and examples to show `WorkloadResult` seam.
2. Add compatibility section with major-version stability promise for manifest/result.
3. Add conformance checklist for extension authors.

### Exit Criteria

1. Single clear public extension story in docs.
2. No public docs instruct direct engine/turn internals usage.

## Phase 5: Deterministic Runtime Policy Hardening

This phase is scoped as runtime-policy hardening for demo quality and should not block core SDK package contracts.

### Deliverables

1. Deterministic hint policy:
   - repeat suppression
   - target cooldown markers
   - actor-aware suggestion routing
2. Deterministic disambiguation policy:
   - control command handling
   - full-sentence/forced-surface fallback behavior
3. Conformance tests for hint-loop prevention and disambiguation control flow.

### Exit Criteria

1. Demo no longer exhibits repeated suggestion loops in deterministic scripted runs.
2. Disambiguation prompt supports `back/help/quit` without dead-end behavior.
3. Policy remains deterministic and replay-safe.

## Ownership Slices

1. Contracts and SDK package:
   - API definitions, validation logic, model tests
2. Runtime bridge:
   - loader branching, capability preflight, result mapping
3. Determinism and testing:
   - harness coverage, digest normalization tests, replay checks
4. Demo extension:
   - external repo setup and end-to-end validation
5. Documentation:
   - guides, migration notes, compatibility policy
6. Runtime policy quality:
   - deterministic hint and disambiguation behavior for demo UX

## Test Cases and Scenarios

1. Manifest parsing and validation:
   - YAML primary and JSON accepted
   - required field errors with stable issue codes
2. Capability preflight:
   - missing capability fails before workload run
3. Result validation:
   - invalid status and malformed artifact references are rejected
4. Artifact safety:
   - path traversal or out-of-namespace writes are blocked
5. Determinism:
   - same seed + same transcript => same output + artifact digests
6. Migration:
   - legacy extensions still pass runtime execution under bridge mode
7. Runtime policy:
   - nudge repeat suppression and target cooldown behavior
   - actor-aware hint routing
   - disambiguation command handling (`back/help/quit`)

## Risks and Mitigations

1. Risk: Dual-surface confusion during transition.
   - Mitigation: Route all docs and examples to SDK seam first; mark legacy as compatibility mode.
2. Risk: Determinism drift from environment-specific output.
   - Mitigation: normalize path/timestamp noise and enforce digest-based checks.
3. Risk: Capability leaks.
   - Mitigation: strict required capability preflight and namespaced provider resolution.
4. Risk: Demo perceived quality regresses despite correct architecture.
   - Mitigation: deterministic runtime-policy conformance tests and scripted transcript smoke gates.
