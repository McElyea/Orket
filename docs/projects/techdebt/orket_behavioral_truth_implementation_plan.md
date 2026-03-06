# Orket Behavioral Truth Implementation Plan

Last updated: 2026-03-06  
Status: Active (proposed)  
Owner: Orket Core

## Purpose

Convert `orket_behavioral_truth_review.md` findings into a minimal-scope hardening plan that reduces false confidence and aligns runtime behavior with claimed behavior.

## Source Input

1. `docs/projects/techdebt/orket_behavioral_truth_review.md`

## Scope

In scope:
1. Behavior/truth mismatches called out in Findings 1-17.
2. High-value test repairs that validate runtime contracts instead of scaffolding.
3. Explicit degradation signaling for fallback or partial-load paths.

Out of scope:
1. Broad architecture rewrites.
2. Packaging lane expansion beyond direct truth/behavior fixes.
3. Unrelated cleanup not tied to a finding in the source review.

## Success Criteria

1. No narrated action claims without matching state effect.
2. No silent downgrade on core startup/prompting/config paths without explicit degradation signal.
3. Prompt/help/telemetry surfaces match real executable behavior.
4. Highest-risk seams have contract or integration coverage proving runtime truth.
5. Structural tests are clearly separated from runtime-truth tests.

## Additional Locked Rules for This Plan

1. Mixed mutation/suggestion semantics are forbidden for a single action surface.
2. Any recurring side effect must not be hidden behind `first_run` naming or telemetry.
3. Prompt/help/executor parity must derive from one canonical action registry.
4. Startup/config dependencies must be classified as `required`, `degradable`, or `optional`.
5. Strict mode and compatibility mode must emit distinct stable telemetry/event codes.
6. Partial-load results must be explicitly marked as partial success and must not appear equivalent to complete success.
7. Tests that bypass the decisive seam under review must not be cited as runtime proof.
8. Integration-test labeling is forbidden where the decisive external or cross-layer seam is mocked.
9. Response text, telemetry, and state effect must agree on whether an operation mutated state, suggested an action, degraded, or failed.
10. Active prompting mode and degradation state must be exposed through at least one operator-visible runtime surface and one machine-assertable telemetry or event surface.
11. A reduced or empty hierarchy caused by load failure must not be indistinguishable from a genuinely complete empty hierarchy.
12. Minimal seam mocking permits harness isolation only; business-path decisions and behavior under review must execute through the real implementation.
13. Slice closeout must name the exact behavior claim now proven, the test layer proving it, and any remaining unproven seam.

## Priority and Phasing

Execution order:
1. Phase 0: behavioral truth blockers (P0).
2. Phase 1: protocol and integrity hardening (P1).
3. Phase 2: telemetry/version truth and cleanup of dead affordances (P2).
4. Phase 3: proof hardening and gate promotion (P2).

## Phase 0: Behavioral Truth Blockers (P0)

### WS-BT1: Narrated Actions vs Real State Effects

Findings:
1. Finding 3 (`assign_team` message-as-action).

Implementation:
1. Decide and enforce one truth contract:
   1. `assign_team` performs real state transition and persistence, or
   2. `assign_team` is suggestion-only with truthful response text and telemetry.
2. Align return text, logs, and downstream routing behavior with chosen contract.
3. Mixed mode is forbidden; the action must be classified as mutation or suggestion before response generation.

Required proof:
1. Unit: branch behavior for `assign_team` payload parsing.
2. Contract: returned response schema and meaning for suggestion vs mutation mode.
3. Integration: end-to-end driver request proving persisted or non-persisted behavior exactly as documented.

Exit criteria:
1. No response text claims a switch if no switch occurred.
2. Integration test proves observed runtime effect.

### WS-BT2: Startup Semantics Truth

Findings:
1. Finding 2 (`perform_first_run_setup` does every-startup reconciliation).
2. Finding 14 (CLI tests bypass startup behavior).

Implementation:
1. Split startup reconciliation from first-run setup semantics, or keep wrapper with explicit internal naming and tracing.
2. Keep fast monkeypatched tests where useful, but add at least one real startup path test with reconciliation enabled.
3. Ensure startup logs/telemetry distinguish:
   1. reconciliation path,
   2. first-run setup path,
   3. no-op path.

Required proof:
1. Contract: function semantics and naming reflect actual side effects.
2. Integration: CLI startup path executes real reconciliation behavior without monkeypatch bypass.

Exit criteria:
1. First-run naming no longer hides recurring mutation behavior.
2. At least one CLI startup integration test validates real startup semantics.
3. No recurring reconciliation side effect may remain inside a function or telemetry surface named `first_run` unless the recurring behavior is explicitly named in that surface.

### WS-BT3: Prompt/Executor Surface Parity

Findings:
1. Finding 4 (prompt advertises broader structural action surface than executor).

Implementation:
1. Restrict prompt action list to actions actually handled by executor, or expand executor deliberately with explicit scope.
2. Add an action-contract test that validates prompt-advertised actions are executable or intentionally rejected with stable error semantics.
3. Define one canonical action registry used by prompt construction, help text, executor dispatch, and parity tests.

Required proof:
1. Contract: prompt action vocabulary parity check.
2. Integration: representative prompt-selected action reaches expected executor branch.

Exit criteria:
1. No prompt-help affordance claims unsupported action capability.

### WS-BT4: CLI Recognizer Reachability

Findings:
1. Finding 5 (`reforge` bare command unreachable).

Implementation:
1. Add `reforge` to recognized bare verbs or document slash-only contract and remove misleading branch affordance.
2. Align CLI help examples with actual accepted forms.

Required proof:
1. Unit: recognizer accepts or rejects bare `reforge` by policy.
2. Integration: `/reforge ...` and bare `reforge ...` behavior matches documented contract.

Exit criteria:
1. No dead branch for intended command form.

### WS-BT5: Silent Degradation on Driver Config Paths

Findings:
1. Finding 6 (`_load_engine_configs` silent fallback).
2. Finding 13 (driver init swallows config load failures).

Implementation:
1. Replace silent `pass` paths with explicit degradation markers and telemetry.
2. Expose active prompting mode (`governed` vs `fallback`) as runtime-visible state.
3. Define strict mode behavior for paths that should fail closed.
4. Each startup/config dependency must be classified as `required`, `degradable`, or `optional`, and the classification must be asserted in tests.
5. Active prompting mode and degradation state must be exposed through at least one user-visible or operator-visible runtime surface and one machine-assertable telemetry or event surface.

Required proof:
1. Contract: missing config yields explicit mode/result markers.
2. Integration: startup with missing assets proves declared degraded or fail-closed behavior.

Exit criteria:
1. Operators can always tell whether governed prompting is active.
2. Missing critical assets cannot silently appear successful.

## Phase 1: Protocol and Integrity Hardening (P1)

### WS-BT6: Strict JSON Boundary

Findings:
1. Finding 10 (brace-slice recovery broader than declared protocol).
2. Finding 16 (strict input claims with soft freeform fallback model).

Implementation:
1. Introduce explicit parsing modes:
   1. strict JSON-only mode,
   2. compatibility mode.
2. Make active mode observable in logs/telemetry.
3. In strict mode, reject non-envelope output without brace-repair parsing.
4. Strict mode and compatibility mode must emit different stable telemetry/event codes.

Required proof:
1. Contract: strict mode rejects non-pure JSON responses.
2. Integration: mode-specific behavior verified against model output variants.

Exit criteria:
1. Protocol claims match parser behavior in each mode.

### WS-BT7: Board Integrity Error Contract

Findings:
1. Finding 8 (silent omission of malformed/missing assets).
2. Finding 9 (weak orphan identity semantics and comment mismatch).
3. Finding 17 (mixed integrity/reporting without truthful error contract).

Implementation:
1. Add explicit `load_failures` section in board hierarchy response.
2. Remove top-level silent `pass` branches in integrity-sensitive loads.
3. Replace weak identity matching with stable issue IDs where available.
4. Align comments with implemented identity semantics.
5. If any integrity-sensitive entity fails to load, the result must indicate partial success explicitly rather than appearing equivalent to a complete successful load.
6. An empty or reduced hierarchy result caused by load failure must not be indistinguishable from a genuinely complete empty hierarchy.

Required proof:
1. Contract: malformed assets appear in `load_failures`, not silent omission.
2. Contract: partial-load status/result marker is asserted when integrity-sensitive loads fail.
3. Integration: hierarchy output distinguishes missing, broken, and loaded entities.

Exit criteria:
1. Board inventory output is truth-preserving under partial corruption.

## Phase 2: Telemetry and Dead-Affordance Truth (P2)

### WS-BT8: Recommendation and Affordance Cleanup

Findings:
1. Finding 1 (`get_engine_recommendations` no-op high-tier logic).
2. Finding 7 (`auto_fix` parameter unused).

Implementation:
1. Implement real installed-tier evaluation or remove dead high-tier logic/comments.
2. Remove or implement `auto_fix` with truthful behavior and naming.
3. Unused behavior flags, dead conditional branches, and comments describing nonexistent logic are forbidden after this slice.

Required proof:
1. Unit: recommendation behavior matrix by installed models and hardware profile.
2. Contract: function docs/comments align with observed behavior.

Exit criteria:
1. No dead affordances in recommendation or board APIs.

### WS-BT9: Telemetry and Version Truth

Findings:
1. Finding 11 (`provider_backend` semantic mismatch).
2. Finding 12 local version fallback drift.

Implementation:
1. Normalize provider telemetry keys so field names map to one meaning only.
2. Derive local version from authoritative metadata instead of stale hardcoded fallback.

Required proof:
1. Contract: telemetry schema assertions for provider backend and provider name.
2. Contract: version source-of-truth assertions for installed and local-dev contexts.
3. Unit: version reporting path in installed and local-dev contexts.

Exit criteria:
1. Telemetry labels are semantically consistent.
2. Reported version reflects running checkout/metadata truth.

## Phase 3: Proof Hardening and Gate Promotion (P2)

### WS-BT10: Runtime-Truth Test Promotion

Findings:
1. Cross-cutting proof gaps listed in review summary.
2. Finding 15 runtime-context bridge stability risk.

Implementation:
1. Any test that bypasses the real seam under review by monkeypatching, direct branch invocation, or stubbed provider behavior must not be cited as runtime proof.
2. Structural/mock-heavy tests may remain for fast feedback, but must be explicitly labeled non-runtime proof.
3. Add integration tests for highest-risk seams:
   1. runtime-context provider seam,
   2. startup reconciliation path,
   3. prompt/executor parity,
   4. CLI recognizer truth.
4. Keep unit tests for edge behavior, but do not present them as end-to-end proof.
5. Minimal seam mocking means transport or test-harness isolation only; business-path decisions, parser behavior, startup branching, and provider capability branching must execute through the real implementation under review.

Required proof:
1. Integration tests pass on real orchestration paths with minimal seam mocking.
2. Contract tests enforce behavior claims for prompts, telemetry, and parser modes.

Exit criteria:
1. High-risk seams have runtime-truth coverage, not only structural coverage.

## Test Layer Policy for This Plan

Every new or modified test in this plan must declare layer in code comments or docstring:
1. unit,
2. contract,
3. integration,
4. end-to-end.

Promotion guidance:
1. Prefer contract/integration for behavior claims.
2. Use unit tests for edge-case isolation only.
3. A test may not be labeled integration if it mocks the decisive external or cross-layer seam whose runtime truth is under evaluation.
4. Any unavoidable proof gap must be called out in closeout notes.

## Delivery Slices

Suggested slice order:
1. Slice A: WS-BT1 + WS-BT2 + WS-BT4 + WS-BT5.
2. Slice B: WS-BT3.
3. Slice C: WS-BT6 + WS-BT7.
4. Slice D: WS-BT8 + WS-BT9.
5. Slice E: WS-BT10 gate/promotion consolidation.

Per-slice closure checklist:
1. behavior change implemented,
2. contract/integration proof added,
3. targeted tests executed,
4. proof gaps documented explicitly if any,
5. exact behavior claim now proven, proving test layer, and any unproven seam explicitly recorded.

## Risks and Controls

1. Risk: strict mode introduces operator friction.
   Control: provide explicit compatibility mode with clear marker.
2. Risk: startup behavior changes break existing fast tests.
   Control: keep fast lane but add one real-path startup integration test.
3. Risk: board integrity hardening reveals latent data defects.
   Control: surface defects via `load_failures` contract and phased remediation.

## Closeout Criteria

This cycle is ready for archive when:
1. P0 and P1 workstreams are complete and verified.
2. Runtime-truth proof exists for the high-risk seams listed in WS-BT10.
3. Remaining P2 items are either complete or explicitly deferred with risk notes.
4. `docs/projects/techdebt/README.md` closure semantics are satisfied.
5. Any deferred finding names the exact behavioral lie that remains, the user-visible risk, and the proof gap.
