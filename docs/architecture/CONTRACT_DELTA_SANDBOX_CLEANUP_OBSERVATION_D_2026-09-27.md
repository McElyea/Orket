# Sandbox cleanup observation ownership

## Summary
- Change title: One retained compose-path observation per cleanup decision.
- Owner: Orket Core.
- Date: 2026-09-27.
- Affected contract: `docs/specs/SANDBOX_CLEANUP_OBSERVATION.md`.

## Delta
- Previously, authorization awaited an unretained native existence check, then
  decision projection checked the filesystem again on the event loop. Cancellation
  could return before the worker and the receipt could contradict authorization.
- Preview and execution now share one explicitly supplied boolean, obtained through
  the existing native worker owner. Projection does no filesystem work.
- Six real-filesystem/SQLite opening controls reproduce disagreement, loop-thread
  metadata and premature cancelled return in both paths. Docker is a declared
  command fixture in this scoped proof, not live Docker acceptance.

## Migration Plan
1. No compatibility shim; internal direct callers replace `compose_path` with
   `compose_path_available`. The two composed callers collect it once.
2. Existing event schema and stored lifecycle records need no migration.
3. Run cleanup observation and existing decision/authority/recovery controls in
   both Quality selections. Retain the strict independent SQLite responsiveness
   bound and cancellation settlement assertions.

## Rollback Plan
1. A parity failure blocks acceptance of this correction.
2. Disable the affected cleanup admission while preserving claims and receipts;
   do not restore duplicate observations or erase partially durable attempts.
3. Existing reconciliation owns recovery. Observed availability is not a filesystem
   lock, compose-content guarantee or verified Docker-resource absence.

## Versioning Decision
- Version bump type: patch, next architectural-truth checkpoint.
- Effective date: 2026-09-27 candidate; publication is recorded in the active plan.
- Downstream impact: direct internal decision builders supply the explicit boolean;
  external payloads, cleanup policy, command budgets and absence checks are preserved.
