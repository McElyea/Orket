# Contract Delta: Trusted Terraform Publication Readiness Gate

## Summary
- Change title: Add a fail-closed publication-readiness gate for `trusted_terraform_plan_decision_v1`
- Owner: Orket Core
- Date: 2026-04-19
- Affected contract(s): `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: Terraform governed-proof publication remains blocked by missing admitted provider-backed governed-proof evidence, but the blocking condition is documented rather than emitted as a stable machine-readable gate.
- Proposed behavior: add `python scripts/proof/check_trusted_terraform_publication_readiness.py` as the canonical fail-closed readiness gate, writing `benchmarks/results/proof/trusted_terraform_plan_decision_publication_readiness.json`.
- Why this break is required now: Workstream 5 needs a mechanical guard so later changes cannot infer publication readiness from local-harness campaign success alone.

## Migration Plan
1. Compatibility window: immediate; no public trust wording is widened.
2. Migration steps:
   1. add the readiness gate command and diff-ledger output,
   2. update Terraform scope, trust/publication, catalog, guide, and current authority docs,
   3. run the gate against current artifacts and keep its blocked result truthful until provider-backed governed-proof evidence succeeds.
3. Validation gates:
   1. `python -m pytest -q tests/scripts/test_check_trusted_terraform_publication_readiness.py`
   2. `python scripts/proof/check_trusted_terraform_publication_readiness.py`
   3. `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: the readiness gate proves to encode a stricter or looser condition than the active publication contract.
2. Rollback steps:
   1. remove the readiness command from current authority and affected specs,
   2. remove the readiness script and focused tests,
   3. restore publication-blocker wording to documentation-only status.
3. Data/state recovery notes: no runtime data migration is involved; the readiness artifact is rerunnable proof output only.

## Versioning Decision
- Version bump type: contract tightening with no public-claim widening
- Effective version/date: 2026-04-19
- Downstream impact: Terraform publication admission now requires the readiness gate to pass in addition to same-change trust/publication authority updates.
