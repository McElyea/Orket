# Contract Delta: Runtime Verification Support Artifact

## Summary

- Change title: downgrade `runtime_verification.json` to an explicit support-verification artifact with preserved history
- Owner: Orket Core
- Date: 2026-04-08
- Affected contract(s):
  - `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
  - `CURRENT_AUTHORITY.md`
  - `orket/application/services/runtime_verifier.py`
  - `orket/application/services/runtime_verification_artifact_service.py`
  - `orket/runtime/summary/run_summary.py`

## Delta

- Current behavior:
  - `runtime_verification.json` existed at one fixed latest path and could be over-read as a primary artifact when no authored work output was recorded
  - the verifier report did not distinguish syntax-only checks, command execution, behavioral verification, and not-evaluated scope explicitly
  - materially distinct verifier results could be overwritten at the latest path without preserved history
- Proposed behavior:
  - `runtime_verification.json` remains the canonical latest-path verifier surface, but it is now explicitly marked `artifact_role=support_verification_evidence`, `artifact_authority=support_only`, and `authored_output=false`
  - every verifier payload now records `overall_evidence_class` plus an `evidence_summary` over `syntax_only`, `command_execution`, `behavioral_verification`, and `not_evaluated`
  - verifier outputs now preserve run, issue, turn, retry, and record provenance and write a stable history index at `runtime_verification_index.json` plus per-record artifacts under `runtime_verifier_records/`
  - run-summary and MAR paths no longer promote the verifier artifact to the primary authored output by default
- Why this break is required now:
  - the previous posture could narrate stronger proof than the verifier had actually produced
  - a single fixed latest path without preserved history was lossy across retries and repeated review turns

## Migration Plan

1. Compatibility window:
   - keep `agent_output/verification/runtime_verification.json` as the canonical latest-path surface
2. Migration steps:
   - emit explicit evidence classes from `RuntimeVerifier`
   - persist latest plus index plus per-record verifier artifacts
   - harden MAR and run-summary logic so support artifacts are not treated as authored outputs
3. Validation gates:
   - `tests/application/test_runtime_verifier_service.py`
   - `tests/application/test_runtime_verification_artifact_service.py`
   - `tests/runtime/test_run_summary_packet1.py`
   - `tests/scripts/test_audit_phase2.py`
   - `tests/live/test_system_acceptance_pipeline.py`

## Rollback Plan

1. Rollback trigger:
   - downstream tooling cannot consume the latest-path verifier artifact after the explicit support-artifact framing lands
2. Rollback steps:
   - keep the latest-path file stable
   - relax MAR/runtime-summary validators first if downstream consumers need time to catch up
   - do not reintroduce implicit primary-output promotion of the verifier artifact
3. Data/state recovery notes:
   - rollback is code-and-docs only; preserved verifier history artifacts may remain on disk

## Versioning Decision

- Version bump type: none at the package level for this repo-local contract hardening change
- Effective version/date: 2026-04-08
- Downstream impact:
  - operator and audit tooling must read the verifier artifact as support evidence, not authored output
  - consumers can continue reading the latest-path file, but now have explicit history and proof-quality metadata
