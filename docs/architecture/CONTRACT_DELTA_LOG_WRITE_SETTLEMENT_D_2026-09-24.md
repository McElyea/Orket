# Log append settlement before audit workspace release

## Summary
- Change title: Settle prior optional append attempts before tool-gate audit cleanup.
- Owner: Orket Core.
- Date: 2026-09-24.
- Affected contracts: `docs/specs/LOG_WRITE_SETTLEMENT.md`,
  `docs/specs/TOOL_EXECUTION_GATE_V1.md` and logging lifecycle documentation.
- Status: implementation contract for 0.6.105. The
  architectural-truth plan owns acceptance and publication status.

## Delta
- Published behavior: async audit collection can return while the existing logging
  daemon still owns writes under the audit temporary workspace. Cleanup can race
  those writes and mask a required engine-close failure.
- Required behavior: the native audit owner settles a marker on that same queue
  before temporary-owner exit, on successful and failed collection paths. Only
  append attempts admitted before the marker are covered. No replacement writer,
  executor or cleanup owner is introduced.
- Failure boundary: a running-loop caller refuses before admission. Unexpected
  daemon death wakes marker waiters with a stable error and retained cause instead
  of stranding them. The writer is not restarted. Ordinary optional `OSError` and
  bounded drop behavior remain best effort.
- Capacity consequence: a pending marker occupies one existing bounded slot and
  can cause a concurrent ordinary admission to drop. Markers never increment the
  ordinary drop counter. Cutoff begins at admission, including when admission had
  to wait for capacity; there is no fairness or live-writer termination promise.
- Combined failure: an invocation-owned collection/close exception remains
  outward when the exact built-in writer-termination error also occurs. A stable
  note records secondary code/type and daemon-cause type without replacing the
  primary's graph or attaching secondary objects. Ambient caller exceptions,
  unknown errors, subclasses and settlement interrupts are not reclassified.
- Runtime-event value construction and constants move unchanged to
  `orket/core/runtime_event.py`. The existing logging schema constant remains
  explicitly available from `orket.logging`; there is one definition and no new
  event schema or field semantics.
- Why now: the retained second final-source campaign failed at real Windows audit
  workspace cleanup. The reached opening demonstrates owner-exit ordering, while
  the original campaign retains the literal WinError 145 observation.

## Migration Plan
1. Compatibility window: additive native boundary; existing optional producers
   retain their existing API. No compatibility shim or persisted-data migration.
2. Migrate the audit CLI to settle in its existing temporary-owner scope. Do not
   call the blocking frontier directly from an event loop or substitute queue-wide
   draining for the fixed marker boundary.
3. Validation gates: retained reached opening; held-write success/failure cleanup;
   later-write exclusion; unprepared reuse, loop refusal, optional append failure,
   full queue and daemon-death controls; combined close/daemon failure, ambient
   caller and exact-classification controls; unchanged affected/full source and exact
   installed package acceptance. The plan distinguishes executed and absent proof.

## Rollback Plan
1. Trigger: duplicate ownership, event/schema drift, missed prior append, dead-writer
   wait, ordinary optional escalation, cleanup race or failed acceptance.
2. Repair or revert the scoped implementation and its contract together. Keep every
   original failed/passing observation and any successor evidence immutable.
3. Do not rewrite logs, operation artifacts or audit history to manufacture success.
   Reverting reinstates the retained cleanup risk; it does not accept that risk.

## Versioning Decision
- Version bump type: patch in the active architectural-remediation lane.
- Target version / contract date: 0.6.105 / 2026-09-24; publication requires proof.
- Downstream impact: audit completion now waits for prior accepted optional append
  attempts. No durability, forced deadline, broader logging lifecycle, Linux,
  full-coverage or whole-lane acceptance is implied.
