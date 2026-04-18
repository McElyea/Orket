# Offline Verifier And Claim Ladder Requirements Plan

Last updated: 2026-04-18
Status: Completed requirements - archived with implementation closeout
Owner: Orket Core

Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/04_OFFLINE_VERIFIER_AND_CLAIM_LADDER.md`
Canonical requirements draft: `docs/projects/archive/Proof/OVCL04182026-IMPLEMENTATION-CLOSEOUT/OFFLINE_VERIFIER_AND_CLAIM_LADDER_REQUIREMENTS.md`
Completed dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Completed dependency: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
Completed dependency: `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`

## Purpose

Promote only the `Offline Verifier And Claim Ladder` idea into an active requirements lane.

This lane defines the requirements for a side-effect-free verifier surface that can consume trusted-run evidence and return the highest truthful claim tier allowed by that evidence.

The first bounded claim is:

```text
An offline verifier may inspect trusted-run evidence and assign a claim tier,
but it must not run the workflow, call a model, mutate workflow state, or
upgrade claims beyond the evidence required by the claim ladder.
```

## Current Baseline

The lane starts from shipped or active authority:

1. determinism claim policy in `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
2. trusted-run witness contract in `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. trusted-run invariant contract in `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. control-plane witness substrate contract in `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
5. current proof scripts under `scripts/proof/`
6. ProductFlow replay review's existing truthful blocker behavior

## Scope

In scope:

1. define offline verifier inputs and outputs
2. define the claim ladder transition rules
3. define which evidence allows `non_deterministic_lab_only`, `verdict_deterministic`, `replay_deterministic`, and `text_deterministic`
4. define fail-closed semantics for unsupported schemas, missing evidence, drifted records, and forbidden claim upgrades
5. define proof requirements for positive and negative verifier examples
6. decide whether accepted output becomes `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

Out of scope:

1. implementing a general replay engine
2. calling models or providers
3. running the workflow
4. making logs authoritative
5. publishing artifacts publicly
6. replacing runtime validation at execution time
7. changing claim tiers without updating `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

## Work Items

1. Requirements hardening - complete
   - define the verifier boundary
   - separate offline inspection from runtime execution
   - define allowed artifact roots and schemas

2. Claim ladder rules - complete
   - map required evidence to each claim tier
   - define downgrade behavior when evidence is missing
   - define forbidden claims

3. Verifier input contract - complete
   - list required bundle/report artifacts
   - define optional replay and compare inputs
   - define schema and digest checks

4. Verifier output contract - complete
   - define stable JSON report fields
   - require observed path/result, claim tier, compare scope, operator surface, and missing evidence
   - require diff-ledger writer convention for rerunnable JSON output

5. Negative proof matrix - complete
   - unsupported schema
   - missing authority
   - drifted ids
   - missing final truth
   - missing replay evidence
   - text-determinism overclaim

6. Durable spec decision - complete
   - decide whether accepted output becomes `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
   - update `CURRENT_AUTHORITY.md` only if behavior, canonical paths, or source-of-truth contracts change

## Resolved Initial Questions

1. The first offline verifier should consume raw witness bundles, single trusted-run verifier reports, and campaign reports as separate input modes.
2. The standalone offline-verifier report should use `benchmarks/results/proof/offline_trusted_run_verifier.json`; the existing trusted-run witness verifier output remains `benchmarks/results/proof/trusted_run_witness_verification.json`.
3. `replay_deterministic` remains future-gated until replay evidence independently satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.
4. `text_deterministic` requires explicit byte identity or declared output-hash identity on the same compare scope, plus the policy-required verdict or replay evidence.
5. Corruption examples should be table-driven/generated first; stored fixtures are optional after generated corruption tests prove the contract.

## Requirements Completion State

The canonical requirements draft now specifies:

1. side-effect-free verifier boundary
2. supported input modes
3. required input evidence by mode
4. stable output schema requirements
5. claim ladder evidence matrix
6. forbidden claim mapping
7. failure semantics
8. positive and negative proof requirements
9. durable spec extraction decision

This requirements lane was accepted by the user's `continue` instruction on 2026-04-18 and moved into implementation.

## Completion Gate

This requirements lane can close only when:

1. the verifier boundary is explicit and side-effect-free
2. every supported claim tier has required evidence
3. every unsupported or forbidden claim has fail-closed behavior
4. the verifier report schema is specified
5. positive and negative proof requirements are listed
6. durable spec extraction is decided
7. the user accepts the requirements or explicitly retires the lane

## Remaining Open Questions

No requirements-blocking questions remain.

Implementation details such as exact CLI argument names, module layout, and whether future text/replay evidence schemas arrive in the first implementation are intentionally deferred to the accepted implementation plan.
