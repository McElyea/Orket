# Terraform Plan Reviewer v1 Requirements

Last updated: 2026-03-22
Status: Accepted (Archived)
Owner: Orket Core
Design reference: [docs/projects/archive/terraform-plan-review/TP03222026/terraform_plan_reviewer_design.md](docs/projects/archive/terraform-plan-review/TP03222026/terraform_plan_reviewer_design.md)
Specification authority: [docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md](docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md)

Archive note: this is the accepted historical requirements slice used for implementation and closeout. The durable v1 contract authority remains [docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md](docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md).

## Scope

These requirements define the authoritative v1 contract for an Orket workload that reviews a Terraform plan artifact before merge and writes a durable audit result.

This document is the archived requirements slice for v1 behavior. Design rationale, decomposition options, and open design questions live in [docs/projects/archive/terraform-plan-review/TP03222026/terraform_plan_reviewer_design.md](docs/projects/archive/terraform-plan-review/TP03222026/terraform_plan_reviewer_design.md).

## Authoritative input

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

`request_metadata` may include:

* merge request identifier
* repository
* branch
* actor
* request timestamp

## Allowed and forbidden capabilities

The workload may:

* read the Terraform JSON plan object from S3
* invoke one approved Bedrock model for summarization
* write the final audit record to DynamoDB table `TerraformReviews`
* emit runtime observability logs

The workload must not:

* execute shell commands
* invoke Terraform CLI
* mutate local files
* mutate AWS infrastructure
* make network calls outside approved workload adapters
* auto-approve a merge

The only allowed durable mutation in v1 is the DynamoDB audit write.

## Deterministic analysis authority

Deterministic analysis owns:

* Terraform plan parsing
* resource action classification
* forbidden-operation detection
* verdict gating

The model does not own and must not influence:

* detection of forbidden operations
* verdict gating
* override of deterministic findings

Minimum deterministic analysis outputs:

* changed resource count
* actions by class
* resource addresses
* provider and resource-type summary
* explicit forbidden-operation hits
* parse warnings

## Verdict contract

The only v1 verdict values are:

* `safe_for_v1_policy`
* `risky_for_v1_policy`

Verdict rule:

* `risky_for_v1_policy` if any forbidden operation hit exists
* otherwise `safe_for_v1_policy`

Broader semantic concerns such as IAM expansion, public exposure, or unusually high churn are out of scope for deterministic v1 verdicting.

Those concerns may appear in explanatory notes only. They must not change the deterministic verdict.

## Model role

The Bedrock model may:

* explain what is changing
* explain why the deterministic result is policy-safe or policy-risky
* suggest human review focus areas

The Bedrock model must receive:

* compact structured analysis output
* deterministic forbidden-operation hits
* a constrained prompt
* no tool access

The model summary is advisory. It must not override deterministic findings or verdict rules.

The model call must use deterministic configuration with temperature `0`.

## Publish and failure semantics

### No-publish conditions

No review result may be published if deterministic analysis is incomplete or invalid.

No-publish conditions include:

* S3 read failure
* invalid or unreadable JSON plan input
* parse failure severe enough to invalidate deterministic analysis
* policy violation attempt during execution

### Degraded publish conditions

A degraded result may be published only if deterministic analysis succeeded and model summarization failed.

If a degraded result is published, it must:

* derive the verdict purely from deterministic rules
* set summary status to `summary_unavailable`
* preserve deterministic forbidden-operation hits
* clearly indicate degraded publication state

## Verification strategy

This lane has two independent proof obligations:

1. **Correctness proof**
   The workload must produce the correct v1 review result from authoritative input and deterministic policy rules.

2. **Governance proof**
   Orket must block prohibited capabilities, preserve deterministic verdict authority, enforce publish and no-publish rules, and emit enough evidence to explain the enforcement result.

Verification for this lane must be fixture-first, not cloud-first.

The primary acceptance harness must use:

* fixture Terraform JSON plans
* fake or in-memory adapters
* deterministic violation injection
* the same logical artifact surfaces required by production

Live AWS proof is supplementary smoke validation only. It is not the primary acceptance strategy.

Every verification run must emit:

* the logical workload artifacts required by this lane
* a governance artifact recording execution status, publish decision, blocked capabilities, and mutation-attempt outcomes

The lane is not complete unless both proof obligations are satisfied.

## Required audit record

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

## Mandatory persisted evidence

Each execution must preserve, directly or by stable reference:

* input artifact hash
* deterministic analysis artifact hash
* model request configuration
* model response reference when present
* final review artifact hash
* policy bundle id

## Optional observability

Optional runtime observability may include:

* adapter call logs
* CloudWatch execution logs
* trace correlation fields

Optional observability does not replace mandatory persisted evidence.

## Out of scope for v1

v1 does not include:

* merge approval or auto-merge actions
* Terraform apply capability
* local file artifact output as a contract requirement
* non-S3 input sources
* non-DynamoDB durable sinks
* broader semantic risk classes as deterministic verdict inputs
