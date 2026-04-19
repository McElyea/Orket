# Contract Delta: Trusted Terraform Plan Decision v1

## Summary
- Change title: Trusted Terraform plan decision v1 durable contract publication
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: the governed-proof lane had only a lane-local recommendation that Terraform plan decision was the leading first non-fixture candidate, with no durable `docs/specs/` scope contract and no truthful evaluator guide distinguishing selected-next status from admitted trust status.
- Proposed behavior: publish a durable chosen-scope contract and evaluator guide for `trusted_terraform_plan_decision_v1`, keep it explicitly non-admitted and non-public, reserve its future proof surfaces without activating them, and record that Workstream 2 selection in current authority.
- Why this break is required now: Workstream 2 requires an explicit chosen scope with durable authority before implementation claims are made, and the repo needs one truthful place that says Terraform plan decision is selected next without implying that its governed-proof wrapper already exists.

## Migration Plan
1. Compatibility window: immediate; no runtime compatibility surface changes because the chosen scope is not yet implemented.
2. Migration steps:
   1. publish `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`,
   2. publish `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`,
   3. update the governed-proof lane docs to record the explicit Workstream 2 selection,
   4. update `CURRENT_AUTHORITY.md` to mark the chosen scope as selected next rather than admitted.
3. Validation gates:
   1. docs review must confirm the scope is not added to admitted compare scopes,
   2. docs review must confirm no public trust wording broadens,
   3. docs hygiene must pass.

## Rollback Plan
1. Rollback trigger: the chosen scope no longer appears to be the best first non-fixture candidate, or the contract extraction is found to overstate admission or proof status.
2. Rollback steps:
   1. remove or retire `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`,
   2. remove or retire the paired guide,
   3. revert the Workstream 2 selection wording in current authority and the governed-proof lane docs.
3. Data/state recovery notes: no runtime state or durable data migration is required because this change is documentation authority only.

## Versioning Decision
- Version bump type: new durable contract publication
- Effective version/date: `v1`, 2026-04-18
- Downstream impact: the governed-proof lane now has one durable chosen-scope contract for Workstream 2, but runtime proof, admission, and public trust publication remain unchanged.
