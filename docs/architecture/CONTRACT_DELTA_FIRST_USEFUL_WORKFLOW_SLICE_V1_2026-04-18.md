# First Useful Workflow Slice v1 Contract Delta

## Summary
- Change title: First Useful Workflow Slice v1
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`, `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`

## Delta
- Current behavior: Trusted Run Witness v1 admitted only the ProductFlow governed `write_file` compare scope, which proves the internal `approved.txt` slice but is not an externally useful repo-change workflow.
- Proposed behavior: Admit `trusted_repo_config_change_v1` as a separate proof-only useful workflow slice that writes a bounded fixture repo JSON config after approval, validates it deterministically, emits a witness bundle, and routes offline claim assignment through the existing offline verifier CLI.
- Why this break is required now: The accepted requirements ask Orket to prove value beyond the control-plane story and beyond ProductFlow's internal `approved.txt` proof without relabeling old evidence.

## Migration Plan
1. Compatibility window: ProductFlow Trusted Run Witness remains valid with its existing compare scope and artifact paths.
2. Migration steps: Add the new durable spec, add dedicated proof workflow scripts, route offline verification by `compare_scope`, and keep existing ProductFlow proofs unchanged.
3. Validation gates: Contract tests for validator, witness bundle verification, campaign stability, offline claim assignment, denial, validator failure, missing authority evidence, and overclaim prevention; live campaign proof with `ORKET_DISABLE_SANDBOX=1`.

## Rollback Plan
1. Rollback trigger: The new proof slice produces false-green evidence, mutates outside the fixture workspace, or causes existing ProductFlow Trusted Run proof regression.
2. Rollback steps: Remove the `trusted_repo_config_change_v1` CLI routing and proof commands, remove the new canonical authority entries, and leave ProductFlow Trusted Run Witness v1 unchanged.
3. Data/state recovery notes: The slice writes only under `workspace/trusted_repo_change/` and `benchmarks/results/proof/`; no durable runtime database migration is introduced.

## Versioning Decision
- Version bump type: Additive contract extension.
- Effective version/date: 2026-04-18.
- Downstream impact: Offline verifier callers may now submit `trusted_repo_config_change_v1` evidence through the existing verifier CLI. Existing ProductFlow evidence remains supported.
