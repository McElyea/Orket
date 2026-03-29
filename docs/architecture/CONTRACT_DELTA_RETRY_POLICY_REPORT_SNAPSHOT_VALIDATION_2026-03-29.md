# Contract Delta

## Summary
- Change title: Retry-policy report embedded snapshot validation hardening
- Owner: Orket Core
- Date: 2026-03-29
- Affected contract(s): retry-policy report contract in `scripts/governance/check_retry_classification_policy.py` and its acceptance-gate consumer in `scripts/governance/run_runtime_truth_acceptance_gate.py`

## Delta
- Current behavior: the retry-policy checker already normalized malformed top-level report shape into a fail-closed error payload, and the acceptance gate already validated top-level report structure plus the persisted run-level `retry_classification_policy.json` artifact, but the embedded `snapshot` inside a retry-policy report only had to be a dict. An empty or drifted embedded snapshot could still survive failure-report validation, malformed producer output could still persist that invalid embedded snapshot into the diff-ledger artifact, and the acceptance gate could collapse valid fail-closed retry-policy reports back into generic false state without preserving their explicit error detail.
- Proposed behavior: retry-policy reports now fail closed unless the embedded `snapshot` is itself a valid retry-classification-policy snapshot. Producer normalization now falls back to the current canonical retry-policy snapshot when malformed output omits or drifts that embedded snapshot, and the acceptance gate rejects retry-policy reports whose embedded snapshot is invalid before trusting any top-level green or red signal while preserving explicit error detail from validated fail-closed retry-policy reports.
- Why this break is required now: Workstream 1 is demoting retry-local guidance into explicit projection-only evidence. Allowing an invalid embedded retry-policy snapshot to survive report validation or producer normalization would preserve a hidden second attempt-history authority inside governance evidence.

## Migration Plan
1. Compatibility window: none for malformed retry-policy reports; aligned reports remain unchanged.
2. Migration steps:
   - validate the embedded retry-policy snapshot in both success and failure reports
   - stop treating empty or falsy snapshot dicts as implicit fallback-to-canonical payloads during retry-policy validation
   - normalize malformed producer output to a fail-closed report carrying the canonical retry-policy snapshot
   - update active lane authority docs to record the new fail-closed rule
3. Validation gates:
   - runtime contract proof that empty payload no longer falls back to canonical snapshot silently
   - script proof that malformed report output is normalized to a valid fail-closed payload before diff-ledger write
   - acceptance-gate proof that invalid embedded snapshots are rejected

## Rollback Plan
1. Rollback trigger: truthful retry-policy reports with aligned embedded snapshots begin failing the checker or the acceptance gate on the default path.
2. Rollback steps:
   - revert embedded snapshot validation in `scripts/governance/check_retry_classification_policy.py`
   - revert the `None`-only fallback behavior in `orket/runtime/retry_classification_policy.py` if evidence shows it breaks truthful callers
   - revert the acceptance-gate dependency on the stricter report validator
   - revert the same-change authority wording that depends on this stricter contract
3. Data/state recovery notes: no persisted data migration is required; the change only rejects malformed retry-policy reports or rewrites malformed producer output to a fail-closed canonical-snapshot fallback.

## Versioning Decision
- Version bump type: additive fail-closed contract hardening
- Effective version/date: 2026-03-29
- Downstream impact: any producer or test fixture that emits a retry-policy report with an invalid embedded `snapshot`, or relied on empty embedded snapshots silently falling back to canonical policy truth, must now align that snapshot or expect fail-closed normalization / validation failure
