# ODR Context Continuity Implementation Plan

Last updated: 2026-03-21
Status: Active
Owner: Orket Core

Requirements authority: `docs/projects/ContextContinuity/odr_context_continuity_requirements.md`

## Objective

Implement the bounded ODR continuity comparison lane defined by the requirements authority so Orket can truthfully determine whether stronger within-run continuity materially improves coordinated refinement versus the frozen control replay path.

The implementation lane must ship:

1. the frozen control continuity mode,
2. the bounded V0 log-derived replay mode,
3. the stronger V1 compiled shared-state mode,
4. the inspectability and aggregation surfaces required to compare them fairly,
5. the budget-scoped decision outputs required by Section 15 of the requirements authority.

## Scope Lock

This plan is implementation authority for the lane. The requirements authority remains the acceptance authority.

The lane is bounded by the following rules:

1. control behavior may not drift during the lane,
2. pair selection must remain pre-registered under Section 13 of the requirements authority,
3. the lane may run as `single-pair bounded` if exactly one pair qualifies,
4. V0 may not grow beyond the explicit exclusions locked in the requirements authority,
5. V1 may not bypass the locked state machine, inspectability, or regression accounting rules,
6. live comparison proof must remain budget-scoped at 5 rounds and 9 rounds,
7. secondary sensitivity checks may not be merged into the primary denominator after execution begins.

V1 is not gated on V0 proving materially worthwhile. Once the control freeze, pair pre-registration, and inspectability substrate are in place, the lane proceeds to V1 because the acceptance question explicitly compares frozen replay, bounded replay, and compiled shared state under one authority rather than treating V0 as a rollout gate for V1.

No `docs/specs/` extraction is introduced in this change because the current authority is lane-scoped experiment and implementation governance rather than a durable cross-repo runtime contract. If this lane stabilizes durable runtime contracts during implementation, extract them before declaring the lane complete.

## Success Criteria

The lane is complete only when all of the following are true:

1. the control, V0, and V1 modes are all runnable through the same comparison harness,
2. per-round inspectability artifacts required by the requirements authority are emitted and reviewable,
3. pair-equal, budget-scoped aggregates are computed from scenario-run units only,
4. the lane produces truthful Section 15 verdicts for V0 and V1 at 5 rounds and 9 rounds,
5. a first-class machine-readable verdict artifact exists for each locked budget and continuity mode,
6. the final report states whether the evidence is full-matrix, primary-plus-sensitivity, or `single-pair bounded`,
7. live proof has been run on the qualified pre-registered pair set without silent fallback behavior.

## Execution Model

Delivery uses five bounded slices. Each slice must ship its own code, proof, and closeout notes before the next slice claims success.

### CC-IMP-00: Control Freeze and Lane Bootstrap

Scope:

1. Freeze the current replay path as the control continuity mode.
2. Create the lane pre-registration record for included pairs, excluded pairs, and cited prior artifacts.
3. Lock the scenario-run aggregation helpers and budget-scoped reducers used by the comparison harness.
4. Define the canonical lane output schema for control, V0, and V1 comparison runs.
5. Commit one machine-readable lane configuration that locks:
   1. continuity mode enum,
   2. locked budgets,
   3. selected primary pair or pairs,
   4. secondary sensitivity pairs, if any,
   5. scenario set,
   6. threshold table reference,
   7. artifact root and canonical output paths.

Deliverables:

1. a frozen control continuity configuration or contract surface,
2. a committed pre-registration record in `docs/projects/ContextContinuity/`,
3. reusable reducers for scenario-run to pair-budget aggregation,
4. a canonical rerunnable JSON output path using the repo diff-ledger convention,
5. a committed machine-readable lane configuration artifact consumed by the comparison harness.

Required proof:

1. `unit` tests for reducer math and threshold evaluation,
2. `contract` tests proving the frozen control selection path does not drift when alternate continuity modes are enabled,
3. `contract` tests proving the harness reads locked budgets, pairs, scenarios, and output paths from the machine-readable lane configuration rather than hand-assembled defaults.

Exit criteria:

1. control runs can be reproduced without reading V0 or V1 state,
2. pair selection inputs are locked before V0 or V1 comparisons begin.

### CC-IMP-01: Inspectability and Artifact Surfaces

Scope:

1. Emit per-round loaded-context artifacts for every continuity mode.
2. Emit source-input inventories, hashes, and role-view derivation traces required by the requirements authority.
3. Emit V0 replay artifacts and V1 compiled shared-state snapshots without introducing duplicate authorities.
4. Emit predecessor linkage so every round records:
   1. prior-round artifact hash reference,
   2. prior-round state hash reference where state exists,
   3. explicit `derived_from` linkage from source inputs to loaded context.
5. Ensure all lane JSON outputs write through the rerun diff-ledger helpers.

Deliverables:

1. per-round inspectability artifacts for control, V0, and V1,
2. role-view derivation artifacts for architect and auditor,
3. stable hashes for loaded context, source inputs, and state snapshots,
4. predecessor-linkage fields connecting each round to prior-round artifacts and state,
5. documented artifact locations in the lane output schema.

Required proof:

1. `contract` tests for artifact shape and hash presence,
2. `contract` tests for predecessor-linkage and `derived_from` integrity,
3. `integration` tests proving each continuity mode emits the required artifacts on a real harness run.

Exit criteria:

1. a reviewer can inspect one round and determine exactly what context each role received and why,
2. artifact emission remains compatible with reruns and diff-ledger history.

### CC-IMP-02: V0 Bounded Replay Mode

Scope:

1. Implement V0 as bounded log-derived continuity replay only.
2. Enforce the explicit V0 exclusions from the requirements authority.
3. Preserve causal continuity without introducing compiled shared state.
4. Lock a deterministic replay-builder contract surface covering:
   1. source ordering,
   2. inclusion precedence,
   3. truncation policy,
   4. duplicate suppression,
   5. formatting template,
   6. causal-summary construction rule.
5. Make V0 selectable in the common comparison harness beside control.

Deliverables:

1. V0 replay builder and loader path,
2. V0-specific inspectability artifacts,
3. a deterministic V0 replay-builder contract surface used by the builder and tests,
4. regression accounting for reopened, contradiction, and carry-forward metrics under V0.

Required proof:

1. `integration` tests covering V0 replay assembly and exclusion enforcement,
2. `contract` tests covering ordering, truncation, duplicate suppression, and causal-summary determinism,
3. live proof at 5 rounds and 9 rounds on the primary qualified pair showing control and V0 outputs side by side.

Exit criteria:

1. V0 is clearly stronger than control in available continuity inputs,
2. V0 still remains inside the bounded replay design and does not silently become proto-V1.

### CC-IMP-03: V1 Compiled Shared State

Scope:

1. Implement the locked item state machine for unresolved, accepted, rejected, superseded, reopened, contradiction, and regression events.
2. Build the compiled shared-state representation and role-view derivation path.
3. Carry forward accepted and unresolved state according to the requirements authority.
4. Implement deterministic continuity-item identity and linkage rules so the same tracked issue or decision can be recognized across rounds.
5. Preserve inspectability so every compiled state decision is reconstructable from prior evidence.

Deliverables:

1. a compiled shared-state store or artifact,
2. deterministic role-view derivation for architect and auditor,
3. deterministic continuity-item identity and linkage rules across rounds,
4. event accounting surfaces for reopened decisions, contradictions, regressions, and carry-forward integrity.

Required proof:

1. `unit` tests for state transitions and event classification,
2. `contract` tests for role-view derivation, item identity stability, and state snapshot integrity,
3. `integration` tests proving V1 artifacts and metric counters align on real harness runs.

Exit criteria:

1. V1 can be audited round by round from source inputs to role-specific loaded context,
2. V1 metrics are computed from the same scenario-run facts used by control and V0.

### CC-IMP-04: Comparison Harness and Decision Reporting

Scope:

1. Run control, V0, and V1 under the locked 5-round and 9-round budgets.
2. Compute budget-scoped pair-equal aggregates from scenario-run units only.
3. Apply the locked Section 15 decision rule without discretionary overrides.
4. Emit a first-class machine-readable verdict artifact for each locked budget and continuity mode.
5. Produce final reports that distinguish full-matrix, primary-plus-sensitivity, and `single-pair bounded` evidence.

Deliverables:

1. comparison execution entrypoint,
2. budget-scoped result payloads with absolute and percentage deltas,
3. a machine-readable verdict artifact containing:
   1. budget,
   2. pair scope,
   3. evidence scope,
   4. worthwhile verdict enum,
   5. threshold inputs,
   6. absolute converged-case deltas,
   7. percentage deltas,
   8. disqualifying regressions, if any,
4. final decision report surfaces for V0 and V1,
5. explicit non-worthwhile or continuity-quality-only reporting paths when the thresholds are not met.

Required proof:

1. `integration` tests for aggregation and verdict labeling,
2. `contract` tests for verdict artifact shape and threshold-input fidelity,
3. live proof at both locked budgets on the qualified pair set with truthful artifact output and no hidden fallback path.

Exit criteria:

1. the lane can state whether V0 is worthwhile, whether V1 is worthwhile, or whether neither is materially justified,
2. the report can be reproduced from committed code, locked pair selection, and recorded artifacts only.

## Recommended Order of Work

1. Ship `CC-IMP-00` first so the control and pair registry cannot drift.
2. Ship `CC-IMP-01` before any V0 or V1 verdict claims so inspectability is available from the first comparison run.
3. Ship `CC-IMP-02` before `CC-IMP-03` so V0 evidence exists before the stronger abstraction is introduced.
4. Ship `CC-IMP-03` only after V0 exclusions and artifact boundaries are proven.
5. Ship `CC-IMP-04` last so the final lane verdicts are computed from stable implementations rather than moving targets.

## Verification Expectations

Structural proof expectations:

1. reducer, threshold, and state-machine tests must be labeled `unit` or `contract`,
2. continuity-mode harness tests must be labeled `integration`,
3. mock-only proof is insufficient for any claimed comparison or verdict behavior.

Live proof expectations:

1. all non-sandbox acceptance runs must set `ORKET_DISABLE_SANDBOX=1`,
2. live comparison proof must be recorded at both 5 rounds and 9 rounds,
3. the observed path and observed result must be recorded for each live run,
4. if no pair qualifies under the locked thresholds, the lane must stop and report that no current pair is continuity-testable rather than widening the gate.

## Closeout Conditions

Do not close this lane until:

1. the implementation slices above are complete or explicitly retired,
2. the live comparison outputs exist for the qualified pair set and locked budgets,
3. the final report applies the Section 15 decision rule exactly as written,
4. the final artifacts preserve the original primary denominator and do not silently promote secondary sensitivity checks into primary evidence,
5. any durable cross-lane contracts discovered during implementation have been extracted or explicitly deferred with rationale,
6. roadmap and project-index entries have been cleaned up in the same closeout change.
