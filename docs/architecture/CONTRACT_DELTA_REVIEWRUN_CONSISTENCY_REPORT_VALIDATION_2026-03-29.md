# Contract Delta

## Summary
- Change title: ReviewRun consistency report contract validation hardening
- Owner: Orket Core
- Date: 2026-03-29
- Affected contract(s): persisted `scripts/reviewrun/run_1000_consistency.py` report contract; `scripts/reviewrun/check_1000_consistency.py`

## Delta
- Current behavior: the consistency report producer failed closed before serializing empty default, strict, replay, or baseline `run_id`, but it still wrote report payloads without validating its own shared contract framing first, and persisted report validation still trusted shallow `ok`, `runs_checked`, and signature counters without validating report contract framing, those nested report `run_id` fields, the required nested baseline/default/strict/replay signature fields including deterministic finding-row shape, or scenario-local `truncation_check` snapshot digests, byte counts, and boolean flags.
- Proposed behavior: producer-side consistency reporting now validates shared report contract framing plus required nested baseline/default/strict/replay signature digests, deterministic finding-row code/severity/message/path/span/details shape, deterministic-lane version, executed-check lists, truncation framing, and scenario-local `truncation_check` snapshot digests, byte counts, and boolean flags before write while still allowing truthful failed outcomes to persist as failed reports, and persisted consistency report validation now requires `contract_version=reviewrun_consistency_check_v1`, requires non-empty default, strict, replay, and baseline report `run_id` when runs were checked, requires those same nested signature fields plus scenario-local `truncation_check` fields to remain well formed, and fails closed before trusting persisted report JSON when any of that contract drifts.
- Why this break is required now: Workstream 1 is demoting review-local run-like read surfaces. Allowing either malformed producer-side consistency reports or shallow persisted checker trust would leave soft run-like authority paths after review-bundle hardening.

## Migration Plan
1. Compatibility window: none for malformed persisted consistency reports; truthful reports remain unchanged.
2. Migration steps:
   - validate producer-side report `contract_version` and required framing before writing any persisted consistency report while still permitting truthful failed outcomes
   - validate report `contract_version` before trusting any persisted consistency report
   - require non-empty default, strict, replay, and baseline report `run_id` fields before trusting persisted report JSON
   - require baseline/default/strict/replay signature digests, deterministic finding-row code/severity/message/path/span/details shape, deterministic-lane version, executed-check lists, truncation framing, and scenario-local `truncation_check` snapshot digests, byte counts, and boolean flags before producer write or persisted report trust
   - update Workstream 1 authority docs in the same change
3. Validation gates:
   - contract proof for producer-side consistency-report validation that still permits truthful failed outcomes
   - contract proof for persisted consistency-report validation
   - integration proof for producer main-path failure on malformed report contract framing, nested signature or finding-row shape, or scenario-local `truncation_check` shape before write
   - integration proof for checker main-path failure on malformed persisted report identity, nested signature or finding-row shape, or scenario-local `truncation_check` shape

## Rollback Plan
1. Rollback trigger: truthful persisted consistency reports begin failing validation on the default path.
2. Rollback steps:
   - revert the producer-side shared report-contract validation in `scripts/reviewrun/run_1000_consistency.py`
   - revert the persisted report `contract_version`, nested report `run_id`, nested signature-shape or finding-row-shape, and scenario-local `truncation_check` checks in `scripts/reviewrun/check_1000_consistency.py`
   - revert the Workstream 1 authority wording naming that checker hardening
3. Data/state recovery notes: no migration is required; the change only rejects malformed producer-side or persisted consistency reports.

## Versioning Decision
- Version bump type: additive fail-closed contract hardening
- Effective version/date: 2026-03-29
- Downstream impact: any producer-side consistency report with drifted `contract_version`, malformed contract framing, malformed nested baseline/default/strict/replay signature fields including deterministic finding-row shape, or malformed scenario-local `truncation_check` snapshot digests, byte counts, or boolean flags now fails before write, truthful failed outcomes remain writable as failed reports, and any persisted consistency report with drifted `contract_version`, empty default/strict/replay/baseline report `run_id`, malformed nested signature digests, deterministic finding-row shape, deterministic-lane version, executed-check lists, or truncation framing, or malformed scenario-local `truncation_check` fields must now be corrected or `check_1000_consistency.py` will fail closed instead of trusting shallow green counters.
