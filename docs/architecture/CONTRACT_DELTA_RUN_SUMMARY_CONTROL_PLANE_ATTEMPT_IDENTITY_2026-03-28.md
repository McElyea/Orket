# Contract Delta

## Summary
- Change title: Run-summary control-plane run, attempt, and step projection hardening
- Owner: Orket Core
- Date: 2026-03-28
- Affected contract(s): cards `run_summary.json` `control_plane` projection contract in `orket/runtime/run_summary.py` and `orket/runtime/run_summary_control_plane.py`

## Delta
- Current behavior: legacy cards `run_summary.json` `control_plane` projections already failed closed on projection framing drift, but a transient summary projection could still serialize if a projected cards run dropped core run metadata while still carrying `run_id`, if projected attempt ids survived without attempt state or ordinal, if projected attempt state or ordinal survived after projected `attempt_id` dropped, if projected `current_attempt_id` survived after projected `attempt_id` dropped, if projected `current_attempt_id` diverged from projected `attempt_id`, if a projected `attempt_id` or `step_id` survived after the projection dropped `run_id`, if a projected `step_id` survived after the projection dropped `attempt_id`, or if projected `step_kind` survived after projected `step_id` dropped, if a projected `attempt_id` no longer belonged to the projected `run_id`, or if a projected `step_id` no longer belonged to the projected `run_id` or survived without `step_kind`.
- Proposed behavior: cards `run_summary.json` `control_plane` projections now also fail closed when a projected cards run drops core run metadata while still carrying `run_id`, when lower-level projected ids survive without the parent ids they depend on, when projected attempt ids survive without attempt state or a positive attempt ordinal, when projected attempt state or ordinal survives after projected `attempt_id` drops, when projected `current_attempt_id` survives after projected `attempt_id` drops, when projected `current_attempt_id` drifts from projected `attempt_id` when both are present, when projected attempt ids drift outside the projected run lineage, or when projected step ids drift outside the projected run lineage or survive without `step_kind` or when projected `step_kind` survives after projected `step_id` drops. Finalize-time degradation keeps the durable run, attempt, and step records intact while dropping the invalid transient summary projection.
- Why this break is required now: Workstream 1 is demoting legacy summary-backed run, attempt, and step state into explicit projection-only read surfaces. Allowing transient run-projection incompleteness, id-hierarchy incompleteness, current-attempt hierarchy incompleteness, orphaned attempt or step metadata, attempt-metadata incompleteness, attempt-identity drift, attempt-lineage drift, step-metadata incompleteness, or step-lineage drift inside the summary projection would leave hidden execution authority in a surface that claims to be a derived projection.

## Migration Plan
1. Compatibility window: none for malformed cards summary projections; aligned projections remain unchanged.
2. Migration steps:
   - validate cards `run_summary.json` control-plane run projection completeness plus control-plane id hierarchy completeness, current-attempt hierarchy completeness, orphaned attempt/step metadata rejection, attempt/step metadata completeness, attempt alignment, and attempt/step run lineage during payload validation and summary building
   - keep finalize-time summary generation on the degraded closeout path when transient projection drift is detected
   - document the new fail-closed rule in the active ControlPlane lane authority surfaces
3. Validation gates:
   - contract proof for `run_summary` projection validation and builder fail-closed behavior
   - integration proof for finalize-time degraded summary generation when transient control-plane run-projection incompleteness, id-hierarchy incompleteness, current-attempt hierarchy incompleteness, orphaned attempt/step metadata, attempt/step metadata incompleteness, attempt-alignment, attempt-lineage, or step-lineage drift occurs
   - docs hygiene proof after updating the active lane authority files

## Rollback Plan
1. Rollback trigger: truthful cards summaries with aligned durable run and attempt truth begin failing validation or finalize-time closeout on the default cards path.
2. Rollback steps:
   - revert the added control-plane run-projection completeness, control-plane id hierarchy completeness, current-attempt hierarchy completeness, orphaned attempt/step metadata rejection, attempt/step metadata completeness, attempt-alignment, attempt-lineage, and step-lineage validation in `orket/runtime/run_summary.py`
   - revert the finalize-path proof and authority updates that depend on this hardening
   - keep existing projection-framing and bootstrap-identity checks in place unless rollback evidence shows they are also faulty
3. Data/state recovery notes: no persisted data migration is required; this change only rejects malformed transient summary projections and degrades summary emission when they occur.

## Versioning Decision
- Version bump type: additive fail-closed contract hardening
- Effective version/date: 2026-03-28
- Downstream impact: any cards summary producer or test fixture that drops core run metadata while still carrying `run_id`, lets projected lower-level ids survive after dropping their parent ids, lets projected attempt ids survive without attempt state or ordinal, lets projected attempt state or ordinal survive after projected `attempt_id` drops, lets projected `current_attempt_id` survive after projected `attempt_id` drops, lets projected `current_attempt_id` drift from projected `attempt_id`, lets a projected attempt id drift outside the projected run lineage, or lets a projected step id drift outside the projected run lineage or without `step_kind`, or lets projected `step_kind` survive after projected `step_id` drops, must now align those values or expect degraded summary generation / validation failure
