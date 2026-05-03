# Outward Run Proof Kernel Requirements v1

Last updated: 2026-05-01
Status: Archived accepted requirements - approved single-turn boundary closed
Owner: Orket Core

Implementation plan: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`
Future extensions: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

Primary dependencies:
1. `CURRENT_AUTHORITY.md`
2. `docs/ARCHITECTURE.md`
3. `docs/specs/ORKET_OPERATING_PRINCIPLES.md`
4. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
5. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
6. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`
7. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
8. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
9. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
10. `docs/specs/LEDGER_EXPORT_V1.md`

## Purpose

Define the next active proof lane after the outward-facing run pipeline checkpoint.

This lane turns the outward-facing run loop into a proof-bearing runtime slice. It must make consequential outward runs independently checkable from serialized evidence without consulting live databases, clocks, providers, mutable runtime state, or narrative-only documentation.

## Direction

The accepted direction is:

```text
Every consequential outward AI effect should have a finite, portable evidence object
that independently proves what was proposed, admitted, approved, executed, and
truthfully claimed; unsupported claims must fail closed.
```

This direction extends the existing trusted-run, invariant, substrate, offline-verifier, and determinism vocabulary. It must not create a parallel proof vocabulary.

## Non-Goals

This lane does not:
1. create a prose constitution,
2. claim Orket is mathematically proven in general,
3. broaden public trust wording before evidence supports it,
4. reopen Bedrock-gated Terraform or NorthStar lanes,
5. treat ControlPlane expansion as valuable unless it answers a verifier question,
6. treat Data Plane expansion as valuable unless it emits proof-bearing effect evidence, or
7. replace existing trusted-run witness, invariant, substrate, offline-verifier, or trust-reason contracts.

## Required Slices

ORPK-SHAPE-001: The original lane kept eight slice folders while active. Slices 01 through 06 are archived with the completed boundary, and Slices 07 through 08 are future-hold extensions:
1. `01-assurance-case-index/`
2. `02-outward-run-witness-bundle/`
3. `03-invariant-checker/`
4. `04-negative-corruption-suite/`
5. `05-non-fixture-useful-slice/`
6. `06-claim-tier-taxonomy/`
7. `07-multi-turn-sequence-proof/`
8. `08-odr-determinism-integration/`

ORPK-SHAPE-002: Slice folders are lane-local planning surfaces. Durable contracts accepted from those slices MUST be extracted to `docs/specs/` before implementation claims depend on them.

ORPK-SHAPE-003: The roadmap MUST point at the implementation plan, not at slice plans or requirements.

## Assurance Case Index Requirements

ORPK-ACI-001: The lane MUST create one canonical map from claim to:
1. invariant ids,
2. authority evidence artifacts,
3. verifier command or commands,
4. allowed claim tier,
5. compare scope,
6. operator surface, and
7. current blocker or limitation status.

ORPK-ACI-002: The assurance case index MUST distinguish authority-bearing evidence from projections, summaries, guides, and support-only material.

ORPK-ACI-003: The assurance case index MUST not become a prose constitution or a second source for public trust wording.

## Outward Run Witness Bundle Requirements

ORPK-WIT-001: The lane MUST define an outward-run witness package that reuses the existing trusted-run evidence vocabulary where applicable.

ORPK-WIT-002: Package verification MUST consume files inside the witness package only and MUST NOT consult live databases, clocks, providers, network services, process environment, mutable runtime state, or mutable workspace paths outside the package.

ORPK-WIT-003: The witness package MUST represent outward pipeline facts needed to prove proposal, admission, approval, effect, final truth, ledger integrity, and claim-tier eligibility.

ORPK-WIT-004: The witness package MUST preserve source authority refs or digests when it carries projections.

ORPK-WIT-005: Any digest used as authority MUST be recomputed from canonical bytes included in the witness package or anchored by a verified full `ledger_export.v1` payload field.

ORPK-WIT-006: Claims that require event absence or full-ledger completeness MUST use a full canonical `ledger_export.v1` with `export_scope=all`; partial views cannot prove absence.

ORPK-WIT-007: Bundle-only verifier modes MAY support schema or introspection checks, but MUST NOT return accepted proof claims. Accepted proof claims require an `outward_run_witness_package.v1` input.

## Invariant Checker Requirements

ORPK-INV-001: The invariant checker MUST mechanize outward-run invariants before any broader proof claim is made.

ORPK-INV-002: Initial invariants MUST include:
1. no effect before admission,
2. no approval-required effect before approval,
3. success requires final truth,
4. effect claims require effect evidence,
5. projections cannot replace authority,
6. full or partial ledger hash verification must match the export scope, and
7. claim tiers require their declared evidence.

ORPK-INV-003: Missing evidence MUST produce explicit failures or blockers instead of success-shaped output.

## Negative Corruption Suite Requirements

ORPK-COR-001: The lane MUST create a negative corruption suite that mutates outward-run witness packages, including manifest, bundle, ledger export, artifact bytes, and claim surfaces.

ORPK-COR-002: Corruptions MUST require stable fail-closed reason codes.

ORPK-COR-003: Negative proof MUST be treated as claim-critical evidence, not optional test decoration.

## Non-Fixture Useful Slice Requirements

ORPK-NFU-001: The lane MUST select one externally useful non-fixture outward workflow scope.

ORPK-NFU-002: The selected scope MUST be operationally legible, repeatable under a stable compare scope, and bounded enough for a deterministic validator or equivalent check.

ORPK-NFU-003: Promotion of that scope into public trust wording MUST remain blocked until the proof artifacts and trust-reason contract support the change in the same update.

ORPK-NFU-004: Fixture-bounded proof may support implementation development, but it MUST NOT satisfy this slice's external usefulness requirement by itself.

## Claim Tier Taxonomy Requirements

ORPK-TIER-001: The lane MUST define outward-run claim postures with minimum evidence requirements before checker code assigns them.

ORPK-TIER-002: Any outward-specific posture ladder MUST remain subordinate to `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` for determinism wording.

ORPK-TIER-003: Public trust posture MUST require same-change admission in `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

## Deferred Extension Requirements

ORPK-SEQ-001: Multi-turn sequence proof MAY be designed in this lane, but it MUST NOT block the single-turn proof kernel.

ORPK-SEQ-002: Multi-turn sequence proof MUST prove cross-turn ordering and prior-result linkage from serialized evidence before it can be admitted.

ORPK-ODR-001: ODR determinism integration MAY be designed in this lane, but it MUST NOT claim model text determinism or whole-run determinism.

ORPK-ODR-002: Any ODR-backed deterministic claim MUST satisfy `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` before publication or release wording uses it.
