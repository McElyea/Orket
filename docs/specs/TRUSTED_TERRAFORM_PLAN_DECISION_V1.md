# Trusted Terraform Plan Decision v1

Last updated: 2026-04-19
Status: Active internal admitted compare-scope contract
Owner: Orket Core

Implementation lane: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`
Evaluator guide: `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`
Reusable runtime authority: `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`

## Purpose

Define the durable contract family for the first non-fixture trusted change scope admitted by the governed-proof lane.

The selected scope is one policy-bounded Terraform plan review decision over one authoritative Terraform JSON plan input.

## Boundary

This spec admits and bounds one internal governed-proof compare scope.

It does not:
1. admit a new compare scope into the current externally publishable public trust slice,
2. replace `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` as the runtime contract for the existing Terraform plan reviewer workload, or
3. broaden public trust wording beyond the current `trusted_repo_config_change_v1` slice.

## Scope Identity

The durable identity for this scope family is:

1. compare scope: `trusted_terraform_plan_decision_v1`
2. operator surface: `trusted_run_witness_report.v1`
3. witness bundle schema: `trusted_run.witness_bundle.v1`
4. contract verdict surface: `trusted_terraform_plan_decision_contract_verdict.v1`
5. validator surface: `trusted_terraform_plan_decision_validator.v1`
6. offline claim surface: `offline_trusted_run_verifier.v1`
7. single-run fallback claim tier: `non_deterministic_lab_only`
8. current campaign claim ceiling: `verdict_deterministic`
9. current publication status: internal admitted only, not externally publishable

## Relationship To Terraform Plan Reviewer v1

This scope intentionally reuses the existing Terraform reviewer contract rather than relabeling it.

It must preserve, at minimum, the following Terraform reviewer truth:

1. authoritative input remains Terraform JSON plan output stored in S3,
2. forbidden capabilities still include shell execution, Terraform CLI invocation, infrastructure mutation, and merge or auto-merge actions,
3. deterministic analysis still owns plan parsing, resource action classification, forbidden-operation detection, and verdict gating,
4. allowed reviewer verdicts remain `safe_for_v1_policy` and `risky_for_v1_policy`, and
5. allowed publication outcomes remain `normal_publish`, `degraded_publish`, and `no_publish`.

The governed-proof layer adds trusted-run witness, invariant, substrate, and offline-claim packaging around that bounded decision surface. It does not rename the Terraform reviewer outcome vocabulary.

## Bounded Effect Surface

The bounded effect for this scope is:

1. read one authoritative Terraform JSON plan input,
2. compute one deterministic policy verdict over that plan,
3. optionally attach advisory summary text that cannot override the deterministic verdict, and
4. publish exactly one bounded review decision record plus governed proof artifacts.

This scope is decision publication only. It is not a Terraform apply, rollout, merge, or infrastructure mutation scope.

## Allowed Mutation Boundary

The allowed durable mutations for this scope are limited to:

1. one bounded review decision publication consistent with `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`,
2. one bounded audit publication for that same decision, and
3. governed-proof witness and verifier artifacts for that same decision.

It must not:

1. mutate infrastructure,
2. mutate arbitrary repository files,
3. invoke Terraform CLI,
4. widen network capabilities beyond the existing Terraform reviewer contract, or
5. convert reviewer success into merge authority or auto-approval authority.

## Required Authority Families

A success-shaped governed proof for this scope must carry or reference all of the following:

1. governed input naming the plan input reference and forbidden-operation policy,
2. policy snapshot and configuration snapshot for the governed run,
3. run and current-attempt authority for the decision execution,
4. deterministic plan-analysis artifact proving the bounded verdict basis,
5. review decision artifact preserving `risk_verdict`, `publish_decision`, `summary_status`, and `final_verdict_source`,
6. bounded audit publication evidence when `publish_decision` is not `no_publish`,
7. final-truth authority for the governed decision result,
8. witness bundle, invariant model, substrate model, and verifier report, and
9. offline claim-evaluator output for the selected claim tier.

## Deterministic Validator Surface

`trusted_terraform_plan_decision_validator.v1` is the active validator surface for the governed-proof wrapper of this scope.

That validator must mechanically confirm, at minimum:

1. the plan input is readable and valid JSON,
2. deterministic action classification completed,
3. forbidden-operation hits are preserved exactly,
4. `risk_verdict` matches the deterministic forbidden-operation rule,
5. `publish_decision` does not claim publication when deterministic analysis is incomplete,
6. model summary output does not override deterministic verdict truth, and
7. the bounded audit publication, when present, agrees with the published decision.

## Must-Catch Corruption Set

The minimum corruption set for this scope is:

1. invalid or unreadable Terraform JSON input,
2. forbidden-operation hits removed or contradicted,
3. `risk_verdict` drift from deterministic analysis,
4. `publish_decision=normal_publish` or `degraded_publish` when deterministic analysis is incomplete,
5. audit publication claimed when `publish_decision=no_publish`,
6. undeclared durable mutation outside the bounded audit and proof artifacts,
7. compare-scope drift or operator-surface drift, and
8. final-truth omission or contradiction.

## Active Implementation Surfaces

The following canonical surfaces are active current authority for this scope:

1. live proof command: `python scripts/proof/run_trusted_terraform_plan_decision.py`
2. campaign proof command: `python scripts/proof/run_trusted_terraform_plan_decision_campaign.py`
3. runtime-backed governed proof command: `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json`
4. offline verifier command: `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json`
5. live setup packet command: `python scripts/proof/prepare_trusted_terraform_live_setup_packet.py`
6. live setup preflight command: `python scripts/proof/check_trusted_terraform_live_setup_preflight.py`
7. publication readiness command: `python scripts/proof/check_trusted_terraform_publication_readiness.py`
8. publication gate sequence command: `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py`
9. live proof output path: `benchmarks/results/proof/trusted_terraform_plan_decision_live_run.json`
10. runtime-backed governed proof output path: `benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json`
11. live setup packet output path: `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json`
12. live setup packet root: `workspace/trusted_terraform_live_setup/`
13. live setup preflight output path: `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_preflight.json`
14. validator output path: `benchmarks/results/proof/trusted_terraform_plan_decision_validator.json`
15. campaign output path: `benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json`
16. offline verifier output path: `benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json`
17. publication readiness output path: `benchmarks/results/proof/trusted_terraform_plan_decision_publication_readiness.json`
18. publication gate sequence output path: `benchmarks/results/proof/trusted_terraform_plan_decision_publication_gate.json`
19. witness bundle root: `workspace/trusted_terraform_plan_decision/runs/<session_id>/trusted_run_witness_bundle.json`

## Evaluator Path

The truthful current evaluator path for this admitted internal-only scope is the guide at `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`.

That guide must remain explicit that:

1. this scope is admitted internally only and is not yet part of the current externally publishable public trust slice,
2. the governed-proof witness campaign and offline claim surfaces now exist for this compare scope, and
3. a provider-backed governed-proof operator path now exists for this compare scope, but
4. existing Terraform reviewer proof remains related reusable runtime authority rather than the same thing as the governed-proof publication boundary.

## Current Proof Limitations

The current proof limitations for this scope are:

1. the admitted `verdict_deterministic` campaign evidence for this scope still comes from the bounded local harness over the Terraform reviewer contract,
2. the live setup packet and live setup preflight are preparation surfaces only and do not create provider-backed proof evidence,
3. the provider-backed governed proof command may fail closed as an environment blocker when required AWS inputs are absent,
4. `scripts/reviewrun/run_terraform_plan_review_live_smoke.py` remains the separate provider-backed runtime smoke seam for `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`,
5. `python scripts/proof/check_trusted_terraform_publication_readiness.py` must block publication readiness while provider-backed governed-proof evidence is missing or environment-blocked,
6. `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` must fail fast at live-environment preflight by default when required provider inputs are missing, may rerun local evidence under `--force-local-evidence`, and must preserve blocked readiness in the aggregate gate output, and
7. public trust/publication remains blocked until successful provider-backed governed-proof evidence is admitted under the trust/publication authority.

## Provider-Backed Proof Inputs

The provider-backed governed-proof path requires live environment inputs. These inputs are prerequisites for successful publication readiness, not proof by themselves.

Before provisioning any live resources, generate the local setup packet:

```text
python scripts/proof/prepare_trusted_terraform_live_setup_packet.py
```

That packet writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json` and local setup files under `workspace/trusted_terraform_live_setup/`. It MUST execute zero provider calls, MUST NOT write credential values, and is not publication evidence by itself.

Before attempting provider-backed proof, run:

```text
python scripts/proof/check_trusted_terraform_live_setup_preflight.py
```

That preflight is no-spend and MUST NOT call AWS. It validates local configuration shape, blocks generated placeholder S3 URIs, records planned provider calls, and writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_preflight.json`.

Required:

1. `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`: S3 URI for the authoritative Terraform JSON plan input.
2. `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`: Bedrock model or inference-profile id for the advisory summary path.
3. `AWS_REGION` or `AWS_DEFAULT_REGION`: AWS region for S3, Bedrock Runtime, and DynamoDB clients.
4. valid AWS credentials from the standard AWS provider chain.

Optional:

1. `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE`: DynamoDB audit table name; defaults to `TerraformReviews`.
2. `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_CREATED_AT`: fixed request timestamp for reproducible smoke input.
3. `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TRACE_REF`: execution trace ref.
4. `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_POLICY_BUNDLE_ID`: policy bundle id; defaults to `terraform_plan_reviewer_v1`.

The current setup packet defaults `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID` to `us.amazon.nova-lite-v1:0` so the low-cost provider-backed attempt stays portable in the AWS Regions where Bedrock requires a cross-Region inference profile instead of a direct on-demand Nova foundation-model id. The live summary seam currently admits direct `anthropic.*` model ids plus Anthropic inference-profile ids (`us.anthropic.*`, `global.anthropic.*`, or matching inference-profile ARNs) through `InvokeModel`, and direct `amazon.nova-*` model ids plus Nova inference-profile ids (`us.amazon.nova-*`, `global.amazon.nova-*`, or matching inference-profile ARNs) through `Converse`. Unsupported model ids MUST fail closed in no-spend preflight and setup-packet readiness before provider calls are attempted.

The publication gate sequence records missing required non-secret environment names in `live_environment_preflight` and fails fast before rerunning local proof steps when those inputs are absent. Operators MAY pass `--force-local-evidence` to regenerate local proof artifacts while keeping publication blocked. The gate MUST NOT record AWS credential values.

## Forbidden Claims

This scope must not currently claim:

1. that this scope is already part of the externally publishable public trust slice,
2. replay determinism,
3. text determinism,
4. Terraform apply safety or infrastructure correctness in general, or
5. general trust for arbitrary IaC workflows.

## Publication Rule

Although `trusted_terraform_plan_decision_v1` is now an admitted internal governed-proof compare scope, it may join the externally publishable public trust slice only when all of the following are true:

1. the live proof, validator, campaign, offline-claim, and corruption proof surfaces above remain passing truthfully,
2. scope-local public wording is supported by the admitted evidence rather than by the Terraform reviewer runtime contract alone,
3. the runtime-backed governed proof path produces successful admitted evidence rather than only an environment-blocked or local-harness-only path,
4. `python scripts/proof/check_trusted_terraform_publication_readiness.py` reports `publication_decision=ready_for_publication_boundary_update`,
5. `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` reports `publication_decision=ready_for_publication_boundary_update`,
6. `CURRENT_AUTHORITY.md` and `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` are updated in the same change, and
7. any broader wording still stops at the actual claim ceiling permitted by the offline verifier.
