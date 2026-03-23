# Terraform Plan Reviewer V1

Last updated: 2026-03-22
Status: Active
Owner: Orket Core
Source requirements: [docs/projects/archive/terraform-plan-review/TP03222026/requirements.md](docs/projects/archive/terraform-plan-review/TP03222026/requirements.md)
Verification authority: [docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md](docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md)
Implementation closeout authority: [docs/projects/archive/terraform-plan-review/TP03222026/CLOSEOUT.md](docs/projects/archive/terraform-plan-review/TP03222026/CLOSEOUT.md)

## 1. Purpose

Define the active v1 contract for an Orket workload that reviews a Terraform plan artifact before merge, produces a policy-bounded review result, and proves governability through required artifacts and enforcement behavior.

## 2. Authoritative Input Contract

The only authoritative v1 input format is Terraform JSON plan output stored in S3.

v1 does not accept:

* raw Terraform binary plan files
* normalized text summaries as authoritative input
* any input that depends on runtime shell conversion

Required input fields:

* `plan_s3_uri`
* `forbidden_operations`

Optional input fields:

* `request_metadata`

## 3. Capability Contract

Allowed capabilities:

* read Terraform JSON plan object from S3
* invoke one approved Bedrock model for summarization
* write the final audit record to DynamoDB table `TerraformReviews`
* emit runtime observability logs

Forbidden capabilities:

* shell execution
* Terraform CLI invocation
* local file mutation outside approved governed artifact handling
* AWS infrastructure mutation
* network calls outside approved workload adapters
* merge approval or auto-merge actions

The only allowed durable mutation in v1 is the DynamoDB audit write.

## 4. Deterministic Authority Contract

Deterministic analysis owns:

* Terraform plan parsing
* resource action classification
* forbidden-operation detection
* verdict gating

The model is advisory only. It must not override deterministic findings or verdict rules.

Minimum deterministic outputs:

* changed resource count
* actions by class
* resource addresses
* provider and resource-type summary
* explicit forbidden-operation hits
* parse warnings

## 5. Verdict Contract

Allowed verdict values:

* `safe_for_v1_policy`
* `risky_for_v1_policy`

Verdict rule:

* `risky_for_v1_policy` if any forbidden operation hit exists
* otherwise `safe_for_v1_policy`

Broader semantic concerns may appear in explanatory notes only. They must not change the deterministic verdict.

## 6. Publish and Failure Contract

Allowed `publish_decision` values:

* `normal_publish`
* `degraded_publish`
* `no_publish`

No review result may be published if deterministic analysis is incomplete or invalid.

No-publish conditions include:

* S3 read failure
* invalid or unreadable JSON plan input
* parse failure severe enough to invalidate deterministic analysis
* policy violation attempt during execution

A degraded result may be published only if deterministic analysis succeeded and model summarization failed.

Degraded publication requires:

* verdict derived purely from deterministic rules
* `summary_status = summary_unavailable`
* deterministic forbidden-operation hits preserved
* degraded publication state recorded in artifacts

## 7. Required Audit Record

The final audit record must include:

* `plan_hash`
* `plan_s3_uri` or stable input reference
* `risk_verdict`
* `forbidden_operation_hits`
* `resource_change_summary`
* `model_id`
* `summary`
* `summary_status`
* `policy_bundle_id`
* `execution_trace_ref`
* `created_at`

If summarization is unavailable, `summary` may be empty only when `summary_status` is `summary_unavailable`.

## 8. Required Governance Artifact

Every verification run must emit a governance artifact containing all required fields:

* `execution_status`
* `publish_decision`
* `policy_violation_type`
* `blocked_capability`
* `durable_mutations_attempted`
* `durable_mutations_allowed`
* `adapter_calls_attempted`
* `adapter_calls_blocked`
* `deterministic_analysis_complete`
* `summary_status`
* `final_verdict_source`
* `policy_bundle_id`
* `execution_trace_ref`

## 9. Mandatory Persisted Evidence

Each execution must preserve, directly or by stable reference:

* input artifact hash
* deterministic analysis artifact hash
* model request configuration
* model response reference when present
* final review artifact hash
* policy bundle id

## 10. Verification Gate

This lane has two independent proof obligations:

1. correctness proof
2. governance proof

The lane is not complete unless both proof obligations are satisfied according to [docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md](docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md).
