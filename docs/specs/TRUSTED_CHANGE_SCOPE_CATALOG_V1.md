# Trusted Change Scope Catalog v1

Last updated: 2026-04-19
Status: Active contract
Owner: Orket Core

This spec is the truthful compare-scope catalog for admitted governed-proof trusted change scopes.

## Purpose

Keep the admitted compare-scope surface comparable without erasing the current public/internal distinction.

The current externally publishable public trust slice remains narrower than the full internal admitted compare-scope set.

## Boundary

This catalog does not, by itself:

1. admit a new compare scope,
2. broaden public trust wording,
3. replace scope-local contracts, or
4. replace `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` as the external/public publication authority.

## Current Catalog Summary

| Compare scope | Publication status | Purpose | Effect boundary | Validator / deterministic check surface | Claim ceiling | Current proof limitations | Authority docs |
|---|---|---|---|---|---|---|---|
| `trusted_run_productflow_write_file_v1` | internal admitted only | bounded ProductFlow governed `write_file` proof slice | one governed `write_file` effect over one approved ProductFlow issue | `trusted_run_contract_verdict.v1` with no separate validator surface | `verdict_deterministic` | not part of current public trust slice; no replay determinism; no text determinism | `docs/specs/TRUSTED_RUN_WITNESS_V1.md` |
| `trusted_repo_config_change_v1` | current externally admitted public trust slice | bounded useful workflow slice for a local fixture repo config change | one policy-bounded local fixture config mutation | `trusted_repo_config_validator.v1` | `verdict_deterministic` | local fixture only; no replay determinism; no text determinism | `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`, `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` |
| `trusted_terraform_plan_decision_v1` | internal admitted only | bounded Terraform plan review decision proof slice | one policy-bounded Terraform review decision publication | `trusted_terraform_plan_decision_validator.v1` | `verdict_deterministic` | internal only; provider-backed governed-proof publication readiness not yet satisfied; setup packet and preflight are preparation-only; decision publication only; no replay determinism; no text determinism | `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md` |

## Scope Cards

Each admitted scope is summarized below through one short scope card.

### `trusted_run_productflow_write_file_v1`

1. publication status: internal admitted only
2. purpose: prove one bounded governed ProductFlow `write_file` success path
3. bounded effect: write `agent_output/productflow/approved.txt` and publish consistent success truth for the same governed run
4. validator / deterministic check surface: `trusted_run_contract_verdict.v1`
5. single-run claim tier: `non_deterministic_lab_only`
6. campaign claim ceiling: `verdict_deterministic`
7. current proof limitations: not part of the current external/public trust slice; replay and text claims remain forbidden
8. canonical commands: `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_run_witness_campaign.py`; `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_run_witness_verification.json --claim verdict_deterministic`
9. authority docs: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`, `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`, `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
10. forbidden claims: current public trust admission, replay determinism, text determinism, or general workflow correctness

### `trusted_repo_config_change_v1`

1. publication status: current externally admitted public trust slice
2. purpose: prove one bounded useful local fixture repo config change under policy
3. bounded effect: mutate only `workspace/trusted_repo_change/repo/config/trusted-change.json` and validate the exact resulting config
4. validator / deterministic check surface: `trusted_repo_config_validator.v1`
5. single-run claim tier: `non_deterministic_lab_only`
6. campaign claim ceiling: `verdict_deterministic`
7. current proof limitations: local fixture only; replay and text claims remain forbidden; broader workflow claims remain out of scope
8. canonical commands: `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py`; `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py`; `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json`
9. authority docs: `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`, `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
10. forbidden claims: replay determinism, text determinism, remote provider truth, or general repository automation trust

### `trusted_terraform_plan_decision_v1`

1. publication status: internal admitted only
2. purpose: prove one bounded Terraform plan review decision without turning that proof into Terraform apply or infrastructure trust
3. bounded effect: publish one bounded Terraform review decision plus governed-proof evidence for the same plan input
4. validator / deterministic check surface: `trusted_terraform_plan_decision_validator.v1`
5. single-run claim tier: `non_deterministic_lab_only`
6. campaign claim ceiling: `verdict_deterministic`
7. current proof limitations: internal only; provider-backed governed-proof publication readiness currently blocks when successful runtime evidence is missing; setup packet and preflight are preparation-only; no replay determinism; no text determinism; no Terraform apply or infrastructure correctness claim
8. canonical commands: `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py`; `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py`; `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json`; `python scripts/proof/prepare_trusted_terraform_live_setup_packet.py`; `python scripts/proof/check_trusted_terraform_live_setup_preflight.py`; `python scripts/proof/check_trusted_terraform_publication_readiness.py`; `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py`
9. authority docs: `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`
10. forbidden claims: current external/public trust admission, replay determinism, text determinism, Terraform apply safety, or general IaC workflow trust

## Catalog Rule

This catalog remains truthful only while all of the following are true:

1. every admitted scope above still resolves to a scope-local contract under `docs/specs/`,
2. publication status and claim ceilings match the current offline-verifier truth,
3. current proof limitations stay explicit rather than implied, and
4. new compare scopes are not treated as admitted until this catalog and `CURRENT_AUTHORITY.md` are updated in the same change.
