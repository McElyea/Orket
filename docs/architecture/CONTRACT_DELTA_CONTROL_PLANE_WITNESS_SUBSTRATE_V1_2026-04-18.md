# Control Plane Witness Substrate v1 Contract Delta

## Summary
- Change title: Control Plane Witness Substrate v1 verifier evidence model
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`, `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`, `trusted_run_witness_report.v1`

## Delta
- Current behavior: Trusted Run Witness verifier acceptance depends on the recomputed contract verdict and Trusted Run Invariants model.
- Proposed behavior: Verifier acceptance also emits and enforces a Control Plane Witness Substrate model that distinguishes required authority, authority-preserving projections, projection-only evidence, and forbidden substitutes.
- Why this break is required now: The accepted Control Plane As Witness Substrate requirements define the control plane as proof substrate, not product surface expansion, and require projection-only evidence to fail closed when used as authority.

## Migration Plan
1. Compatibility window: No compatibility shim for current proof artifacts. Regenerate Trusted Run Witness proof artifacts after this verifier change.
2. Migration steps: Run `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_run_witness_campaign.py`.
3. Validation gates: focused Trusted Run Witness contract tests, proof script compile checks, live ProductFlow campaign, and docs hygiene.

## Rollback Plan
1. Rollback trigger: Current ProductFlow Trusted Run Witness campaign cannot produce two successful substrate-verified reports.
2. Rollback steps: Remove the substrate verifier enforcement and restore the Control Plane As Witness Substrate requirements lane as active.
3. Data/state recovery notes: Proof artifacts are rerunnable JSON with diff-ledger history; no workflow state migration is required.

## Versioning Decision
- Version bump type: additive verifier contract tightening
- Effective version/date: 2026-04-18
- Downstream impact: Consumers of `trusted_run_witness_report.v1` should read `control_plane_witness_substrate` and `substrate_signature_digest` when evaluating campaign trust.
