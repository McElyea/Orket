# Trusted Change Scope Admission Standard v1

Last updated: 2026-04-18
Status: Active contract
Owner: Orket Core

This spec defines the durable admission standard for governed-proof trusted change scopes.

## Dependencies

This contract depends on:

1. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
2. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
3. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
4. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
5. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`

## Purpose

Admit trusted change scopes through one durable standard without collapsing:

1. internal admitted compare scopes into the narrower external/public trust slice,
2. scope-local validator or decision vocabularies into generic trust wording, or
3. working-lane drafts into durable authority.

## Boundary

This spec does not, by itself:

1. admit a compare scope,
2. broaden current public trust wording,
3. replace a scope-local contract under `docs/specs/`, or
4. replace `CURRENT_AUTHORITY.md` as the current authority snapshot.

A scope becomes admitted only when the admission requirements below, the scope-local contract, the catalog entry, and the current-authority update all land in the same change.

## Durable Admission Checklist

A candidate scope is not ready for admission until the repo can answer each field below without relying on prose-only justification.

| Field | Required answer |
|---|---|
| compare scope | exact compare-scope name |
| operator surface | exact operator-facing surface or report family |
| contract verdict surface | exact contract verdict schema or equivalent deterministic surface |
| validator surface | exact validator family if the scope uses one |
| bounded effect surface | one bounded task with clear success and failure semantics |
| allowed mutation boundary | exact files, resources, or decision outputs the scope may change |
| required authority families | exact authority records or equivalent primary evidence needed for success |
| evidence vocabulary reuse / no relabeling | exact statement of which existing trusted-run evidence vocabulary is reused and explicit confirmation that the scope does not relabel evidence from another compare scope |
| must-catch corruption set | exact negative cases the scope must catch |
| single-run fallback claim tier | highest truthful claim from one valid run |
| campaign claim tier ceiling | highest truthful claim from repeat evidence |
| canonical live proof commands | exact live proof command or commands |
| canonical witness output path | exact stable witness output location |
| canonical offline verifier command | exact offline claim-evaluator path |
| evaluator guide | one human-readable guide for skeptical evaluation |
| forbidden claims | exact stronger claims the scope may not make |
| current proof limitations | explicit exposed limitations that remain in force |
| durable authority path | exact `docs/specs/` location once promoted |

## Admission Rule

A governed-proof compare scope is durably admitted only when all of the following are true:

1. one scope-local contract under `docs/specs/` defines the scope identity, mutation boundary, proof commands, output paths, and forbidden claims,
2. `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md` adds or updates the scope's catalog entry in the same change,
3. `CURRENT_AUTHORITY.md` records the canonical commands, compare scope, publication status, and output paths in the same change,
4. the scope's live proof, witness verification, and offline claim evaluation surfaces all pass truthfully for the admitted claim ceiling, and
5. external/public trust wording remains unchanged unless a separate same-change update truthfully broadens that boundary.

## Family Reuse Rules

Trusted scope admission MUST preserve family reuse where a truthful shared seam already exists.

| Need | Current family standard |
|---|---|
| witness bundle packaging | reuse `trusted_run.witness_bundle.v1` from `docs/specs/TRUSTED_RUN_WITNESS_V1.md` |
| invariant and substrate evidence | reuse `trusted_run_invariant_model.v1` and `control_plane_witness_substrate.v1` |
| offline claim ladder | reuse `offline_trusted_run_verifier.v1` and its admitted claim ladder |
| diff-ledger output discipline | rerunnable JSON outputs use the repository diff-ledger writer convention |
| validator-backed campaign and offline evaluation | `scripts/proof/trusted_scope_family_support.py` is the current shared implementation seam for validator-backed compare scopes that reuse the trusted-run witness report family, with claim-ladder/common helpers kept under `scripts/proof/trusted_scope_family_*.py` |

Validators MAY remain scope-local where the deterministic decision surface differs by effect class. When a scope uses a validator, it MUST still expose a stable `validator_signature_digest` and machine-readable failure vocabulary.

Witness-bundle construction MAY remain scope-local where bounded effects differ. It MUST still reuse the admitted trusted-run witness schema and must not mint a new evidence vocabulary without same-change authority updates.

Corruption matrices MAY remain scope-local. Each admitted scope MUST publish its minimum must-catch corruption set in its scope contract and keep that set reflected in scope-local contract tests.

## Publication Rule

Admission and publication are not the same thing.

The internal admitted compare-scope set MAY be broader than the external/public trust slice. A newly admitted scope joins the external/public slice only when:

1. its current admitted evidence truthfully supports scope-local public wording,
2. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` is updated in the same change,
3. `CURRENT_AUTHORITY.md` reflects the new publication status in the same change, and
4. public wording stops at the highest claim ceiling the offline verifier actually permits.
