# Contract Delta: Trusted Terraform Publication Gate Sequence

## Summary
- Change title: Add a one-shot Terraform governed-proof publication gate sequence
- Owner: Orket Core
- Date: 2026-04-19
- Affected contract(s): `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: operators must run the Terraform proof foundation, campaign, offline claim, provider-backed governed runtime smoke, and readiness gate as separate commands to evaluate publication readiness.
- Proposed behavior: add `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` as the canonical one-shot gate sequence, writing `benchmarks/results/proof/trusted_terraform_plan_decision_publication_gate.json`, recording non-secret live-environment preflight status, and failing fast by default when required live inputs are missing.
- Why this break is required now: the lane needs one repeatable operator path for live-environment retry without allowing local campaign success to be mistaken for public admission evidence.

## Migration Plan
1. Compatibility window: immediate; existing individual proof commands remain canonical and are invoked by the new sequence.
2. Migration steps:
   1. add the aggregate gate sequence command,
   2. record missing required live-provider input names without recording credential values,
   3. add `--force-local-evidence` for explicit local-artifact refresh while publication remains blocked,
   4. update scope, catalog, guide, trust/publication, and current authority docs,
   5. keep the sequence fail-closed until provider-backed governed-proof evidence succeeds.
3. Validation gates:
   1. `python -m pytest -q tests/scripts/test_run_trusted_terraform_plan_decision_publication_gate.py`
   2. `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py`
   3. `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: the aggregate sequence diverges from the individual canonical proof command results.
2. Rollback steps:
   1. remove the aggregate sequence from current authority and affected specs,
   2. remove the aggregate sequence script and focused tests,
   3. keep the individual proof commands and readiness gate as the publication boundary.
3. Data/state recovery notes: no runtime data migration is involved; the aggregate gate artifact is rerunnable proof output only.

## Versioning Decision
- Version bump type: operator-surface addition with no public-claim widening
- Effective version/date: 2026-04-19
- Downstream impact: future Terraform publication attempts should use the aggregate sequence as the first gate, then perform same-change public authority updates only if the sequence reports readiness.
