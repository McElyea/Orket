# Complete asynchronous runtime-input capture

## Summary
- Change title: Retain the complete runtime-input capture operation in one native owner.
- Owner: Orket Core.
- Date: 2026-09-25.
- Affected contracts: `SETTINGS_INPUT_OWNERSHIP.md` and
  `RUNTIME_EXECUTION_RESULT_CONTRACT.md`.
- Status: implementation contract for the 0.6.106 development candidate.
  Acceptance and publication remain governed by the canonical architectural-truth
  remediation plan; scoped source proof is not installed acceptance.

## Delta
- Published behavior: async complete capture performs cwd selection, environment
  mapping hooks, serialization and immutable construction on the event loop around
  an owned settings-read await. Initial location selection precedes suspension.
- Required behavior: one existing `run_owned_thread` call owns the entire capture.
  One settings-pair collector preserves independent bound/persisted values and
  one unbound location. Native failure precedence and cancellation settlement remain.
- Intentional timing change: no-input async defaults select cwd/environment and
  unbound location as the admitted capture worker executes. This is later than
  selection in the coroutine before its first suspension. Explicit objects retain
  their already-selected identity and values. This is not identical timing.
  Fully bound settings-pair collection now also uses the owned worker and can
  suspend; it previously could return without suspension. No file read is added
  for an independently bound value.
- Bound context propagation, existing persistence selection, empty bound objects,
  preference migration, malformed-data errors and synchronous capture remain.
  There is no new executor, queue, settings implementation or runtime owner.
- This correction alone does not prove canonical CLI/API/driver/child/legacy route
  propagation. Those routes remain required D work with their own concrete deltas.

## Migration Plan
1. Compatibility window: public async default capture remains available. Callers
   requiring an earlier instant supply explicit `RuntimeConstructionInputs`.
2. Migration steps: move complete capture into the existing native owner, retain
   the settings value collector once, and bind returned settings in the caller's
   context when required. A worker-local binding cannot configure another task.
3. Validation gates: retain independently bound/unbound/empty values, migration,
   malformed-file and synchronous omission controls; execute held real reads and
   a blocking mapping, strict independent SQLite under .5s, repeated cancellation
   and native-failure precedence. Preserve factory admission and lifetime controls.
   Source and installed proof remain required. Prepared tests are not evidence.

## Rollback Plan
1. Rollback trigger: changed value/migration/error behavior or unowned native work.
2. Rollback steps: stop candidate publication and correct the existing owner; do
   not substitute a second capture or weaken responsiveness/lifetime checks.
3. Data/state recovery notes: retain every observed migration/partial effect and
   failed proof. Cancellation does not roll back completed settings effects.

## Versioning Decision
- Version bump type: patch correction with an explicit async selection-time delta.
- Effective version/date: 0.6.106 development candidate / 2026-09-25.
- Downstream impact: earlier-snapshot callers pass an explicit object; no settings
  file schema, runtime result schema or default path is changed.
