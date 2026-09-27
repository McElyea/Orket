# Sandbox lifecycle event publication ownership

## Summary
- Change title: Capture event publication inputs and retain one cooperating spool owner.
- Owner: Orket Core.
- Date: 2026-09-27.
- Affected contract: `docs/specs/SANDBOX_EVENT_PUBLICATION_OWNERSHIP.md`.

## Delta
- Previously, cancelled replay acquisition could leak a descriptor and permanent
  exclusive-create sentinel. Fallback could serialize a changed payload under an
  earlier event identity. A producer could receive `fallback` while replay later
  deleted its newly appended row.
- Emit and replay capture their standard invocation inputs before awaiting and
  use the existing shared I/O owner through all admitted work and cleanup.
  Repository arguments are detached from the records reserved for fallback,
  retry and dead-letter publication.
- Publisher identity and direct service admission reuse the existing hook-free
  `capture_log_event_inputs` value authority before any repository or spool effect.
  Exact built-in JSON values plus tuples are supported; custom classes/subclasses,
  cycles, non-string keys and non-finite numbers refuse with the existing
  `E_LOG_EVENT_INPUT_UNSUPPORTED`. Direct service records must be the exact declared
  model. This closes the earlier candidate's custom `__deepcopy__` borrowing and
  loop-blocking hole without adding a second JSON copier or copying resource ports.
  Replay refuses unsupported retained values without consuming a repository retry.
- The required replay warning runs through the existing native worker with
  captured diagnostic fields and exception information. Handler failure remains
  explicit and preserves prior partial effects; general logging is outside scope.
- Append and replay share existing nonblocking host-native locks. Busy replay
  preserves its zero-count refusal. Busy fallback now explicitly fails both-sink
  publication instead of acknowledging a row that replay can discard.
- Retry counts, legacy/current spool rows, SQLite event identity, temporary-file
  replacement and partial dead-letter effects retain their existing semantics.
  No exactly-once, rollback, distributed lock or replay scheduler is introduced.

## Migration Plan
1. Stop all old callers before using the new protocol on a spool. Mixed versions
   do not share ownership and are unsupported.
2. An existing legacy `.lock` entry refuses spool work. Inspect old owners and
   retained evidence; resolve that sentinel only through separately authorized
   maintenance. The application does not delete an uncertain legacy owner.
3. Preserve new native identity files in `<spool-name>.owners/`; their presence is
   normal after release. Process exit releases the OS lock, not its identity file.
4. Callers encountering explicit busy fallback must handle publication refusal;
   a retry is a new admission after inspecting/resolving the conflicting owner.
5. Keep focused file/SQLite/process controls with existing sandbox lifecycle,
   cleanup and recovery guards in both Quality selections. Candidate observations
   and environment limits belong in the architectural-truth plan.
6. Normalize custom Python payloads/metadata to supported built-ins before calling
   either publication entrypoint. There is no hook-based compatibility window.
   Inspect retained unsupported replay rows and correct them through separately
   authorized maintenance; refusal does not delete or silently normalize evidence.
7. Process proof must bind child interpreter/package origins to the selected source
   or installed package separately from the copied test harness.

## Rollback Plan
1. Refuse affected admission if parity or ownership controls fail; preserve spool,
   dead-letter, SQLite and ownership evidence.
2. Stop cooperating callers before changing protocols. Do not restore the old
   replay-only lock or erase partial effects to manufacture a clean result.

## Versioning Decision
- Version bump type: patch, next architectural-truth checkpoint.
- Effective date: candidate dated 2026-09-27; publication is recorded in the plan.
- Downstream impact: busy fallback and unsupported Python values now report explicit
  refusal; admitted JSON schemas and identity formula remain unchanged. Direct
  private replay-lock helpers are removed.
