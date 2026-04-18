# Offline Verifier And Claim Ladder

Last updated: 2026-04-18
Status: Implemented and archived
Authority status: Historical staging source only. Durable authority lives at `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`; lane closeout lives at `docs/projects/archive/Proof/OVCL04182026-IMPLEMENTATION-CLOSEOUT/`.
Owner: Orket Core

## Current Shipped Baseline

`docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` already defines claim tiers:

1. `replay_deterministic`
2. `verdict_deterministic`
3. `text_deterministic`
4. `non_deterministic_lab_only`

The ProductFlow replay review currently emits the right kind of truthful blocker: it reports `non_deterministic_lab_only` when replay evidence is incomplete.

## Future Delta Proposed By This Doc

Build an offline verifier that consumes a trusted-run witness bundle and returns one bounded claim.

The verifier should not run the workflow.
It should not call a model.
It should not perform side effects.
It should answer:

```text
What does this bundle prove?
What does it fail to prove?
What claim tier is allowed?
```

## What This Doc Does Not Reopen

1. It does not create a general replay engine.
2. It does not make logs authoritative.
3. It does not replace runtime validation at execution time.
4. It does not require network access.
5. It does not publish artifacts publicly without separate publication approval.

## Verifier Inputs

The verifier should accept a bundle root containing:

1. bundle manifest
2. resolved policy snapshot
3. resolved configuration snapshot
4. workload or governed input record
5. run, attempt, and step records
6. approval and operator action records when applicable
7. checkpoint and checkpoint acceptance records when applicable
8. reservation, lease, and resource records when applicable
9. effect journal records
10. final truth record
11. authored output or observed state evidence
12. MAR or equivalent completeness report
13. replay or compare report when claim tier requires it

## Verifier Output

The verifier should emit a stable JSON report with:

1. `schema_version`
2. `bundle_id`
3. `verified_at_utc`
4. `observed_path`
5. `observed_result`
6. `claim_tier`
7. `compare_scope`
8. `operator_surface`
9. `policy_digest`
10. `control_bundle_ref`
11. `evidence_ref`
12. `required_checks`
13. `passed_checks`
14. `failed_checks`
15. `missing_evidence`
16. `forbidden_claims`

Any rerunnable verifier JSON output must use the repository diff-ledger writer convention.

## Claim Ladder

The verifier should assign the lowest truthful claim tier:

1. `non_deterministic_lab_only` when evidence is useful but replay or verdict stability is not proven
2. `replay_deterministic` when the same governed bundle can be replayed and compared honestly on the declared operator surface
3. `verdict_deterministic` when repeated or campaign evidence proves stable verdicts and must-catch outcomes
4. `text_deterministic` only when byte identity or output hashes are explicitly in scope and proven

The verifier should never upgrade a claim because the model output looked good.

## Failure Semantics

The verifier must fail closed when:

1. a required authority record is missing
2. record ids drift across bundle surfaces
3. final truth claims success without sufficient evidence
4. approval continuation is not bound to the declared checkpoint and run
5. effect evidence is missing or contradicted
6. replay or compare evidence is required but absent
7. the bundle uses unsupported schema versions

These failures should be machine-readable, not prose-only.

## Acceptance Boundary

This idea is ready for implementation when:

1. the trusted-run bundle schema is known
2. the first compare scope is named
3. the first operator surface is named
4. the verifier can produce one positive report and several negative corruption reports
5. the verifier has no runtime side effects
