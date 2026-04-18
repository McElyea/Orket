# Mathematical Foundation And Invariants Requirements Plan

Last updated: 2026-04-18
Status: Archived accepted requirements lane
Owner: Orket Core

Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/03_MATHEMATICAL_FOUNDATION_AND_INVARIANTS.md`
Canonical requirements draft archive: `docs/projects/archive/Proof/MFI04182026-IMPLEMENTATION-CLOSEOUT/MATHEMATICAL_FOUNDATION_AND_INVARIANTS_REQUIREMENTS.md`
Completed dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Completed dependency archive: `docs/projects/archive/Proof/TRW04162026-IMPLEMENTATION-CLOSEOUT/`

## Purpose

Promote only the `Mathematical Foundation And Invariants` idea into an active lane.

This lane defines the bounded formal foundation for Orket's trusted-run proof surface. It is not a claim that the whole Python runtime is formally verified. The first useful claim is narrower:

```text
If a verifier accepts a trusted-run witness bundle,
then the recorded trace satisfies the declared trusted-run invariants
for the named compare scope.
```

## Current Baseline

The lane starts from shipped or active authority:

1. target runtime architecture in `docs/ARCHITECTURE.md`
2. determinism claim policy in `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
3. minimum auditable record rules in `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
4. trusted-run witness contract in `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
5. ProductFlow trusted-run witness scripts under `scripts/proof/`
6. control-plane contract models under `orket/core/contracts/`

The completed Trusted Run Witness v1 implementation gives this lane a concrete first compare scope: `trusted_run_productflow_write_file_v1`.

## Scope

In scope:

1. define a small state-machine model for trusted-run witness verification
2. define the first invariant set for accepted trusted-run bundles
3. map each invariant to verifier checks or explicit missing-proof blockers
4. define the negative corruption cases each invariant must catch
5. state what proof tier the model supports and what remains outside the model
6. decide whether the durable output is a new spec, likely `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`

Out of scope:

1. full formal verification of Orket
2. proving model-generated text is semantically correct
3. proving all runtime paths
4. changing the Trusted Run Witness v1 implementation during requirements work
5. replacing live proof, integration proof, or contract proof
6. adopting the rest of `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/`

## Dependency Position

This lane is dependent on the accepted and implemented Trusted Run Witness v1 surface because it needs a real witness bundle schema and verifier report to model.

This lane is not blocked by:

1. offline verifier productization
2. public adoption work
3. observability dashboard work
4. broader ControlPlane expansion

## Work Items

1. Requirements hardening
   - refine the model boundary
   - identify exactly which state transitions are modeled
   - separate model truth from runtime implementation detail
   - archived draft: `docs/projects/archive/Proof/MFI04182026-IMPLEMENTATION-CLOSEOUT/MATHEMATICAL_FOUNDATION_AND_INVARIANTS_REQUIREMENTS.md`

2. Invariant inventory
   - start with final truth, run lineage, approval continuation, checkpoint acceptance, reservation/lease, effect journal, and side-effect-free verification invariants
   - classify each invariant as bundle-level, verifier-level, campaign-level, or runtime-level

3. Proof obligation mapping
   - map each invariant to existing `Trusted Run Witness v1` verifier checks where possible
   - name gaps as missing proof rather than implied correctness

4. Negative corruption matrix
   - define one-field or one-family corruptions that must fail closed
   - align with the current must-catch outcomes from `docs/specs/TRUSTED_RUN_WITNESS_V1.md`

5. Durable spec decision
   - decide whether to extract `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
   - if extracted, define the relationship between that spec and `docs/specs/TRUSTED_RUN_WITNESS_V1.md`

6. Implementation handoff
   - produce a bounded implementation plan only after requirements are accepted
   - do not treat this requirements lane as implementation-complete because an implementation plan exists

## Completion Gate

This requirements lane can close only when:

1. the accepted formal model is smaller than the implementation
2. every accepted invariant has an explicit verifier check, contract test, or truthful missing-proof blocker
3. the negative corruption matrix names the expected fail-closed result for each corruption
4. the lane states exactly which proof tier is supported
5. remaining implementation decisions are listed explicitly
6. the user accepts the requirements or explicitly retires the lane

## Initial Open Questions

1. Which existing Trusted Run Witness checks are durable enough to become invariant authority rather than implementation detail?
2. Can effect-journal prior-chain proof be derived from current bundle fields, or does the bundle need schema expansion?
3. Can resource-versus-lease contradiction proof be derived from current bundle fields, or does the bundle need schema expansion?
4. What exact machine-readable shape should missing-proof blockers use in the later implementation?

## Resolved Decisions

1. The first model uses both a finite state-machine table and lightweight rule notation.
2. Requirements use stable `MFI-REQ-###` ids.
3. Invariants use stable `TRI-INV-###` ids.
4. Later implementation proof should include both property-style trace coverage and serialized witness corruption coverage unless explicitly scoped down.
5. Durable contract extraction target is `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` if the user accepts these requirements.
