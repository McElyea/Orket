# ODR Role-Fit Follow-Up Implementation Plan

Last updated: 2026-03-22
Status: Active
Owner: Orket Core

Background authority:

1. `docs/projects/archive/ODRModelRoleFit/MRF03212026/Closeout.md`
2. `docs/projects/archive/ContextContinuity/CC03212026/Closeout.md`

## Objective

Run the smallest truthful follow-up to the archived ODR model-role fit lane:

1. fix the triple execution blocker,
2. tighten the `v1_compiled_shared_state` substrate where it is confounding role-fit evidence,
3. rerun a narrow architect bakeoff anchored on `gemma3:27b` as reviewer,
4. emit bounded staging evidence without reopening the archived continuity question or broadening the full pair matrix.

## Scope Lock

1. Treat the archived model-role fit lane as settled bounded evidence, not as an active lane.
2. Treat the archived ContextContinuity lane as settled bounded evidence that stronger continuity alone did not rescue the prior primary pair.
3. Keep execution serial only.
4. Keep `gemma3:27b` fixed as the reviewer anchor for the follow-up architect bakeoff unless a documented runtime blocker prevents that role.
5. Do not broaden the architect matrix beyond:
   1. `Command-R:35B -> gemma3:27b`
   2. `llama-3.3-70b-instruct -> gemma3:27b`
   3. `mistralai/magistral-small-2509 -> gemma3:27b`
6. Fix the triple path before treating any triple artifact as evidence.
7. Tighten the V1 state and continuity-item identity substrate before claiming architect ranking is cleaner than the archived result.
8. Keep all rerunnable evidence in `benchmarks/staging/`.

## Proposed Execution Slices

### RFU-IMP-00: Triple Blocker Repair

Objective:

1. repair the config and harness mismatch that currently blocks all triple runs,
2. add regression proof for the exact blocker shape seen in staging,
3. rerun the triple path so blocked-on-bug evidence is replaced with truthful runtime evidence.

### RFU-IMP-01: V1 State and Identity Tightening

Objective:

1. tighten continuity-item identity and unresolved-state handling in the reused V1 substrate,
2. keep identity evidence explicit and non-fuzzy,
3. improve the inspectability path so role-fit evidence is less confounded by state-quality noise.

### RFU-IMP-02: Narrow Architect Bakeoff

Objective:

1. rerun only the three reviewer-anchored architect candidates,
2. preserve the archived scenario family, budgets, inspectability, compare, and verdict discipline unless an explicit blocker requires a change,
3. rank architect candidates only after the full narrow pass completes.

### RFU-IMP-03: Gated Triple Rerun and Closeout

Objective:

1. admit only triple variants justified by the narrow architect bakeoff results,
2. rerun triples only after the blocker repair and V1 tightening are complete,
3. close the lane with a bounded result that states whether architect selection is improved, still unresolved, or blocked by runtime limitations.

## Success Criteria

The lane is ready for execution only when:

1. the roadmap points to this plan,
2. the follow-up scope is explicitly narrower than the archived full matrix,
3. the triple blocker is isolated as a harness defect rather than model evidence.

The lane is complete only when:

1. the triple blocker is fixed and regression-tested,
2. the V1 state/identity tightening is implemented and proven at the relevant script level,
3. the three architect-reviewer pairs above have been rerun at the locked budgets,
4. any admitted triples have been rerun after the blocker repair,
5. compare, verdict, and closeout artifacts exist in staging for the follow-up lane,
6. the lane closes with an explicit bounded conclusion about reviewer fit, architect fit, and any remaining runtime blockers.

## Current Execution Status

1. `RFU-IMP-00` completed on `2026-03-22`.
   Triple runtime now accepts the archived reused V1 contract path shape and no longer fails on `KeyError: 'v1_state_contract_path'`.
2. `RFU-IMP-01` completed on `2026-03-22`.
   The reused V1 substrate now keeps explicit unresolved issue summaries and parses fenced `orket-constraints` payloads without promoting JSON fragments into accepted decisions.
3. `RFU-IMP-02` completed on `2026-03-22`.
   The narrowed serial architect bakeoff ran for:
   1. `Command-R:35B -> gemma3:27b`
   2. `llama-3.3-70b-instruct -> gemma3:27b`
   3. `mistralai/magistral-small-2509 -> gemma3:27b`
4. `RFU-IMP-03` remains pending.
   This follow-up lane intentionally leaves triples unconfigured until an explicit follow-on decision admits a triple phase under the narrowed evidence.
