# Contract Delta: Trusted Terraform Live Setup Packet

## Summary
- Change title: Add no-spend live setup packet for Terraform governed proof
- Owner: Orket Core
- Date: 2026-04-19
- Affected contract(s): `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: operators can inspect live input shape through preflight, but the repo does not generate a bounded local setup packet for the later low-cost provider-backed run.
- Proposed behavior: add `python scripts/proof/prepare_trusted_terraform_live_setup_packet.py` as a no-spend setup packet generator that writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json` and local setup files under `workspace/trusted_terraform_live_setup/`; keep live preflight blocked when generated S3 placeholders are not replaced.
- Why this break is required now: the next provider-backed governed-proof attempt needs explicit fixture, environment, IAM, setup-command, and cleanup-command surfaces before credentials or provider APIs are used.

## Migration Plan
1. Compatibility window: immediate; no existing proof command behavior changes.
2. Migration steps:
   1. add the setup packet generator and tests,
   2. document the packet as preparation-only and no-spend,
   3. update current authority, the Terraform scope spec, the scope catalog, the trust/publication boundary, and the evaluator guide.
3. Validation gates:
   1. `python -m pytest -q tests/scripts/test_prepare_trusted_terraform_live_setup_packet.py`
   2. `python scripts/proof/prepare_trusted_terraform_live_setup_packet.py`
   3. `python scripts/governance/check_docs_project_hygiene.py`

## Rollback Plan
1. Rollback trigger: the generated packet drifts from the runtime smoke or preflight call plan.
2. Rollback steps:
   1. remove the setup packet generator and tests,
   2. remove setup packet references from current authority and affected specs,
   3. continue using the preflight, runtime smoke, and publication gate as the only live-readiness surfaces.
3. Data/state recovery notes: no runtime data migration is involved; generated setup files live under ignored workspace output and the report is rerunnable proof-support output.

## Versioning Decision
- Version bump type: operator-surface addition with no public-claim widening
- Effective version/date: 2026-04-19
- Downstream impact: live Terraform governed-proof attempts should generate the no-spend setup packet before provisioning low-cost AWS resources.
