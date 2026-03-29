# Contract Delta

## Summary
- Change title: Review-run bundle identity presence and alignment hardening
- Owner: Orket Core
- Date: 2026-03-28
- Affected contract(s): `docs/specs/REVIEW_RUN_V0.md`; shared review-bundle validation contract in `orket/application/review/bundle_validation.py`

## Delta
- Current behavior: shared review-bundle validation failed closed on execution-authority marker drift, but fresh or persisted manifest and lane payloads could still omit manifest or lane-payload `run_id`, fresh manifest or lane payload serialization could still emit `control_plane_run_id` that drifted from the same artifact `run_id`, persisted or fresh manifest and lane payloads could keep `control_plane_attempt_id` / `control_plane_step_id` refs that drifted outside the declared `control_plane_run_id` lineage, persisted lane payloads could still omit `control_plane_*` refs that the manifest already declared, keep lower-level `control_plane_attempt_id` / `control_plane_step_id` refs after parent run or attempt refs were dropped, disagree on `run_id` / `control_plane_*` refs while replay, scoring, or consistency consumers treated the bundle as trusted evidence, or let the consistency report producer serialize empty default, strict, replay, or baseline `run_id` fields into its own report surface.
- Proposed behavior: fresh manifest and review-lane artifact serialization plus shared review-bundle validation now require non-empty manifest and lane-payload `run_id`, reject fresh manifest or lane-payload `control_plane_run_id` when it drifts from the same artifact `run_id`, reject fresh or persisted manifest and lane attempt or step refs when they drift outside the declared `control_plane_run_id` lineage, require lane-payload `control_plane_run_id` / `control_plane_attempt_id` / `control_plane_step_id` whenever the manifest declares them, reject lower-level manifest or lane `control_plane_attempt_id` / `control_plane_step_id` refs that survive after parent run or attempt refs are dropped, fail closed when persisted manifest or lane payload `run_id`, `control_plane_run_id`, `control_plane_attempt_id`, or `control_plane_step_id` drift across the bundle, and make `scripts/reviewrun/run_1000_consistency.py` fail closed before report serialization when default, strict, replay, or baseline `run_id` is empty instead of emitting a blank run-like field.
- Why this break is required now: Workstream 1 is demoting review-local JSON to non-authoritative evidence. Allowing persisted bundle identifier omission or drift to survive shared validation would keep a hidden second run/attempt/step authority inside replay and analysis paths.

## Migration Plan
1. Compatibility window: none for malformed persisted bundles; aligned bundles remain unchanged.
2. Migration steps:
   - validate required manifest and lane-payload `run_id` presence, same-artifact `control_plane_run_id` alignment, required lane-payload `control_plane_*` refs when the manifest declares them, attempt/step run-lineage alignment under the declared `control_plane_run_id`, and lower-level manifest or lane `control_plane_*` ref hierarchy completeness during fresh artifact serialization and in the shared bundle loader
   - route replay, scoring, and consistency consumers through that shared loader
   - make workload-side code-review probe bundles emit aligned bundle-local `run_id` values and fail closed before artifact persistence when that `run_id` is empty before reusing shared scoring
   - fail closed before consistency-report serialization when default, strict, replay, or baseline `run_id` is empty instead of writing a blank run-like field into the report payload
   - update review-run contract docs and Workstream 1 closeout to name the new fail-closed rule
3. Validation gates:
   - contract proof for shared bundle-loader fail-closed behavior
   - scoring proof rejecting missing or drifted bundle identifiers
   - consistency proof rejecting missing or drifted bundle identifiers plus empty report `run_id` fields

## Rollback Plan
1. Rollback trigger: truthful persisted review bundles with aligned identifiers begin failing replay, scoring, or consistency extraction on the default path.
2. Rollback steps:
   - revert the shared required lane-payload `run_id`, required lane-payload `control_plane_*`, attempt/step run-lineage, control-plane ref hierarchy, and manifest-to-lane identifier checks in `orket/application/review/bundle_validation.py`
   - revert the fresh review manifest and lane-artifact same-run `control_plane_run_id`, attempt/step run-lineage, plus hierarchy checks in `orket/application/review/models.py`
   - revert the producer-side consistency-report `run_id` checks in `scripts/reviewrun/run_1000_consistency.py`
   - revert the review-run contract wording that requires persisted identifier alignment
   - revert workload-side code-review probe lane-payload `run_id` emission and producer-side empty-`run_id` rejection if the scoring seam must again tolerate omission
   - keep existing execution-authority marker checks in place unless rollback evidence shows they are also at fault
3. Data/state recovery notes: no persisted data migration is required; the change only rejects malformed persisted review bundles during validation.

## Versioning Decision
- Version bump type: additive fail-closed contract hardening
- Effective version/date: 2026-03-28
- Downstream impact: any fresh or persisted review artifact whose manifest or lane payload omits required `run_id`, whose fresh manifest or lane payload carries `control_plane_run_id` that drifts from the same artifact `run_id`, whose manifest or lane attempt/step refs drift outside the declared `control_plane_run_id` lineage, omits required `control_plane_*` refs declared by the manifest, keeps lower-level manifest or lane `control_plane_*` refs after parent run or attempt refs were dropped, whose manifest and lane payload identifiers drift, or whose consistency report producer tries to serialize empty default, strict, replay, or baseline `run_id` fields, must now be corrected or it will fail serialization, replay, scoring, and consistency validation
