# Slice 08 - ODR Determinism Integration

Last updated: 2026-05-02
Status: Deferred slice plan
Owner: Orket Core

Parent future lane: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`
Base archive: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`

## Purpose

Connect existing ODR canonicalization evidence to the outward-run proof kernel without claiming model text determinism or whole-run determinism.

## Deferred Precondition

Slices 01 through 06 must meet their exit criteria before this slice can close. This slice may inform bundle extensibility now, but it must not block the single-turn proof kernel.

## Scope

In scope:
1. identifying whether proposal extraction can emit ODR canonical evidence
2. carrying ODR canonical hashes in the outward witness bundle
3. checking ODR evidence when a future deterministic posture is requested
4. reusing deterministic permutation-test patterns from the existing ODR gate work

Out of scope:
1. rewriting ODR
2. claiming model output is deterministic
3. claiming full outward-run replay determinism
4. adding public determinism wording before `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` permits it

## Optional Bundle Field Draft

```json
{
  "odr_evidence": {
    "schema_version": "outward_odr_evidence.v1",
    "scope": "proposal_extraction",
    "run_id": "<string>",
    "turns": [
      {
        "turn_index": 0,
        "canonical_hash": "<sha256 hex>",
        "raw_signature": "<string>",
        "permutation_stable": true,
        "permutation_test_count": 10
      }
    ],
    "odr_gate_version": "<string>",
    "odr_evidence_digest": "<sha256 hex>"
  }
}
```

Classification: authority only for hashes produced by the ODR gate at runtime; derived for post-hoc permutation status unless the permutation proof artifact is included.

## New Invariant

| ID | Invariant | Failure Code |
|---|---|---|
| ORP-INV-021 | If a future outward deterministic posture is requested, ODR evidence and campaign evidence must prove matching canonical hashes for the bounded ODR-gated surface. | `odr_determinism_not_proven` |

## Determinism Claim Rule

This slice may only propose a deterministic posture after:
1. ODR evidence exists in at least two bundles,
2. campaign evidence shows matching canonical hashes for the same compare scope,
3. permutation evidence is captured,
4. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` is satisfied, and
5. claim wording names the exact bounded surface, not the whole run.

## Implementation Path

1. Extend the bundle producer to optionally include ODR evidence for proposal extraction.
2. Extend the verifier to check ORP-INV-021 only when ODR evidence and deterministic posture are requested.
3. Add an outward ODR permutation proof command modeled after existing seed-based deterministic mutation patterns.
4. Record output under a stable proof path before any claim uses it.

## Exit Criteria

1. ODR evidence is emitted for at least one admitted run
2. ORP-INV-021 accepts valid bounded ODR evidence and rejects drifted evidence
3. any deterministic claim obeys `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
4. Slices 01 through 06 remain green
