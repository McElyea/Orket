# Contract Delta: Trusted Terraform Live Setup Preflight

## Summary
- Change title: Add no-spend live setup preflight for Terraform governed proof
- Owner: Orket Core
- Date: 2026-04-19
- Affected contract(s): `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: operators can see missing live inputs only through the publication gate or runtime smoke blocker.
- Proposed behavior: add `python scripts/proof/check_trusted_terraform_live_setup_preflight.py` as a no-spend setup preflight that writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_preflight.json`, executes zero provider calls, and records planned AWS operations plus least-privilege action hints.
- Why this break is required now: the next live attempt should be deliberate and low-cost; operators need a setup check that does not invoke Bedrock, S3, or DynamoDB.

## Migration Plan
1. Compatibility window: immediate; no live proof command behavior changes.
2. Migration steps:
   1. add the no-spend preflight script and tests,
   2. document required inputs, planned provider calls, and IAM action hints,
   3. update current authority and governed-proof lane docs.
3. Validation gates:
   1. `python -m pytest -q tests/scripts/test_check_trusted_terraform_live_setup_preflight.py`
   2. `python scripts/proof/check_trusted_terraform_live_setup_preflight.py`
   3. `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: the setup preflight drifts from the actual runtime smoke call plan.
2. Rollback steps:
   1. remove the preflight script and tests,
   2. remove preflight references from current authority and affected specs,
   3. keep the runtime smoke and publication gate as the only live readiness surfaces.
3. Data/state recovery notes: no runtime data migration is involved; the preflight artifact is rerunnable proof output only.

## Versioning Decision
- Version bump type: operator-surface addition with no public-claim widening
- Effective version/date: 2026-04-19
- Downstream impact: live Terraform governed-proof attempts should run the no-spend preflight before provider-backed execution.
