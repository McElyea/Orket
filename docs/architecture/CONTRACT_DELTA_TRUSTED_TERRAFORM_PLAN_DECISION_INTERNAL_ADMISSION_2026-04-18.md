# Contract Delta: Trusted Terraform Plan Decision Internal Admission

## Summary
- Change title: Trusted Terraform plan decision internal compare-scope admission
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`, `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`, `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: `trusted_terraform_plan_decision_v1` was the chosen next scope only. Its commands and output paths were reserved, but it was not yet implemented or admitted in the trusted-run proof stack.
- Proposed behavior: admit `trusted_terraform_plan_decision_v1` as an internal-only governed-proof compare scope with active live, validator, campaign, offline-verifier, and witness-bundle surfaces while keeping public trust wording unchanged.
- Why this break is required now: Workstream 3 requires one externally useful non-fixture scope to be durably implemented and live-proven without overstating the public trust/publication boundary.

## Migration Plan
1. Compatibility window: immediate; existing ProductFlow and useful-workflow trusted-run slices remain unchanged and co-admitted.
2. Migration steps:
   1. implement the Terraform plan decision proof wrapper and CLI surfaces,
   2. admit the scope in current trusted-run specs and current authority,
   3. keep `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` unchanged so the external/public trust slice stays `trusted_repo_config_change_v1`.
3. Validation gates:
   1. `python -m pytest -q tests/application/test_terraform_plan_review_deterministic.py tests/application/test_terraform_plan_review_service.py tests/scripts/test_run_terraform_plan_review_live_smoke.py tests/scripts/test_trusted_terraform_plan_decision.py tests/scripts/test_trusted_run_proof_foundation.py tests/scripts/test_first_useful_workflow_slice.py tests/scripts/test_offline_trusted_run_verifier.py`
   2. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py`
   3. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py`
   4. `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json`
   5. docs hygiene and diff-check.

## Rollback Plan
1. Rollback trigger: the Terraform compare scope can no longer produce two successful verifier reports with stable scope-local signatures or begins to overstate the public trust slice.
2. Rollback steps:
   1. remove the Terraform compare scope from admitted trusted-run authority,
   2. revert the Terraform proof wrapper commands from current authority,
   3. restore `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md` to selected-next-only status.
3. Data/state recovery notes: proof artifacts are rerunnable JSON with diff-ledger history; no durable workflow-state migration is required.

## Versioning Decision
- Version bump type: additive internal admission of a new compare scope
- Effective version/date: 2026-04-18
- Downstream impact: trusted-run consumers may now encounter `trusted_terraform_plan_decision_v1` evidence and must keep its internal admission distinct from the narrower public trust slice.
