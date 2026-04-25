# Finite Trust Kernel Model v1

Last updated: 2026-04-23
Status: Active durable contract
Owner: Orket Core

## Purpose

Define the finite evidence model required by the Trust Kernel and Portable Conformance lane.

This contract does not prove Orket in general.
It defines a bounded model over serialized trusted-run evidence so an admitted verifier can accept, reject, or downgrade claims without consulting mutable runtime state.

## Scope

Adopted lane scope:
1. active implementation lane: Trust Kernel and Portable Conformance,
2. adopted workstream: finite trust-kernel model,
3. initial admitted compare scope: existing `trusted_repo_config_change_v1`,
4. deferred preferred future compare scope: `trusted_repo_manifest_change_v1`.

This contract depends on:
1. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`,
2. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`,
3. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`,
4. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`,
5. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

## Non-Goals

This contract does not:
1. admit a new workflow scope by itself,
2. claim replay determinism,
3. claim text determinism,
4. verify model output correctness,
5. replace witness bundles, validator reports, campaign reports, offline verifier reports, or packet verifier reports.

## Artifact Roles

Artifacts in this model must be classified as:
1. authority-bearing input evidence,
2. claim-bearing verifier output,
3. claim-supporting derived evidence,
4. support-only material,
5. generated corruption.

An artifact may have more than one role only when the adopted contract explicitly says so.
Claim-supporting derived evidence must not replace the evidence it summarizes.

## Model Input Boundary

FTKM-001. Model evaluation must consume serialized evidence only.

FTKM-002. Model evaluation must not consult:
1. live databases,
2. clocks,
3. process environment,
4. model providers,
5. network services,
6. mutable runtime state.

FTKM-003. Model evaluation must be side-effect free with respect to workflow state.

## Required State Set

FTKM-010. The model must distinguish at least:
1. no admissible bundle,
2. admitted input observed,
3. policy and configuration observed,
4. approval or operator decision observed,
5. checkpoint accepted,
6. resource authority established,
7. effect evidence observed,
8. validator or contract verdict observed,
9. final truth observed,
10. verifier accepted,
11. verifier rejected,
12. claim downgraded.

## Required Transition Classes

FTKM-020. The model must define transition classes independent of implementation call stacks.

FTKM-021. At minimum, transition classes must cover:
1. admit run,
2. resolve policy and configuration,
3. request operator decision,
4. resolve operator decision,
5. accept checkpoint,
6. establish reservation, lease, or resource authority,
7. publish effect evidence,
8. publish validator or contract verdict,
9. publish final truth,
10. build witness bundle,
11. verify bundle,
12. assign claim tier.

FTKM-022. Each accepted transition must have explicit preconditions.

## Forbidden Transitions

FTKM-030. The model must fail closed for forbidden transitions.

FTKM-031. At minimum, the model must forbid:
1. success without final truth,
2. success without effect evidence for a mutation scope,
3. success without required approval or operator action,
4. success when required validator evidence is missing or failing,
5. claim upgrade without required repeat, replay, or text-identity evidence,
6. authority projection replacing authority evidence,
7. logs or summaries replacing witness authority.

FTKM-032. Forbidden-transition failures must classify the failure cause as one of:
1. missing evidence,
2. contradictory evidence,
3. stale evidence,
4. malformed evidence,
5. unsupported claim request.

## Invariant Mapping

FTKM-040. Every acceptance condition must map to stable invariant ids.

FTKM-041. Existing `TRI-*`, `TRC-*`, substrate, validator, and packet-verifier invariant ids must be reused where they already apply.

FTKM-042. New invariant ids may be introduced only for genuinely new model obligations.

## Signature Semantics

FTKM-050. The finite-model signature is not authority by itself.

FTKM-051. The signature is claim-supporting only when produced by the admitted verifier over admitted evidence and recorded in a verifier report or conformance summary.

FTKM-052. The signature must be stable for equivalent successful evidence.

FTKM-053. Signature material must include:
1. model schema version,
2. compare scope,
3. operator surface,
4. invariant ids and statuses,
5. must-catch outcome set,
6. claim-tier blockers,
7. missing-proof blockers.

FTKM-054. Signature material must exclude:
1. timestamps,
2. generated ids,
3. session-local paths,
4. absolute local path prefixes,
5. diff-ledger entries,
6. input file order where the contract defines canonical ordering.

## Evidence Equivalence

FTKM-060. Evidence equivalence must be defined by canonical normalization, not implementation-local comparison logic.

FTKM-061. Equivalent successful evidence must share:
1. compare scope,
2. operator surface,
3. bounded mutation or effect class,
4. invariant statuses,
5. claim blockers and missing-proof blockers,
6. normalized validator verdict where the scope uses a validator,
7. explicitly declared non-semantic field exclusions.

## Proof Requirements

FTKM-070. Contract proof must include:
1. positive fixture acceptance,
2. negative fixture rejection,
3. expected reason codes for negative fixtures,
4. stable signatures for equivalent accepted fixtures,
5. a missing-proof case that blocks success instead of producing success-shaped output.

FTKM-071. Structural proof must show:
1. model evaluation is side-effect free,
2. model signatures are not accepted as authority without the admitted verifier path,
3. all required invariant ids are present.
