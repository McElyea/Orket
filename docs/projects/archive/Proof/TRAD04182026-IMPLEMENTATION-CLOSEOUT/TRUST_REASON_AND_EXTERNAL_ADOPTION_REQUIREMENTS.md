# Trust Reason And External Adoption Requirements

Last updated: 2026-04-18
Status: Accepted and archived
Owner: Orket Core

Canonical plan: `docs/projects/archive/Proof/TRAD04182026-IMPLEMENTATION-CLOSEOUT/TRUST_REASON_AND_EXTERNAL_ADOPTION_REQUIREMENTS_PLAN.md`
Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/06_TRUST_REASON_AND_EXTERNAL_ADOPTION.md`
Primary dependency: `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
Primary dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Primary dependency: `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
Primary dependency: `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
Implemented durable contract: `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`

## Purpose

Define accepted requirements for Orket's proof-backed external trust reason and adoption story.

The target is not broad positioning. The target is one truthful answer to:

```text
Why should a skeptical outside team trust Orket's workflow result more than a
runtime that only narrates success?
```

## Resolved Requirements Decisions

1. The external trust reason MUST be about independently checkable workflow success, not about broad philosophical trust language.
2. The first external trust story MUST be bounded to the shipped First Useful Workflow Slice compare scope `trusted_repo_config_change_v1`.
3. The first external trust story MUST explicitly stop at the shipped claim tier `verdict_deterministic`.
4. The practical reason to trust Orket over a runtime with similar logs or summaries MUST be framed as better claim discipline, not as simply having more data.
5. Current shipped proof is sufficient for a bounded README support section and a proof-evaluator guide, but not for replacing the repo's top-line description or making broad product-marketing claims.
6. Public wording that makes trust, determinism, witness, offline-verification, or falsifiable-success claims MUST name the compare scope and claim tier that bound the claim.
7. Public wording MUST state that replay and text determinism are not yet proven for the current external slice.

## Canonical Trust Reason

TRAD-REQ-010: The canonical short-form trust reason MUST be:

```text
Orket makes bounded workflow success independently checkable.
```

TRAD-REQ-011: The canonical expanded trust reason MUST be operationally equivalent to:

```text
For admitted compare scopes such as `trusted_repo_config_change_v1`, Orket can
package approval, effect, validator, final-truth, and claim-tier evidence into
an offline-verifiable witness bundle and refuse stronger claims when that
evidence is missing.
```

TRAD-REQ-012: The accepted trust reason MUST NOT depend on claims that the model output is correct, that all Orket runs are governed equally, or that the whole runtime is mathematically proven.

## Practical Adoption Reason

TRAD-REQ-020: The requirements MUST define the practical reason to choose Orket over a runtime with similar data as better truth discipline over that data.

TRAD-REQ-021: The accepted practical differentiators MUST be:

1. success is tied to approval, effect, validator, and final-truth evidence rather than to narration alone
2. higher trust claims are downgraded or blocked when repeat or replay evidence is missing
3. an outside evaluator can inspect the witness bundle and offline verifier without rerunning the entire runtime
4. required authority is distinguished from support-only summaries and projections
5. fail-closed negative cases are part of the shipped proof story

TRAD-REQ-022: The accepted external reason MUST NOT be framed as "Orket has more logs," "Orket has a bigger control plane," or "Orket is more correct in general than other runtimes."

## Allowed Public Claims Now

TRAD-REQ-030: Current allowed public claims MUST be limited to what is already shipped and observed on `trusted_repo_config_change_v1`.

TRAD-REQ-031: Public wording MAY say all of the following, provided the compare scope and claim tier are named when the statement is trust-claiming:

1. Orket has a shipped bounded proof slice for `trusted_repo_config_change_v1`
2. Orket can emit a `trusted_run.witness_bundle.v1` bundle for that slice
3. Orket can emit an offline verifier report for that slice
4. Orket can fail closed on denial, validator failure, missing authority evidence, and unsupported higher claims for that slice
5. a two-run campaign on that slice currently reaches `verdict_deterministic`

TRAD-REQ-032: Public wording MAY say that Orket "refuses stronger claims than the evidence supports" only when accompanied by the current bounded compare scope and the current shipped claim-tier limit.

TRAD-REQ-033: Generic repo-description wording that does not make determinism or trust claims MAY remain compare-scope-free.

## Deferred And Forbidden Claims

TRAD-REQ-040: Public wording MUST NOT claim or imply any of the following today:

1. all Orket workflows are trusted-run eligible
2. all Orket workflow success is independently verifiable
3. all Orket runs are deterministic
4. the current slice proves model output correctness
5. the current slice proves replay determinism
6. the current slice proves text determinism
7. Orket is mathematically sound in general without naming the bounded model and compare scope
8. logs, review packages, or summaries alone are proof of runtime truth

TRAD-REQ-041: Public wording about `trusted_repo_config_change_v1` MUST explicitly stop at `verdict_deterministic` unless stronger evidence is later shipped on that same compare scope.

TRAD-REQ-042: Public wording MUST NOT reuse the current fixture proof as evidence that arbitrary user workflows are trusted-run verified.

TRAD-REQ-043: README, guide, demo, or publication wording MUST NOT relabel ProductFlow's current replay posture as proven while it still truthfully reports missing replay proof.

## Minimum Evaluator Journey

TRAD-REQ-050: The minimum skeptical-evaluator path MUST be small enough to run locally and MUST include:

1. one positive approved-run proof
2. one offline verifier step
3. at least one shipped negative proof
4. inspection of the witness bundle or equivalent authority artifact

TRAD-REQ-051: The canonical current evaluator path MUST be grounded in the shipped useful-workflow commands:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario approved --output benchmarks/results/proof/trusted_repo_change_live_run.json
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json
```

TRAD-REQ-052: The canonical current negative path MUST include at least one of:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario denied --output benchmarks/results/proof/trusted_repo_change_denial.json
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario validator_failure --output benchmarks/results/proof/trusted_repo_change_validator_failure.json
```

TRAD-REQ-053: The evaluator journey SHOULD prefer shipped negative proof artifacts over asking a first evaluator to hand-edit JSON proof files.

TRAD-REQ-054: A dedicated corruption-demo helper command would improve adoption, but it is not a requirements blocker for this lane because denial and validator-failure proofs already demonstrate fail-closed behavior and the corruption matrix is exercised in shipped tests.

## Evidence Package Requirements

TRAD-REQ-060: The minimum artifact package for a skeptical evaluator MUST include:

| Artifact | Current path | Classification | Why it matters |
|---|---|---|---|
| approved live proof | `benchmarks/results/proof/trusted_repo_change_live_run.json` | authority-bearing proof output | shows the bounded approved path completed |
| validator report | `benchmarks/results/proof/trusted_repo_change_validator.json` | authority-bearing proof output | shows deterministic config validation |
| witness bundle | `workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json` | primary authority artifact | carries approval, effect, validator, and final-truth evidence |
| campaign report | `benchmarks/results/proof/trusted_repo_change_witness_verification.json` | authority-bearing proof output | shows stable repeat evidence and campaign claim tier |
| offline verifier report | `benchmarks/results/proof/trusted_repo_change_offline_verifier.json` | authority-bearing proof output | shows the highest truthful allowed claim |
| denial proof | `benchmarks/results/proof/trusted_repo_change_denial.json` | negative proof output | shows terminal stop before mutation |
| validator-failure proof | `benchmarks/results/proof/trusted_repo_change_validator_failure.json` | negative proof output | shows validator failure blocks success |

TRAD-REQ-061: The evaluator artifact package MAY include human support material such as closeout docs or packet guides, but those MUST be explicitly presented as support-only and MUST NOT replace the witness bundle, campaign report, or offline verifier report.

TRAD-REQ-062: When public docs summarize the package, they MUST distinguish:

1. authority-bearing proof artifacts
2. support-only narrative or review docs

TRAD-REQ-063: Any public or README-level trust section MUST link to at least one durable proof authority doc or proof guide, not only to prose marketing copy.

## Publication Gate Requirements

TRAD-REQ-070: Current shipped proof is sufficient for a bounded README support section, a proof guide, and an evaluator walkthrough, provided those surfaces stay scoped to `trusted_repo_config_change_v1` and `verdict_deterministic`.

TRAD-REQ-071: Current shipped proof is NOT sufficient to replace the existing top-line README description with a broad trust slogan.

TRAD-REQ-072: Current shipped proof is NOT sufficient for broad product or marketing wording that implies:

1. general workflow trust across Orket
2. universal offline verification
3. replay determinism
4. mathematical soundness in the large

TRAD-REQ-073: If README or public wording is updated from this lane, it MUST:

1. name `trusted_repo_config_change_v1`
2. name the current truthful claim tier `verdict_deterministic`
3. state that replay and text determinism are not yet proven for that slice
4. state that the shipped slice is proof-only and fixture-bounded

TRAD-REQ-074: A broader headline or product-level trust repositioning MUST wait for at least one of:

1. a non-fixture workflow slice with equivalent proof quality
2. stronger replay-backed proof on a shipped externally useful compare scope
3. a later explicitly adopted lane that re-evaluates product-level wording with new evidence

## Implementation Handoff Requirements

TRAD-REQ-080: The accepted implementation plan for this lane SHOULD stay documentation-first unless the user explicitly asks for new runtime proof surfaces.

TRAD-REQ-081: The first implementation handoff SHOULD include:

1. a proof-backed evaluator guide
2. a scoped README support section or equivalent docs index entry
3. explicit allowed-claim and forbidden-claim wording
4. direct links to the shipped proof artifacts and durable proof specs

TRAD-REQ-082: If the implementation changes canonical public wording, proof commands, or proof artifact paths, the same change MUST update `CURRENT_AUTHORITY.md` and any affected durable specs.

## Open Requirements Questions

No requirements-blocking questions remain.

Possible later refinements that are not blocking this lane:

1. whether to add a dedicated corruption-demo helper command
2. the exact final section title for a future README support block
3. whether a later public guide should compare ProductFlow and useful-workflow trust surfaces side by side

## Acceptance State

These requirements were accepted and implemented on 2026-04-18 because they specify:

1. the practical trust reason to use Orket now
2. the current truthful compare scope and claim tier
3. the reason to trust Orket over a runtime with similar data
4. the minimum evaluator journey
5. the required evaluator artifact package
6. allowed claims, deferred claims, and forbidden claims
7. bounded README, docs, and broader publication gates
8. a documentation-first implementation handoff

The lane is now closed and archived. Historical implementation closeout lives at `docs/projects/archive/Proof/TRAD04182026-IMPLEMENTATION-CLOSEOUT/TRUST_REASON_AND_EXTERNAL_ADOPTION_CLOSEOUT.md`.
