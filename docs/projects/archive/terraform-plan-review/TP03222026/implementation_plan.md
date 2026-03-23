# Terraform Plan Reviewer V1 Implementation Plan

Last updated: 2026-03-22
Status: Completed (Archived)
Owner: Orket Core
Contract authority: [docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md](docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md)
Requirements slice: [docs/projects/archive/terraform-plan-review/TP03222026/requirements.md](docs/projects/archive/terraform-plan-review/TP03222026/requirements.md)
Verification authority: [docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md](docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md)
Design reference: [docs/projects/archive/terraform-plan-review/TP03222026/terraform_plan_reviewer_design.md](docs/projects/archive/terraform-plan-review/TP03222026/terraform_plan_reviewer_design.md)
Closeout: [docs/projects/archive/terraform-plan-review/TP03222026/CLOSEOUT.md](docs/projects/archive/terraform-plan-review/TP03222026/CLOSEOUT.md)

## 1. Objective

This archived plan records the Terraform Plan Reviewer v1 implementation that was executed to completion, with local governed proof completed before the live AWS smoke route was evaluated.

Non-negotiable implementation truths:

1. Authoritative input remains Terraform JSON plan output in S3 only.
2. Deterministic analysis remains the sole authority for forbidden-operation detection and verdict gating.
3. The model remains explanation-only and cannot override deterministic verdicts.
4. The only allowed durable mutation remains the DynamoDB audit write.
5. Publish and no-publish behavior must be artifact-proven, not inferred from logs.
6. Verification remains fixture-first, local-harness-first, and cloud-second.

## 2. Scope Deliverables

This implementation lane must produce:

1. fixture corpus with locked expected outcomes
2. fake S3, Bedrock, and DynamoDB adapters plus violation injectors
3. governance artifact schema and artifact emission plumbing
4. acceptance harness covering the explicit fixtures and probes
5. thin live AWS smoke layer after local governed proof passes

## 3. Sequenced Execution Plan

Implementation proceeds in five bounded slices.

### IMP-00 - Fixture Corpus and Expected Outcomes

Deliver:

1. canonical Terraform JSON plan fixtures for the six required cases in [docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md](docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md)
2. expected deterministic analysis outputs for each fixture
3. expected verdict, `publish_decision`, `summary_status`, and `final_verdict_source` for each fixture
4. fixture metadata sufficient to drive the acceptance harness without hidden assumptions

Acceptance:

1. every fixture has an explicit expected verdict or explicit no-verdict outcome
2. every fixture has an explicit expected `publish_decision`
3. every fixture has an explicit expected `summary_status` and expected `final_verdict_source`
4. fixture definitions are stable enough to act as the local acceptance baseline

### IMP-01 - Fake Adapter Pack and Violation Injectors

Deliver:

1. fake S3 adapter for authoritative plan retrieval
2. fake Bedrock adapter for bounded summary success and forced failure modes
3. fake DynamoDB adapter for publish capture and no-publish assertions
4. violation injectors for shell execution, local file mutation, unapproved network calls, and prohibited mutation attempts

Blocked capability attempts must be represented as policy-enforced outcomes in artifacts rather than surfacing only as adapter exceptions.

Acceptance:

1. adapters can drive the workload through success, blocked, degraded, and no-publish paths deterministically
2. violation injectors can trigger each explicit probe without relying on live infrastructure
3. blocked capability attempts are recorded as policy enforcement outcomes, not only incidental adapter errors
4. fake adapters expose enough state to verify attempted and blocked calls truthfully

### IMP-02 - Governance Artifact Schema and Emission Plumbing

Deliver:

1. concrete governance artifact schema implementing the required fields from [docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md](docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md)
2. workload plumbing that emits input, deterministic analysis, model summary, final review, and governance artifacts for every verification run
3. deterministic recording of `publish_decision`, `summary_status`, `final_verdict_source`, and mutation-attempt outcomes

Acceptance:

1. every verification path emits the full required artifact set
2. governance artifacts are sufficient to explain blocked, degraded, and normal publish results
3. degraded publication paths preserve deterministic verdict source and summarization failure evidence

### IMP-03 - Acceptance Harness for Fixtures and Probes

Deliver:

1. acceptance harness that runs the fixture corpus through the fake adapter pack
2. acceptance tests for the happy-path fixtures
3. acceptance tests for failure semantics
4. acceptance tests for probes A-F from [docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md](docs/projects/archive/terraform-plan-review/TP03222026/verification_plan.md)

Acceptance:

1. correctness fixtures produce the expected v1 verdicts exactly
2. publish and no-publish decisions match the contract exactly
3. prohibited capabilities are blocked by policy rather than silently ignored
4. conflicting model output is preserved as evidence without affecting verdict authority
5. replay artifacts are sufficient to reconstruct both normal and degraded outcomes

### IMP-04 - Thin Live AWS Smoke Layer

Deliver:

1. minimal live smoke path using real AWS adapters after local governed proof passes
2. curated fixture subset limited to the minimum cases needed to prove authoritative S3 read, bounded Bedrock invoke, DynamoDB audit write, and fail-closed blocker reporting
3. proof that the curated smoke subset executes through the intended runtime path without widening the local acceptance matrix
4. smoke runner path `scripts/reviewrun/run_terraform_plan_review_live_smoke.py` with canonical output path `.orket/durable/observability/terraform_plan_review_live_smoke.json`

Acceptance:

1. live smoke remains supplementary to the local governed harness
2. live smoke uses the same contract and artifact vocabulary as the local harness
3. live smoke does not expand into a second acceptance matrix beyond the curated subset
4. environment blockers or unavailable credentials fail closed and are reported explicitly

## 4. Workstream Detail

### Workstream A - Fixture and Expected-Outcome Authority

Tasks:

1. define the fixture corpus layout and naming
2. encode expected deterministic outputs, verdicts, publish decisions, summary statuses, and verdict sources beside each fixture
3. include failure fixtures for invalid JSON and incomplete deterministic analysis

Acceptance Criteria:

1. the fixture corpus is the single local truth source for acceptance harness inputs
2. expected outcomes do not depend on model text or manual reviewer interpretation

### Workstream B - Governed Fake Runtime Surface

Tasks:

1. implement fake adapters matching the workload contract seam
2. implement explicit violation injectors for prohibited capabilities
3. ensure blocked attempts are captured in governance artifacts rather than lost in incidental exceptions

Blocked capability attempts must be classified as policy-enforced outcomes rather than treated as raw adapter failure alone.

Acceptance Criteria:

1. no violation probe requires live AWS or shell access
2. blocked capability paths are distinguishable from ordinary runtime failure

### Workstream C - Artifact and Schema Plumbing

Tasks:

1. define the governance artifact shape in code
2. wire artifact emission for all execution paths
3. ensure no-publish and degraded publish are represented explicitly rather than inferred later

Acceptance Criteria:

1. artifacts are replayable for equivalent inputs
2. governance artifacts answer why a publish was allowed, degraded, or blocked

### Workstream D - Acceptance Harness

Tasks:

1. create a local harness that executes the workload against the fixture corpus
2. add tests for correctness, failure semantics, violation injection, and replay sufficiency
3. label tests by layer: `unit`, `contract`, `integration`, or `end-to-end`

Acceptance Criteria:

1. the harness fails closed on contract mismatches
2. acceptance tests prove both correctness and governability claims

### Workstream E - Live Smoke Follow-Through

Tasks:

1. add the thinnest practical live AWS smoke route after local harness proof is green
2. limit live smoke to the minimum curated fixture subset needed to prove S3 read, Bedrock invoke, DynamoDB write, and fail-closed blocker reporting
3. capture exact path classification and result classification
4. record blockers explicitly if live proof cannot run

Acceptance Criteria:

1. live smoke is not treated as the primary proof layer
2. the lane can report `primary`, `degraded`, or `blocked` truthfully for live proof status

## 5. Verification Plan

Required proof layers:

1. `contract` tests for governance artifact schema, publish-decision enums, and verdict-contract surfaces
2. `unit` tests for deterministic analysis helpers and publish-decision logic
3. `integration` tests for the local governed harness with fake adapters and explicit probes
4. `end-to-end` smoke proof for the thin live AWS path after local proof passes

Required evidence recording:

1. observed path classification: `primary`, `fallback`, `degraded`, or `blocked`
2. observed result classification: `success`, `failure`, `partial success`, or `environment blocker`
3. exact failing step and exact error when blocked

Required classification mapping:

1. `publish_decision = normal_publish` maps to observed path classification `primary` and observed result classification `success`
2. `publish_decision = degraded_publish` maps to observed path classification `degraded` and observed result classification `partial success`
3. `publish_decision = no_publish` caused by deterministic incompleteness or policy enforcement maps to observed path classification `blocked` and observed result classification `failure`
4. `publish_decision = no_publish` caused by an external prerequisite that prevents attempted proof maps to observed path classification `blocked` and observed result classification `environment blocker`

## 6. Completion Gate

This lane is complete only when:

1. IMP-00 through IMP-03 acceptance criteria are met locally
2. governance artifacts prove blocked capabilities, deterministic verdict authority, and publish/no-publish enforcement
3. replay artifacts are sufficient for normal, degraded, and blocked verification paths
4. IMP-04 smoke proof either succeeds or reports an explicit environment blocker without claiming false success
5. the roadmap remains consistent with lane completion and does not retain stale active-lane authority
