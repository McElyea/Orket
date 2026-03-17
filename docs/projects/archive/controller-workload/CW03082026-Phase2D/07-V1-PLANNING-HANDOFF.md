# Controller Workload v1 Planning Handoff

Last updated: 2026-03-17
Status: Closed (Archived historical planning record)
Owner: Orket Core
Phase authority:
`docs/projects/archive/controller-workload/CW03082026-Phase2D/05-IMPLEMENTATION-PLAN-Phase-2D.md`

Closeout outcome:
1. Phase 2D is complete and no controller-workload follow-on lane remains active in `docs/ROADMAP.md`.
2. This packet is retained as historical planning input only and is not current roadmap or runtime authority.
3. Any future controller-workload expansion must begin from a new explicitly scoped request.

## 1. Purpose At Publication

Define actionable planning input for post-Phase-2 controller v1 work:
1. bounded parallel child execution
2. broader child contract-style support

This document is retained as historical planning input only and does not change current v0 runtime behavior.

## 2. Current Baseline (v0)

1. Sequential child execution only.
2. `sdk_v0` child contract style only.
3. Fail-closed semantics with stable error code surfaces.
4. Deterministic observability and replay/parity checks implemented.

## 3. Proposed v1 Scope Candidates

### 3.1 Bounded Parallelism
1. opt-in bounded concurrency (`max_parallel_children`)
2. deterministic completion ordering contract for summaries/observability
3. explicit conflict policy for shared artifacts and child-side effects

### 3.2 Broader Child Support
1. evaluate safe support path for additional contract styles
2. preserve authoritative dispatch through `ExtensionManager.run_workload`
3. maintain stable failure/denial taxonomy with explicit mappings

## 4. Compatibility and Migration Guardrails

1. `controller_workload_v1` must remain backward compatible by default.
2. New behavior must be opt-in through explicit caps/flags.
3. Existing stable error surfaces must not be silently repurposed.
4. Deterministic parity comparisons must remain available for equivalent inputs.

## 5. Proposed Design-Decision Packet (Next Slice Inputs)

1. concurrency model and deterministic ordering contract
2. child-type expansion matrix and denial mappings
3. replay/parity contract delta impacts
4. observability schema deltas and migration notes
5. rollback strategy for bounded parallel rollout

## 6. Recommended Starting Shape (Proposed)

1. Concurrency scope:
   - introduce `max_parallel_children` cap with default `1` (v0 behavior preserved)
   - first v1 target cap range: `1-4`
2. Ordering contract:
   - execution may occur concurrently, but emitted `child_results` and observability must remain sorted by declared child index
3. Failure policy:
   - preserve stop-on-first-failure semantics at scheduling boundary
   - children already running at first failure may complete; unscheduled children become `not_attempted`
4. Rollout strategy:
   - gate bounded parallelism behind explicit env + payload opt-in
   - require parity and determinism checks at each rollout stage

## 7. Rollback Boundaries

1. Hard rollback trigger:
   - parity regression or non-deterministic ordering in equivalent input runs
2. Fast rollback path:
   - force `max_parallel_children = 1` globally
3. Compatibility rollback:
   - preserve v0 summary/observability schema compatibility for existing consumers

## 8. Open Questions

1. What is the canonical deterministic ordering surface under parallel execution?
2. Should failed child cancellation semantics be immediate or boundary-scoped?
3. Which additional child contract styles are accepted for first v1 slice?
4. What compatibility window is required for v0-only extension ecosystems?
