# Offline Trusted Run Verifier v1 Contract Delta

## Summary

- Change title: Offline Trusted Run Verifier v1
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`, `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

## Delta

- Current behavior: Trusted Run Witness verification can validate a single bundle or compare campaign stability, but there is no separate durable contract for assigning the highest truthful claim tier from existing evidence.
- Proposed behavior: Add an inspection-only offline verifier report schema, command, output path, claim ladder, and forbidden-claim vocabulary.
- Why this break is required now: The proof lane needs a source-of-truth surface that separates evidence validation from claim authorization, so Orket can avoid upgrading determinism claims from success-shaped evidence alone.

## Migration Plan

1. Compatibility window: Existing Trusted Run Witness verifier and campaign commands remain canonical for witness evidence production.
2. Migration steps:
   1. Add `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`.
   2. Add `scripts/proof/offline_trusted_run_verifier.py`.
   3. Add `scripts/proof/verify_offline_trusted_run_claim.py`.
   4. Keep the existing witness verifier output path unchanged.
   5. Add the separate offline verifier output path `benchmarks/results/proof/offline_trusted_run_verifier.json`.
3. Validation gates:
   1. Contract tests for bundle, single-report, campaign-report, requested replay downgrade, and the negative claim matrix.
   2. CLI proof that rerunnable JSON uses `diff_ledger`.
   3. Live ProductFlow Trusted Run Witness campaign followed by offline claim verification.

## Rollback Plan

1. Rollback trigger: Offline verifier reports contradict Trusted Run Witness reports or permit unsupported higher claims.
2. Rollback steps:
   1. Remove the offline verifier command from canonical authority.
   2. Keep Trusted Run Witness v1 bundle and campaign verification unchanged.
   3. Treat existing offline verifier artifacts as superseded structural evidence.
3. Data/state recovery notes: No workflow or durable control-plane state recovery is required because the verifier is inspection-only.

## Versioning Decision

- Version bump type: New additive proof contract.
- Effective version/date: 2026-04-18.
- Downstream impact: New claim reports should use `offline_trusted_run_verifier.v1`; witness bundles and `trusted_run_witness_report.v1` remain unchanged.
