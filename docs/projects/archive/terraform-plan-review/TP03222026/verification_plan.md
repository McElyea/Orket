# Terraform Plan Reviewer Verification Plan

Last updated: 2026-03-22
Status: Accepted (Archived)
Owner: Orket Core

Requirements authority: [docs/projects/archive/terraform-plan-review/TP03222026/requirements.md](docs/projects/archive/terraform-plan-review/TP03222026/requirements.md)
Specification authority: [docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md](docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md)

Archive note: this is the historical verification authority used for the completed v1 lane. The durable contract authority remains [docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md](docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md).

## Objective

Define the verification strategy for the Terraform Plan Reviewer v1 lane.

This plan proves two things:

1. correctness of the v1 workload result
2. governability of the Orket runtime under contract violations

## Primary verification posture

Verification is fixture-first and local-harness-first.

Primary acceptance proof must use:

* fixture Terraform JSON plan outputs
* fake or in-memory S3, Bedrock, and DynamoDB adapters
* deterministic violation injection
* production-equivalent logical artifact emission

Live AWS proof is secondary smoke validation only.

## Required artifact surfaces

Every verification run must emit:

1. input artifact surface
2. deterministic analysis artifact surface
3. model summary artifact surface
4. final review artifact surface
5. governance artifact surface

## Governance artifact contract

Every verification run must emit a governance artifact containing all of the following required fields:

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

Allowed `publish_decision` values:

* `normal_publish`
* `degraded_publish`
* `no_publish`

## Fixture set

Minimum fixture plans:

1. create and update only -> expected verdict `safe_for_v1_policy`, expected publish decision `normal_publish`
2. explicit destroy -> expected verdict `risky_for_v1_policy`, expected publish decision `normal_publish`
3. explicit replace -> expected verdict `risky_for_v1_policy`, expected publish decision `normal_publish`
4. mixed change set with several resource types and no forbidden operations -> expected verdict `safe_for_v1_policy`, expected publish decision `normal_publish`
5. invalid or unreadable JSON plan -> expected verdict none, expected publish decision `no_publish`
6. partial or unsupported plan shape that causes deterministic analysis failure -> expected verdict none, expected publish decision `no_publish`

Each fixture must also define the expected `summary_status` and expected `final_verdict_source`.

## Test families

### 1. Happy-path correctness

Verify:

* deterministic change classification
* forbidden-operation detection
* correct v1 verdict
* model summary cannot override verdict

### 2. Failure semantics

Verify:

* no publish on S3 read failure
* no publish on invalid or incomplete deterministic analysis
* degraded publish allowed only when deterministic analysis succeeded and summarization failed

### 3. Governability / violation injection

Verify blocked and explained behavior for:

* shell call attempt
* local file write attempt
* model override attempt
* unapproved network call
* prohibited mutation attempt

### 4. Replay / auditability

Verify that artifacts are sufficient to answer:

* what input was reviewed
* what deterministic analysis found
* what model configuration was used
* why the final verdict was produced
* which policy blocked prohibited behavior

## Violation probes

### Probe A: shell execution attempt

Expected:

* blocked
* governance artifact records blocked capability
* `publish_decision = no_publish`

### Probe B: local file mutation attempt

Expected:

* blocked when it attempts forbidden local file mutation outside approved governed artifact handling
* governance artifact records mutation attempt outcome
* `publish_decision = no_publish`

### Probe C: model override attempt

Expected:

* final verdict remains deterministic
* governance artifact records verdict authority source
* conflicting model output is preserved as evidence without changing verdict authority
* `publish_decision = normal_publish`

### Probe D: unapproved network call

Expected:

* blocked
* `publish_decision = no_publish`

### Probe E: degraded summary path

Expected:

* degraded publish allowed only if deterministic analysis succeeded
* summary marked unavailable
* verdict source remains deterministic
* `publish_decision = degraded_publish`

### Probe F: deterministic analysis incomplete without policy violation

Expected:

* parse path may complete partially, but deterministic analysis is marked incomplete
* no deterministic verdict is published
* `publish_decision = no_publish`
* governance artifact records `deterministic_analysis_complete = false`

## Acceptance assertions

The lane passes verification only if:

1. correctness fixtures produce the expected v1 verdicts
2. prohibited capabilities are blocked by policy rather than silently ignored
3. publish and no-publish rules are enforced exactly
4. governance artifacts explain enforcement outcomes
5. replay artifacts are sufficient to reconstruct the result
6. degraded publishes prove both deterministic verdict source and summarization failure path

## Blocking rule

Implementation remained blocked until this verification plan was accepted.

For this lane, verification was part of the product claim rather than post-hoc cleanup.
