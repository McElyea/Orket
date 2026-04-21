# Contract Delta: Trusted Terraform Bedrock Summary Provider Flexibility

## Summary
- Change title: Admit Amazon Nova alongside Anthropic for the Terraform governed-proof Bedrock summary seam
- Owner: Orket Core
- Date: 2026-04-19
- Affected contract(s): `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: the provider-backed Terraform governed-proof path accepts only `anthropic.*` Bedrock model ids and emits an Anthropic-specific `InvokeModel` request body for the advisory summary seam.
- Proposed behavior: admit direct `anthropic.*` model ids plus Anthropic inference-profile ids through `InvokeModel`, and direct `amazon.nova-*` model ids plus Nova inference-profile ids through Bedrock `Converse`, while defaulting the no-spend setup packet to the portable Nova profile id `us.amazon.nova-lite-v1:0`.
- Why this break is required now: Bedrock accepts the same bounded Orket summary seam through portable Nova inference profiles in Regions where direct on-demand Nova foundation-model ids are rejected, letting small operator accounts truthfully run the governed-proof summary path when Anthropic FTU approval is unavailable and without widening the public trust boundary or relaxing fail-closed behavior.

## Migration Plan
1. Compatibility window: immediate; Anthropic model ids remain admitted on the existing path while Amazon Nova is added as a second admitted family.
2. Migration steps:
   1. update the Bedrock summary helper to route by admitted model family and inference-profile shape,
   2. update no-spend preflight and setup-packet readiness to admit Nova inference-profile ids and record the truthful Bedrock runtime operation plus resource shape,
   3. update current authority and the Terraform governed-proof scope docs.
3. Validation gates:
   1. `python -m pytest -q tests/scripts/test_check_trusted_terraform_live_setup_preflight.py tests/scripts/test_prepare_trusted_terraform_live_setup_packet.py tests/scripts/test_run_trusted_terraform_plan_decision_runtime_smoke.py`
   2. `python scripts/proof/check_trusted_terraform_live_setup_preflight.py`
   3. provider-backed runtime smoke with an admitted Nova model or inference-profile id

## Rollback Plan
1. Rollback trigger: Bedrock `Converse` drift breaks the bounded Terraform summary seam or produces evidence incompatible with the existing governed-proof wrapper.
2. Rollback steps:
   1. revert the Amazon Nova admission in the Bedrock summary helper and no-spend setup/preflight scripts,
   2. restore the setup packet default model id to the prior Anthropic model,
   3. remove the updated authority notes and this contract delta.
3. Data/state recovery notes: no runtime data migration is involved; generated setup files and proof artifacts are rerunnable support outputs only.

## Versioning Decision
- Version bump type: compatibility-preserving operator-surface expansion with no public-claim widening
- Effective version/date: 2026-04-19
- Downstream impact: operators can run the low-cost provider-backed Terraform governed-proof attempt with Amazon Nova when Anthropic FTU approval is unavailable.
