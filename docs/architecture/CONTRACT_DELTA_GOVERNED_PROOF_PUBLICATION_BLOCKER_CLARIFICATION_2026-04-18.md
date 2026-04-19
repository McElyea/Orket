# Contract Delta: Governed Proof Publication Blocker Clarification

## Summary
- Change title: Clarify why Terraform governed-proof evidence does not yet widen the external/public trust slice
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: the governed-proof lane now has an admitted Terraform compare scope with a passing witness campaign, but the publication boundary does not explicitly say why that scope still fails public admission.
- Proposed behavior: keep the public trust slice unchanged and make the blocker explicit: the current Terraform governed-proof evaluator path is still a bounded local harness over the Terraform reviewer contract, while the provider-backed runtime smoke seam remains separate.
- Why this break is required now: Workstream 5 must not drift into accidental overclaim once a non-fixture-looking compare scope exists internally. The publication boundary needs an explicit truth condition instead of relying on inference.

## Migration Plan
1. Compatibility window: immediate; no public wording is widened by this change.
2. Migration steps:
   1. clarify the trust/publication contract,
   2. clarify the Terraform scope contract and evaluator guide,
   3. record the blocker in current authority and the governed-proof implementation plan.
3. Validation gates:
   1. `python scripts/reviewrun/run_terraform_plan_review_live_smoke.py --out benchmarks/results/proof/terraform_plan_review_live_smoke.json`
   2. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py`
   3. `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json`
   4. `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: the blocker wording is found to understate a newly shipped non-fixture evaluator path or to conflict with later public admission evidence.
2. Rollback steps:
   1. remove the blocker clarification from the trust/publication and Terraform scope contracts,
   2. update current authority to the new public admission truth in the same change.
3. Data/state recovery notes: no runtime data migration is involved.

## Versioning Decision
- Version bump type: clarifying contract tightening without widening public claims
- Effective version/date: 2026-04-18
- Downstream impact: readers must not infer that internal Terraform compare-scope admission is already enough for public trust admission.
