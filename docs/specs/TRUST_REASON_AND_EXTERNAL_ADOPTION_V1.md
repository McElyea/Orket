# Trust Reason And External Adoption v1

Last updated: 2026-04-19
Status: Active
Owner: Orket Core

Primary dependencies:
1. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
4. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
5. `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`
6. `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
7. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`

## Purpose

Define the current proof-backed external trust boundary Orket may present to outside evaluators.

This contract is intentionally narrow. It does not redefine the whole product. It defines the one bounded trust story that is currently supported by shipped proof.

## Admitted External Trust Slice

| Field | Current authority |
|---|---|
| compare scope | `trusted_repo_config_change_v1` |
| claim tier ceiling | `verdict_deterministic` |
| governed change packet schema | `governed_change_packet.v1` |
| witness bundle schema | `trusted_run.witness_bundle.v1` |
| offline verifier report schema | `offline_trusted_run_verifier.v1` |
| standalone packet verifier schema | `governed_change_packet_standalone_verifier.v1` |
| evaluator guide | `docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md` |

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
an inspectable governed change packet plus underlying witness authority and
refuse stronger claims when that evidence is missing.
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
4. Orket emits a `governed_change_packet.v1` entry artifact for that slice.
5. Orket emits a standalone packet verifier report for that slice.
4. Orket fails closed on denial, validator failure, missing authority evidence, and unsupported higher claims for that slice.
6. A two-run campaign on that slice currently reaches `verdict_deterministic`.
7. Orket refuses stronger claims than the evidence supports for that slice.

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
2. one standalone packet verifier step
3. at least one shipped negative proof
4. inspection of the witness bundle or equivalent primary authority artifact

TRAD-V1-041: The canonical positive path is:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_repo_change_packet.py
python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json
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
| governed change packet | `benchmarks/results/proof/governed_repo_change_packet.json` | primary operator entry artifact |
| packet verifier report | `benchmarks/results/proof/governed_repo_change_packet_verifier.json` | authority-bearing proof output |
| trusted-kernel model report | `benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json` | authority-bearing proof output |
| denial proof | `benchmarks/results/proof/trusted_repo_change_denial.json` | negative proof output |
| validator-failure proof | `benchmarks/results/proof/trusted_repo_change_validator_failure.json` | negative proof output |

TRAD-V1-051: Human narrative material such as packet guides, implementation closeouts, and README summaries is support-only. Those materials MUST NOT replace the witness bundle, campaign report, offline verifier report, or packet verifier report as proof authority.

TRAD-V1-051A: The governed change packet is an operator entry artifact, not a substitute authority surface. Packet projections MUST NOT outrank the witness bundle, campaign report, offline verifier report, or packet verifier report.

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
1. a non-fixture workflow slice has equivalent proof quality and a truthful non-fixture evaluator path
2. stronger replay-backed proof exists on a shipped externally useful compare scope
3. a later explicitly adopted lane revises this boundary with new evidence

TRAD-V1-064: `trusted_terraform_plan_decision_v1` does not yet satisfy `TRAD-V1-063`. A provider-backed governed proof operator path now exists, but current public authority still lacks admitted successful provider-backed evidence for that scope and its admitted `verdict_deterministic` campaign evidence still comes from the bounded local harness.

TRAD-V1-065: The Terraform publication-readiness gate is:

```text
python scripts/proof/check_trusted_terraform_publication_readiness.py
```

That gate writes `benchmarks/results/proof/trusted_terraform_plan_decision_publication_readiness.json` and MUST report `publication_decision=ready_for_publication_boundary_update` before this contract may admit `trusted_terraform_plan_decision_v1` into the externally publishable public trust slice.

TRAD-V1-066: The Terraform publication-gate sequence is:

```text
python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py
```

That sequence writes `benchmarks/results/proof/trusted_terraform_plan_decision_publication_gate.json`, fails fast on missing required live-provider inputs by default, reruns the prerequisite proof commands only when live preflight passes or `--force-local-evidence` is supplied, preserves the readiness gate result, and MUST report `publication_decision=ready_for_publication_boundary_update` before any same-change authority update may propose Terraform public admission.

TRAD-V1-067: The Terraform publication-gate sequence MUST record live-provider preflight status without recording credential values. Missing required non-secret inputs, including `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`, `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`, and `AWS_REGION` or `AWS_DEFAULT_REGION`, keep Terraform public admission blocked.

TRAD-V1-068: The no-spend Terraform live setup preflight is:

```text
python scripts/proof/check_trusted_terraform_live_setup_preflight.py
```

That preflight writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_preflight.json`, MUST execute zero provider calls, MUST block generated placeholder S3 URIs, and MAY be used before a live attempt to inspect required inputs, planned AWS operations, and least-privilege action hints. A passing setup preflight is not publication evidence by itself.

TRAD-V1-069: The no-spend Terraform live setup packet generator is:

```text
python scripts/proof/prepare_trusted_terraform_live_setup_packet.py
```

That generator writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json` and local setup files under `workspace/trusted_terraform_live_setup/`, MUST execute zero provider calls, MUST NOT write credential values, and MAY be used to prepare the low-cost provider-backed attempt. A generated setup packet is not publication evidence by itself.
