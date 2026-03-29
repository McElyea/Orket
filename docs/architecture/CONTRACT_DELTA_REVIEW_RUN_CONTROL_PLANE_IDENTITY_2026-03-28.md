# Contract Delta

## Summary
- Change title: Review-run control-plane projection identity and lifecycle hardening
- Owner: Orket Core
- Date: 2026-03-28
- Affected contract(s): `docs/specs/REVIEW_RUN_V0.md`; review result / CLI `control_plane` projection contract in `orket/application/review/control_plane_projection.py` and `orket/application/review/models.py`

## Delta
- Current behavior: review result and CLI `control_plane` summaries failed closed on projection framing drift, but a projection could still serialize successfully if the embedded manifest dropped matching `control_plane_*` refs, if run/attempt/step identity drifted while projection framing stayed valid, if lower-level projected `attempt_id` / `step_id` survived after parent `run_id` / `attempt_id` dropped, if projected `attempt_state` / `attempt_ordinal` survived after projected `attempt_id` dropped, if projected `step_kind` survived after projected `step_id` dropped, or if projected run/attempt/step ids survived after the projection dropped the lifecycle metadata those ids claim to summarize.
- Proposed behavior: review result and CLI `control_plane` summaries now also fail closed when projected `run_id` drifts from the enclosing review result `run_id`, when projected `attempt_id` / `step_id` drift from the embedded manifest control-plane refs when those refs are present, when lower-level projected `attempt_id` / `step_id` survive after parent `run_id` / `attempt_id` drop, when projected `attempt_state` / positive `attempt_ordinal` survives after projected `attempt_id` drops, when projected `step_kind` survives after projected `step_id` drops, when the embedded manifest omits `control_plane_run_id` / `control_plane_attempt_id` / `control_plane_step_id` still carried by the returned projection, or when the projection carries `run_id` / `attempt_id` / `step_id` without the matching projected lifecycle metadata (`run_state`, workload identity, policy/config snapshot refs, `attempt_state`, positive `attempt_ordinal`, `step_kind`). The review CLI now surfaces that serialization failure as the normal structured review error payload instead of an uncaught exception.
- Why this break is required now: Workstream 1 is explicitly demoting review-local execution-state authority. Allowing mismatched, half-dropped, lifecycle-incomplete, or orphaned-metadata control-plane refs to survive inside an otherwise well-framed projection would preserve hidden run/attempt/step drift under a surface that claims to be non-authoritative.

## Migration Plan
1. Compatibility window: none for malformed projections; correctly aligned review results and CLI payloads remain unchanged.
2. Migration steps:
   - validate review result manifests against the enclosing review result run identity
   - validate review `control_plane` projections against the enclosing result and manifest control-plane refs, including required embedded manifest ref preservation when the returned projection carries those refs
   - reject lower-level projected `attempt_id` / `step_id` when the parent `run_id` / `attempt_id` is missing
   - reject projected `attempt_state` / `attempt_ordinal` when `attempt_id` is missing and reject projected `step_kind` when `step_id` is missing
   - require review `control_plane` projections to preserve projected run metadata, attempt state plus positive attempt ordinal, and step kind whenever they carry the corresponding ids
   - keep review CLI serialization failures on the structured `E_REVIEW_RUN_FAILED` path instead of allowing uncaught exceptions
   - keep review replay and bundle-validation paths on the same shared authority story
3. Validation gates:
   - contract proof for `ReviewRunResult` serialization fail-closed behavior
   - contract proof for lifecycle-incomplete and orphaned-metadata review `control_plane` projections
   - integration proof for review-run execution rejecting drifted or lifecycle-incomplete projected control-plane summaries
   - CLI proof for structured review failure output when result serialization detects embedded manifest/control-plane drift
   - replay / review bundle proof showing aligned payloads still pass

## Rollback Plan
1. Rollback trigger: truthful review results with aligned durable control-plane refs begin failing serialization or CLI output on the default review path.
2. Rollback steps:
   - revert the added identifier-alignment, lifecycle-completeness, orphaned-metadata, and embedded manifest ref-preservation checks in the review control-plane projection and result contract
   - revert the structured CLI serialization-error handling if that path itself proves faulty
   - revert the spec wording that requires identifier alignment
   - keep existing framing checks in place unless rollback evidence shows they are also at fault
3. Data/state recovery notes: no persisted data migration is required; this change only rejects mismatched review result projections during serialization.

## Versioning Decision
- Version bump type: additive fail-closed contract hardening
- Effective version/date: 2026-03-28
- Downstream impact: any review result, CLI payload, or test fixture that serialized mismatched control-plane refs, dropped embedded manifest control-plane refs while still returning those refs through the `control_plane` projection, kept projected `attempt_id` / `step_id` after parent `run_id` / `attempt_id` dropped, kept projected `attempt_state` / `attempt_ordinal` after projected `attempt_id` dropped, kept projected `step_kind` after projected `step_id` dropped, or carried projected run/attempt/step ids without the matching lifecycle metadata must now align and preserve those fields, including positive `attempt_ordinal` when `attempt_id` is present, or fail closed
