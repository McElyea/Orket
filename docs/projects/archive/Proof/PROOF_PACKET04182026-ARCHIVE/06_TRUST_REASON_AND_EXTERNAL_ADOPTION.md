# Trust Reason And External Adoption

Last updated: 2026-04-18
Status: Promoted, accepted, implemented, and archived
Authority status: Historical staging source only. Implementation archive lives at `docs/projects/archive/Proof/TRAD04182026-IMPLEMENTATION-CLOSEOUT/`.
Owner: Orket Core

## Current Shipped Baseline

The current README says Orket is a local-first workflow runtime for card-based execution with persistent state, tool gating, and multiple operator surfaces.

That is true, but it is not yet the strongest external adoption reason.

The strongest emerging reason is:

```text
Orket can make workflow success falsifiable.
```

## Future Delta Proposed By This Doc

Shape the adoption story around evidence-backed trust, not philosophy.

The practical reason to use Orket should be:

```text
Use Orket when you need a model-assisted workflow runtime that refuses to call work successful unless the evidence supports that claim.
```

## What This Doc Does Not Reopen

1. It does not rewrite public marketing copy by itself.
2. It does not authorize broad README changes before proof exists.
3. It does not claim Orket is more correct than other runtimes in general.
4. It does not claim full determinism.
5. It does not claim all workflows are trusted-run eligible.

## External User Need

An outside team does not primarily need Orket's internal authority model.

They need answers to practical questions:

1. Can I see what the model was asked to do?
2. Can I see what tool or mutation was attempted?
3. Can I tell whether a human approved the risky part?
4. Can I prove which file or resource changed?
5. Can I tell whether success means verified success or just narrated success?
6. Can I replay or independently verify the evidence?
7. Can I see when the runtime refuses to overclaim?

## Trust Claims Orket Should Earn

After a trusted-run witness lane exists, Orket can truthfully work toward claims like:

1. Orket separates model suggestions from runtime authority.
2. Orket records bounded approval and continuation evidence.
3. Orket ties success to final-truth evidence.
4. Orket labels replay and stability claims with explicit claim tiers.
5. Orket reports missing proof as missing proof.
6. Orket can produce an offline-verifiable witness bundle for a bounded workflow.

These claims are useful because they are falsifiable.

## Claims Orket Should Avoid

Orket should not say:

1. all Orket runs are deterministic
2. Orket proves model output is correct
3. Orket is mathematically sound without naming the bounded model and compare scope
4. Orket's control plane is universal
5. ProductFlow replay is proven while it still reports `not_evaluable`
6. logs alone are proof of runtime truth

## Adoption Path

The adoption path should be small:

1. install Orket
2. run one trusted workflow fixture
3. inspect the witness bundle
4. run the offline verifier
5. corrupt one required evidence field and see the verifier fail
6. adapt the workflow to one local repo use case

That path is stronger than a broad demo because it shows the negative case.

## Product Test

The product test is:

```text
Would a skeptical reviewer trust this workflow result more after reading the witness bundle and verifier report?
```

If the answer is no, the work is probably control-plane expansion without external trust value.

## Acceptance Boundary

This idea should influence public-facing docs only after:

1. at least one trusted-run bundle exists
2. the offline verifier passes on the bundle
3. negative corruption checks fail closed
4. the claim tier is at least `replay_deterministic` or a truthful lower-tier limitation is explicitly acceptable
5. README or public wording names the compare scope instead of claiming broad determinism
