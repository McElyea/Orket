# Terraform Plan Reviewer V1 Contract Delta

## Summary
- Change title: Terraform plan reviewer v1 durable contract publication and lane closeout
- Owner: Orket Core
- Date: 2026-03-22
- Affected contract(s): `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`

## Delta
- Current behavior: Terraform plan review existed only as a project-lane design and requirements effort, with no durable repo-level contract, no canonical smoke output path, and no completed runtime proof tied to a stable spec.
- Proposed behavior: publish a durable Terraform plan reviewer v1 contract, implement the governed local-first runtime and verification harness, define the canonical live-smoke output path, and archive the completed project lane with closeout evidence.
- Why this break is required now: leaving the Terraform lane as a project-only plan after implementation and proof would weaken contract discoverability and create avoidable drift between runtime behavior, smoke output, archive evidence, and documentation.

## Migration Plan
1. Compatibility window: none; this is additive contract publication plus same-change lane closeout.
2. Migration steps:
   1. publish `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` as the durable contract authority
   2. implement the governed local harness, runtime path, and smoke runner aligned to that contract
   3. archive the Terraform project lane docs under `docs/projects/archive/terraform-plan-review/TP03222026/`
   4. keep the roadmap free of stale active Terraform authority and update durable authority references
3. Validation gates:
   1. targeted Terraform review tests pass
   2. live smoke reports either success or an explicit fail-closed environment blocker
   3. docs project hygiene passes after archive closeout

## Rollback Plan
1. Rollback trigger: runtime proof fails, authority drift remains after archive move, or the durable contract is not supportable by the implemented path.
2. Rollback steps:
   1. restore the Terraform lane to active `docs/projects/` status
   2. restore an active roadmap entry only if the lane must be reopened for additional implementation work
   3. remove or revise the durable contract and smoke-output authority references if the runtime surface is not supportable
3. Data/state recovery notes: the change is documentation-, test-, and runtime-surface-level only; no durable data migration is required.

## Versioning Decision
- Version bump type: additive workload contract publication and same-change archive relocation
- Effective version/date: 2026-03-22
- Downstream impact: Terraform plan review readers should use `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` for the durable contract and `docs/projects/archive/terraform-plan-review/TP03222026/CLOSEOUT.md` for completed-lane proof.
