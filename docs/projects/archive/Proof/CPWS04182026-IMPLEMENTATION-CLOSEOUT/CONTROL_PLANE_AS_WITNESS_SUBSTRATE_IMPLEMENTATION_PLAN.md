# Control Plane As Witness Substrate Implementation Plan

Last updated: 2026-04-18
Status: Archived implementation lane
Owner: Orket Core

Accepted requirements archive: `docs/projects/archive/Proof/CPWS04182026-IMPLEMENTATION-CLOSEOUT/CONTROL_PLANE_AS_WITNESS_SUBSTRATE_REQUIREMENTS.md`
Durable contract: `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
Dependencies:

1. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
2. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`

## Purpose

Implement the accepted Control Plane As Witness Substrate requirements for the first ProductFlow Trusted Run Witness slice.

The implementation target is:

```text
Accepted verifier output must be traceable to required authority evidence,
not to projection-only convenience surfaces.
```

## Work Items

1. Extract `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`.
2. Add a small verifier-side substrate model under `scripts/proof/`.
3. Include substrate model output and signature in `trusted_run_witness_report.v1`.
4. Fail closed when projection-only evidence is used as required authority.
5. Require stable substrate signatures before campaign promotion to `verdict_deterministic`.
6. Add contract tests for valid substrate evidence and projection-only substitution failures.
7. Run structural, contract, live ProductFlow campaign, and docs hygiene proof.
8. Archive this lane when all gates pass.

## Completion Gate

This implementation lane is complete only when:

1. the durable substrate contract exists under `docs/specs/`
2. verifier output includes `control_plane_witness_substrate`
3. projection-only substitutions fail closed
4. two-run campaign proof still reaches `verdict_deterministic`
5. docs hygiene passes
6. active `docs/projects/Proof/` docs are archived on closeout
