# Trusted Run Invariants v1 Contract Delta

## Summary
- Change title: Trusted Run Invariants v1 verifier acceptance model
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`, `trusted_run_witness_report.v1`

## Delta
- Current behavior: Trusted Run Witness v1 verifier acceptance depends on the recomputed `trusted_run_contract_verdict.v1`, stable verdict signatures, and stable must-catch outcomes.
- Proposed behavior: Verifier acceptance also requires `trusted_run_invariant_model.v1` to pass. Campaign promotion to `verdict_deterministic` now requires stable contract-verdict and invariant-model signatures.
- Why this break is required now: The accepted mathematical-foundation requirements add a bounded formal model and close previously named missing-proof gaps for step lineage, lease source, resource/lease consistency, effect prior chain, final-truth cardinality, and verifier side-effect-free evaluation.

## Migration Plan
1. Compatibility window: No compatibility shim. Existing trusted-run witness bundles must be regenerated with the current ProductFlow proof scripts.
2. Migration steps: Regenerate the ProductFlow Trusted Run Witness campaign using `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_run_witness_campaign.py`.
3. Validation gates: `python -m pytest -q tests/scripts/test_trusted_run_witness.py`, `python -m py_compile scripts/proof/trusted_run_invariant_model.py scripts/proof/trusted_run_witness_contract.py scripts/proof/trusted_run_witness_support.py scripts/proof/build_trusted_run_witness_bundle.py scripts/proof/verify_trusted_run_witness_bundle.py scripts/proof/run_trusted_run_witness_campaign.py`, and docs project hygiene.

## Rollback Plan
1. Rollback trigger: The ProductFlow campaign can no longer produce two successful verifier reports from current runtime evidence.
2. Rollback steps: Revert verifier acceptance to Trusted Run Witness v1 contract-verdict-only acceptance and restore the accepted requirements lane as active.
3. Data/state recovery notes: Existing proof artifacts are rerunnable JSON with diff-ledger history; no workflow state migration is required.

## Versioning Decision
- Version bump type: additive verifier contract tightening
- Effective version/date: 2026-04-18
- Downstream impact: Consumers of `trusted_run_witness_report.v1` must read `trusted_run_invariant_model` and `invariant_model_signature_digest` when evaluating campaign trust.
