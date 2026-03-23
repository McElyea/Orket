# Orket Terraform Plan Reviewer Design

Last updated: 2026-03-22
Status: Archived Design Draft
Owner: Orket Core
Source prompt: Edgescale Question 2

Archive note: this design draft is retained as historical rationale only. The durable v1 contract lives in [docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md](docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md).

## Objective

Design an Orket-native workload that reviews a Terraform plan before merge, explains what will change, flags policy-sensitive operations, and writes a durable audit record, while guaranteeing that the workload cannot apply infrastructure, modify files, or execute shell commands.

## Why this is a strong Orket fit

This workload is a good fit for Orket because it is:

* bounded
* safety-sensitive
* artifact-oriented
* auditable
* naturally split between deterministic analysis and model interpretation

The model should not be the source of truth for forbidden-operation detection. Orket should do deterministic extraction and policy checks first, then use the model for explanation and summarization.

## Product framing

This is not "an agent with AWS access."

This is a governed review workload with:

* one authoritative input artifact
* a fixed read-only tool surface for analysis
* deterministic pre-model analysis
* one bounded model call
* one durable audit artifact

## Design posture

This document is design guidance, not requirements authority.

It captures rationale, decomposition, and open questions that supported contract extraction. The accepted historical requirements slice for this lane lives in [docs/projects/archive/terraform-plan-review/TP03222026/requirements.md](docs/projects/archive/terraform-plan-review/TP03222026/requirements.md).

## Workload shape

### Input surface

The workload is expected to accept:

* a Terraform plan artifact reference in S3
* a configured policy bundle for forbidden operation classes
* optional request metadata such as merge request, repo, branch, actor, and timestamp

### Output surface

The workload is expected to produce a governed review artifact containing at minimum:

* plan hash
* model id
* summary
* policy verdict
* forbidden operation hits
* resource change summary
* confidence notes
* input reference
* created timestamp
* policy bundle id
* execution trace reference

### Allowed mutation

The intended v1 mutation surface is narrow:

* write the final review artifact to DynamoDB table `TerraformReviews`

No other mutation should be part of the v1 contract.

## Non-goals

This workload must not:

* run `terraform apply`
* modify the plan file
* modify local files
* invoke shell tools
* mutate AWS infrastructure
* auto-approve a merge

## Execution model

### Stage 1: fetch authoritative input

Read the Terraform plan artifact from S3 using a read-only adapter.

Design outputs:

* source reference
* content hash
* content size
* parsed or normalized representation suitable for deterministic analysis

If the plan cannot be read, fail with a bounded read error and produce no safe review result.

### Stage 2: deterministic plan analysis

Before invoking the model, Orket performs deterministic extraction.

Design outputs:

* changed resource count
* actions by class
* resource addresses
* provider and resource-type summary
* explicit forbidden-operation hits
* parse warnings or unsupported sections

This stage is authoritative for forbidden-operation detection.

### Stage 3: bounded model summarization

Invoke Bedrock with a deterministic configuration to explain:

* what is changing
* why the change set is policy-safe or policy-risky
* what the main human-review focus areas are

The model receives:

* a compact structured change summary
* the forbidden-operation hits from deterministic analysis
* a constrained instruction prompt
* no tool access

The model does not receive authority to determine whether forbidden operations exist. It may only explain deterministic findings and summarize the change set.

### Stage 4: verdict assembly

Orket assembles the final review artifact.

The model summary cannot override deterministic verdict rules.

### Stage 5: audit persistence

Write the final review artifact to DynamoDB `TerraformReviews`.

## Policy model

### Allowed capabilities

* read object from S3
* invoke Bedrock model
* write audit artifact to DynamoDB
* emit CloudWatch logs for workload observability

### Forbidden capabilities

* shell execution
* file mutation
* Terraform CLI invocation
* network calls outside approved AWS adapters
* infrastructure mutation APIs

### Tool surface

The workload should expose only explicit adapters:

* `read_s3_object`
* `invoke_bedrock_model`
* `put_dynamodb_item`
* optional `write_observability_log`

No raw AWS SDK escape hatch should be given to the model step.

## Suggested Orket workload decomposition

### Workload A: `terraform_plan_fetch`

Purpose:

* fetch plan from S3
* compute hash
* emit a normalized input surface for downstream analysis

### Workload B: `terraform_plan_analyzer`

Purpose:

* parse plan deterministically
* classify resource actions
* detect forbidden operations
* emit structured analysis output

### Workload C: `terraform_plan_summarizer`

Purpose:

* call Bedrock using the structured analysis output
* produce human-readable summary and review notes

### Workload D: `terraform_review_publisher`

Purpose:

* assemble final verdict artifact
* persist to DynamoDB

These may run inside one parent workload if desired, but the artifact boundaries should still exist.

## Logical artifact surfaces

These are logical runtime artifacts. They are not a requirement to write arbitrary local files.

They may be persisted through Orket's governed artifact store, embedded in durable records, or referenced from the execution trace.

### Input artifact surface

Representative fields:

* `plan_s3_uri`
* `plan_hash`
* `size_bytes`
* `fetched_at`
* `content_type`
* `parse_mode`

### Analysis artifact surface

Representative fields:

* `resource_changes`
* `action_counts`
* `forbidden_operation_hits`
* `warnings`
* `analysis_confidence`

### Model summary artifact surface

Representative fields:

* `model_id`
* `temperature`
* `summary`
* `review_focus_areas`
* `raw_completion_ref`

### Final review artifact surface

Representative fields:

* `plan_hash`
* `risk_verdict`
* `summary`
* `forbidden_operation_hits`
* `resource_change_summary`
* `model_id`
* `policy_bundle_id`
* `execution_trace_ref`
* `stored_in_dynamodb`

## Data model for DynamoDB

### Table: `TerraformReviews`

Suggested keys:

* partition key: `plan_hash`
* sort key: `created_at`

Suggested attributes:

* `plan_hash`
* `created_at`
* `risk_verdict`
* `model_id`
* `summary`
* `forbidden_operation_hits`
* `plan_s3_uri`
* `repo`
* `branch`
* `actor`
* `policy_bundle_id`
* `execution_trace_ref`

Open design considerations:

* whether retrieval is primarily by plan hash, merge request, or repository context
* retention expectations for audit history and raw model references
* whether secondary indexes are needed for reviewer lookup flows

## Failure behavior

### Fail closed on incomplete deterministic analysis

If any of the following occur, the workload must fail closed and avoid publishing a misleading safe result:

* S3 read failure
* plan parse failure severe enough to invalidate deterministic analysis
* policy violation attempt

### Degraded summary behavior

If deterministic analysis succeeds but model summarization fails, the workload may emit a degraded artifact only if:

* the verdict is derived purely from deterministic rules
* the summary is marked unavailable
* the result is clearly identified as degraded

This still requires an explicit requirements decision before implementation.

## Evidence and observability

### Mandatory persisted evidence

Each run should preserve, either directly or by stable reference:

* input artifact hash
* analysis artifact hash
* model request configuration
* model response reference
* final review artifact hash
* policy bundle id

### Optional observability

Runtime observability may additionally capture:

* adapter call logs
* CloudWatch execution logs
* trace correlation fields for debugging

A reviewer should be able to answer:

* which plan was reviewed
* why the verdict was policy-safe or policy-risky
* whether the model summary was consistent with deterministic findings
* which policy prevented mutation paths

## Determinism posture

The model call should run with temperature 0.

Deterministic analysis should be the primary truth surface for:

* change classification
* forbidden-operation detection
* verdict gating

The model should only interpret and explain.

## Security posture

This workload should run with least privilege:

* S3 read on the input bucket or object prefix only
* DynamoDB write on `TerraformReviews` only
* Bedrock invoke on the single approved model only
* CloudWatch write only if needed for runtime logs

## Open design questions

1. What exact reviewer lookup and retention patterns should drive the DynamoDB table and index design?
2. Should parse failure produce only hard failure, or a deterministic degraded artifact that is always policy-risky?
3. Should the audit record include the full summary text, or a bounded summary plus artifact reference?
4. What exact confidence or warning surface should be exposed when parsing is partial?
5. Should the review artifact include a recommended reviewer action such as `manual_review_required`?

## Recommended next step

Keep the implementation lane narrow:

* single authoritative input shape in requirements
* single output sink: DynamoDB
* single approved model
* deterministic verdict rule
* no merge integration yet
* no CLI dependency

That gives Orket a governed workload shape that directly answers the interview problem while staying consistent with artifact-native, policy-compiled execution.
