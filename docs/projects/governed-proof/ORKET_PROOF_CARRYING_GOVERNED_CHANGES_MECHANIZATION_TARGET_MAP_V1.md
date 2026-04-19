# Orket Proof-Carrying Governed Changes Mechanization Target Map v1

Last updated: 2026-04-18
Status: Active lane working doc
Owner: Orket Core

Implementation lane: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`
Accepted requirements: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_REQUIREMENTS_V1.md`

## Purpose

Operationalize Workstream 1 of the governed-proof lane into a fixed set of proof-strengthening targets.

This document exists to make the active lane's mechanization scope explicit before any implementation work tries to close the lane by interpretation rather than by evidence.

## Boundary

This document is a lane-local planning surface.

It does not:
1. replace `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`,
2. replace `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`,
3. replace `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`, or
4. create new public trust wording.

Durable authority remains with the active specs and `CURRENT_AUTHORITY.md` until a same-change promotion updates those sources.

## Fixed Workstream 1 Targets

For the active governed-proof lane, the mechanization and independent-evidence target set is fixed to the six checks below.

| Target | Current source surface | Current truthful posture | Required lane output | Minimum closeout evidence | Status |
|---|---|---|---|---|---|
| `step_lineage_missing_or_drifted` and step-lineage independence | `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md` attempt/step linkage rules | Exposed as a fail-closed trusted-run check | mechanized or independently checkable step-to-effect lineage rule | one machine-checkable or independently replayable proof artifact showing the step/effect linkage rule plus a negative case for drift | complete |
| `lease_source_reservation_not_verified` | `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md` reservation and lease source rules | Exposed as a fail-closed trusted-run check | mechanized or independently checkable reservation-to-lease source rule | one proof artifact showing lease authority is traceable to reservation evidence plus a negative mismatch case | complete |
| `resource_lease_consistency_not_verified` | `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md` resource-versus-lease consistency rules | Exposed as a fail-closed trusted-run check | mechanized or independently checkable resource-versus-lease consistency rule | one proof artifact showing latest resource authority cannot contradict the lease used for the effect without detection | complete |
| `effect_prior_chain_not_verified` | `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md` effect-journal prior-chain rules | Exposed as a fail-closed trusted-run check | mechanized or independently checkable effect-chain linkage rule | one proof artifact showing non-initial effect entries preserve prior-entry linkage and drift is caught | complete |
| `final_truth_cardinality_not_verified` | `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md` final-truth linkage rules | Exposed as a fail-closed trusted-run check | mechanized or independently checkable terminal final-truth cardinality rule | one proof artifact showing the modeled run has exactly one terminal final-truth authority for success-shaped proof | complete |
| `verifier_side_effect_absence_not_mechanically_proven` | `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md` and `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` | Exposed as a forbidden-claim reason or blocker | mechanically constrained or independently checkable non-interference proof story | one proof artifact showing the offline verifier cannot mutate workflow state, durable control-plane state, or invoke providers/models while evaluating evidence | complete |

Canonical closeout artifact: `python scripts/proof/verify_trusted_run_proof_foundation.py`, which writes `benchmarks/results/proof/trusted_run_proof_foundation.json`.

## Verifier Non-Interference Acceptance Shape

Workstream 1 is not complete until the lane can point to a bounded, independently checkable answer for all of the following:

1. how the offline verifier is prevented from running workflow execution,
2. how it is prevented from mutating durable workflow or control-plane state,
3. how it is prevented from calling providers or models,
4. how it is prevented from performing external side effects outside its own declared report output, and
5. how a later evaluator can inspect or rerun that proof boundary without trusting prose alone.

## Initial Execution Order

The lane should implement or evidence the target set in this order unless same-change context justifies another order:

1. step lineage, effect prior-chain, and final-truth cardinality
2. reservation-to-lease source and resource-versus-lease consistency
3. offline-verifier non-interference

This order is preferred because it makes the trusted-run closure story harder to misread before the scope-family work begins.

## Closeout Rule

The governed-proof implementation plan may refer to "the six fixed priority checks" only if it means the exact target set listed in this document.
