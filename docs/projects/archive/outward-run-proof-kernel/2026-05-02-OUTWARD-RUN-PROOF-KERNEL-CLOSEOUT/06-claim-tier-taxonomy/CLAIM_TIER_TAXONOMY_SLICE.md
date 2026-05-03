# Slice 06 - Claim Tier Taxonomy

Last updated: 2026-05-01
Status: Archived slice plan - claim ladder promoted
Owner: Orket Core

Parent closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`

## Purpose

Define a stable outward-specific claim ladder that the invariant checker and assurance case index can reference without weakening `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

The ladder was extracted to `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md`. These names remain proof postures, not public determinism claims.

## Proposed Outward Claim Ladder

### `outward_lab_only`

Meaning: one verifier report accepted the witness package for the admitted compare scope.

Minimum evidence:
1. one accepted `outward_run_witness_package.v1`
2. all applicable `ORP-INV-*` invariants passed
3. no missing-evidence blockers

Does not claim repeatability, replay determinism, text determinism, or public trust.

### `outward_verifier_stable`

Meaning: two or more verifier reports for the same admitted compare scope have matching invariant signatures. The verifier is stable over equivalent evidence, while the outward pipeline may still be nondeterministic.

Minimum evidence:
1. two or more accepted bundles
2. matching invariant signatures
3. campaign report `outward_run_campaign_report.v1`

Does not claim model text identity or connector result identity.

### `outward_externally_checkable`

Meaning: an external evaluator with the witness package, offline verifier, and compare scope can reproduce accept/reject without live Orket context.

Minimum evidence:
1. `outward_verifier_stable` achieved
2. offline verifier accepts on a clean machine or clean environment
3. corruption suite passes in that same clean environment
4. assurance case index links the verification artifact

Does not claim the public trust boundary has widened.

### `outward_public_trust`

Meaning: `outward_externally_checkable` has been achieved and `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` admits the scope in the same change.

Minimum evidence:
1. `outward_externally_checkable` achieved
2. same-change trust-reason contract update names the compare scope
3. no public wording contradicts the evidence ceiling

## Deferred Deterministic Posture

`outward_deterministic` is intentionally not part of the initial four-tier ladder. Slice 08 may propose it only after ODR evidence, campaign evidence, and the determinism gate policy can support the exact bounded claim.

## Tier Ceiling Rules

| Condition | Maximum posture |
|---|---|
| single accepted verifier report | `outward_lab_only` |
| two or more accepted reports without campaign report | `outward_lab_only` |
| valid campaign report with stable invariant signatures | `outward_verifier_stable` |
| clean-environment offline verification plus corruption suite | `outward_externally_checkable` |
| same-change trust-reason contract update | `outward_public_trust` |

Requesting a higher posture must produce `claim_tier_not_supported`.

## Relationship to Existing Determinism Tiers

This ladder does not replace `non_deterministic_lab_only`, `verdict_deterministic`, `replay_deterministic`, or `text_deterministic` from `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

Any future public wording that uses determinism language must still use the determinism gate policy and name `claim_tier`, `compare_scope`, and `operator_surface`.

## Required Outputs

1. this tier ladder as lane-local planning material
2. extraction to `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md` before scripts depend on it
3. checker ceiling enforcement
4. assurance case rows referencing accepted tier names

## Exit Criteria

1. four outward postures are named with minimum evidence
2. checker enforces ceilings without manual override
3. the ladder is extracted before public wording references it
4. `TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` remains unchanged unless same-change evidence supports it
