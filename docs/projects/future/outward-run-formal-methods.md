# Future Lane - Outward Run Formal Methods

Last updated: 2026-05-02
Status: Future hold
Owner: Orket Core

Related completed boundary: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`
Related future extensions: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

## Purpose

Preserve future formal-methods ideas without making them active proof-kernel exit criteria.

## Candidate Future Work

1. Encode the outward-run labeled transition system in Alloy and check bounded instances of the reachability properties.
2. Explore Coq or Lean formalization of the transition system and prove R1 through R3 by induction.
3. Investigate a correspondence proof between the formal model and the Python invariant checker.
4. Add property-based generation of valid and invalid event sequences if dependency policy permits.

## Reopen Trigger

Reopen only after:
1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md` is an active durable contract,
2. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md` is an active durable contract,
3. the outward-run proof kernel has a green single-turn package producer, offline verifier, invariant checker, and corruption suite, and
4. the proposed formal model maps back to ORP-INV ids and verifier failure-code vocabulary.

## Non-Goals

1. This future lane must not block the active single-turn proof kernel.
2. This future lane must not claim Orket is mathematically proven in general.
3. This future lane must not replace serialized-evidence proof with prose.
4. Formal models must reuse the accepted outward witness schema, ORP-INV ids, and verifier failure-code vocabulary.
5. A formal result without a correspondence argument to the Python verifier is exploratory only.
