# Trust Reason And External Adoption Requirements Plan

Last updated: 2026-04-18
Status: Accepted and archived
Owner: Orket Core

Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/06_TRUST_REASON_AND_EXTERNAL_ADOPTION.md`
Canonical requirements draft: `docs/projects/archive/Proof/TRAD04182026-IMPLEMENTATION-CLOSEOUT/TRUST_REASON_AND_EXTERNAL_ADOPTION_REQUIREMENTS.md`
Completed dependency: `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
Completed dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Completed dependency: `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
Implementation closeout: `docs/projects/archive/Proof/TRAD04182026-IMPLEMENTATION-CLOSEOUT/TRUST_REASON_AND_EXTERNAL_ADOPTION_CLOSEOUT.md`

## Purpose

Promote only the `Trust Reason And External Adoption` idea into an active requirements lane.

This lane defines the bounded external adoption story Orket can truthfully tell after the shipped proof slices.

The core question is:

```text
What concrete trust reason should Orket present to outside users now, and what
proof-backed wording, demo path, and claim limits make that reason credible?
```

## Current Baseline

The lane starts from shipped or active authority:

1. First Useful Workflow Slice v1
2. Trusted Run Witness v1
3. Trusted Run Invariants v1
4. Control Plane Witness Substrate v1
5. Offline Trusted Run Verifier v1
6. current README and current authority wording

## Scope

In scope:

1. define Orket's external trust reason in operational, falsifiable terms
2. define the minimum proof-backed adoption path for a skeptical evaluator
3. define claims Orket may say now versus claims it must avoid
4. define publish boundaries for README, docs, and demo wording
5. define what evidence package an outside evaluator must be able to inspect

Out of scope:

1. broad marketing rewrite
2. new proof-runtime implementation
3. UI redesign
4. claiming stronger determinism than the shipped proof supports
5. treating future publication language as current authority before acceptance

## Work Items

1. Trust reason framing - complete
   - define the concrete external reason to use Orket
   - tie it to shipped proof, not philosophy

2. Claim boundary - complete
   - separate allowed claims, deferred claims, and forbidden claims
   - define compare-scope naming requirements for public wording

3. Adoption path - complete
   - define the smallest evaluator journey from install to trust judgment
   - require both positive and negative proof steps

4. Evidence package - complete
   - define the minimum artifact set a skeptical evaluator should inspect
   - define which outputs are authority versus support

5. Publication gate - complete
   - define what must exist before README or public wording changes
   - define truthful lower-tier wording if replay proof is not yet available

## Resolved Requirements Decisions

1. The external trust reason MUST center on independently checkable workflow success, not on philosophy, internal control-plane sophistication, or broad claims of correctness.
2. The current shipped compare scope for the first external adoption story MUST be `trusted_repo_config_change_v1`.
3. The highest truthful shipped claim tier for that external story MUST remain `verdict_deterministic`.
4. `replay_deterministic` and `text_deterministic` MUST remain deferred and MUST NOT be implied by public wording for the current slice.
5. The differentiator over runtimes with similar logs or summaries MUST be claim discipline: approval, effect, validator, final-truth, and claim-tier evidence are packaged so an outside evaluator can inspect them and see stronger claims fail closed.
6. The minimum evaluator journey MUST use the shipped live approved proof, offline verifier proof, and at least one shipped negative proof.
7. Current shipped proof is sufficient for a bounded README support section or proof guide, but not for replacing the repo's top-line description with a generalized trust slogan.
8. Public wording that makes determinism, trust, verification, witness, or falsifiable-success claims MUST name the compare scope and claim tier. Generic repo-description language that makes no such claim does not need compare-scope naming.

## Requirements Completion State

The canonical requirements draft now specifies:

1. the practical trust reason to use Orket now
2. the scoped compare surface and current truthful claim tier
3. the concrete reason to trust Orket over another runtime with similar data
4. the minimum evaluator journey
5. the required authority artifact package
6. allowed, deferred, and forbidden public claims
7. README, docs, demo, and broader publication gates
8. implementation handoff requirements for a later docs/publication lane

## Outcome

The user accepted this requirements lane and advanced it into same-day implementation.

The durable contract now lives at `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, and the implemented evaluator surface now lives at `docs/guides/TRUSTED_REPO_CHANGE_PROOF_GUIDE.md`.

## Remaining Open Questions

No requirements-blocking questions remain.
