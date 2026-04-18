# Trust Reason And External Adoption v1

Last updated: 2026-04-18
Status: Active
Owner: Orket Core

Primary dependencies:
1. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
4. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

## Purpose

Define the current proof-backed external trust boundary Orket may present to outside evaluators.

This contract is intentionally narrow. It does not redefine the whole product. It defines the one bounded trust story that is currently supported by shipped proof.

## Admitted External Trust Slice

| Field | Current authority |
|---|---|
| compare scope | `trusted_repo_config_change_v1` |
| claim tier ceiling | `verdict_deterministic` |
| witness bundle schema | `trusted_run.witness_bundle.v1` |
| offline verifier report schema | `offline_trusted_run_verifier.v1` |
| evaluator guide | `docs/guides/TRUSTED_REPO_CHANGE_PROOF_GUIDE.md` |

TRAD-V1-001: All public trust, witness, offline-verification, determinism, or falsifiable-success wording governed by this contract MUST stay bounded to the admitted external trust slice above.

TRAD-V1-002: Product-level wording outside that bounded slice MUST remain neutral and MUST NOT imply broader proof than the admitted slice actually carries.

## Canonical Trust Reason

TRAD-V1-010: The canonical short-form trust reason is:

```text
Orket makes bounded workflow success independently checkable.
```

TRAD-V1-011: The canonical expanded trust reason is:

```text
For admitted compare scopes such as `trusted_repo_config_change_v1`, Orket can
package approval, effect, validator, final-truth, and claim-tier evidence into
an offline-verifiable witness bundle and refuse stronger claims when that
evidence is missing.
```

TRAD-V1-012: The trust reason MUST be framed as claim discipline over workflow success evidence. It MUST NOT depend on broad claims that:
1. all workflows are equally governed
2. all model output is correct
3. the entire runtime is mathematically proven
4. the control plane alone is the product reason to trust Orket

## Allowed Public Claims

TRAD-V1-020: Public wording MAY say the following for `trusted_repo_config_change_v1` when the compare scope and claim tier are named:
1. Orket ships a proof-only witnessable workflow slice.
2. Orket emits a `trusted_run.witness_bundle.v1` bundle for that slice.
3. Orket emits an offline verifier report for that slice.
4. Orket fails closed on denial, validator failure, missing authority evidence, and unsupported higher claims for that slice.
5. A two-run campaign on that slice currently reaches `verdict_deterministic`.
6. Orket refuses stronger claims than the evidence supports for that slice.

TRAD-V1-021: Generic repo-description wording that does not make trust, determinism, or witness claims MAY remain compare-scope-free.

TRAD-V1-022: Any wording governed by this contract MUST also say all of the following:
1. the slice is `trusted_repo_config_change_v1`
2. the current truthful claim ceiling is `verdict_deterministic`
3. replay determinism is not yet proven for that slice
4. text determinism is not yet proven for that slice
5. the slice is proof-only and fixture-bounded

## Forbidden And Deferred Claims

TRAD-V1-030: Public wording governed by this contract MUST NOT claim or imply:
1. all Orket workflows are trusted-run eligible
2. all Orket workflow success is independently verifiable
3. all Orket runs are deterministic
4. the current slice proves model output correctness
5. the current slice proves replay determinism
6. the current slice proves text determinism
7. Orket is mathematically sound in general without naming the bounded compare scope
8. logs, review packages, or summaries alone are runtime proof
9. the fixture proof demonstrates arbitrary user-workflow trust

TRAD-V1-031: ProductFlow's current replay posture MUST remain truthfully reported as missing replay proof. This contract MUST NOT relabel that posture as proven.

## Minimum Evaluator Journey

TRAD-V1-040: The minimum skeptical-evaluator path MUST include:
1. one positive approved-run proof
2. one offline verifier step
3. at least one shipped negative proof
4. inspection of the witness bundle or equivalent primary authority artifact

TRAD-V1-041: The canonical positive path is:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario approved --output benchmarks/results/proof/trusted_repo_change_live_run.json
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json
```

TRAD-V1-042: The canonical negative path is at least one of:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario denied --output benchmarks/results/proof/trusted_repo_change_denial.json
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario validator_failure --output benchmarks/results/proof/trusted_repo_change_validator_failure.json
```

TRAD-V1-043: Public evaluator material SHOULD prefer shipped negative proofs over custom corruption steps for a first evaluator. Additional corruption helpers are optional.

## Required Evidence Package

TRAD-V1-050: Public proof-backed evaluator material for this slice MUST identify the following artifact set:

| Artifact | Current path | Classification |
|---|---|---|
| approved live proof | `benchmarks/results/proof/trusted_repo_change_live_run.json` | authority-bearing proof output |
| validator report | `benchmarks/results/proof/trusted_repo_change_validator.json` | authority-bearing proof output |
| witness bundle | `workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json` | primary authority artifact |
| campaign report | `benchmarks/results/proof/trusted_repo_change_witness_verification.json` | authority-bearing proof output |
| offline verifier report | `benchmarks/results/proof/trusted_repo_change_offline_verifier.json` | authority-bearing proof output |
| denial proof | `benchmarks/results/proof/trusted_repo_change_denial.json` | negative proof output |
| validator-failure proof | `benchmarks/results/proof/trusted_repo_change_validator_failure.json` | negative proof output |

TRAD-V1-051: Human narrative material such as packet guides, implementation closeouts, and README summaries is support-only. Those materials MUST NOT replace the witness bundle, campaign report, or offline verifier report as proof authority.

TRAD-V1-052: Public evaluator material MUST distinguish authority-bearing proof artifacts from support-only narrative material.

## Publication Boundary

TRAD-V1-060: Current shipped proof is sufficient for:
1. a bounded README support section
2. a proof evaluator guide
3. docs-index links to the bounded proof authority

TRAD-V1-061: Current shipped proof is not sufficient for:
1. replacing the repo top-line README description with a trust slogan
2. broad product wording that implies general workflow trust
3. public claims of replay determinism
4. public claims of text determinism
5. public claims of mathematical soundness in the large

TRAD-V1-062: README or other public wording governed by this contract MUST link to at least one durable proof authority doc or evaluator guide. It MUST NOT rely on unsupported marketing prose.

TRAD-V1-063: Broader product-level trust repositioning is deferred until at least one of:
1. a non-fixture workflow slice has equivalent proof quality
2. stronger replay-backed proof exists on a shipped externally useful compare scope
3. a later explicitly adopted lane revises this boundary with new evidence
