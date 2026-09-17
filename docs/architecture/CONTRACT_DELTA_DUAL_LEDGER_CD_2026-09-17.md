# Dual-ledger lifecycle ownership and recovery

## Summary
- Owner: Orket Core.
- Date: 2026-09-17.
- Status: implementation candidate; source/live provider proof passes, installed gate open on retained Linux deadline failures.
- Affected contracts: dual-write lifecycle coordination, journal binding, recovery,
  cancellation and degraded mirror behavior.

## Delta
- `AsyncDualModeLedgerRepository` belongs to
  `orket/application/services/dual_write_run_ledger.py`. Storage owns journal
  serialization and verified file publication; core owns intent validation and
  content-match decisions. The old storage coordination module is removed.
- The journal is `<sqlite-db-filename>.dual-write-intents.json`, adjacent to the
  database. Schema `2.0` binds the resolved SQLite path and protocol root. Separate
  database files no longer share one parent-directory journal.
- A cooperating invocation owns both the journal's native `.owners/` lock and
  the protocol root's `.dual-ledger-owners/` lock through recovery and admitted
  lifecycle work. A busy owner explicitly refuses admission. Independent
  databases sharing a protocol root cannot race its lifecycle writes.
- Journal writes use a same-directory temporary file, flush/fsync, atomic replace
  and byte readback. Empty, malformed, incorrectly bound or unsupported-version
  journals, invalid intent rows and duplicate intent identities refuse recovery.
  They are not treated as empty pending work. Acknowledgement bits are retained
  observations; actual backend content is rechecked before an intent is cleared.
- Conflicting starts and terminal content refuse replay. Finalization can advance
  an existing running row. Supplied summary/artifact entries and explicit final
  timestamps must be observed in durable backend data. A success-shaped adapter
  return without that effect leaves the intent pending and raises an error.
- Each invocation rechecks durable pending work. A pending lifecycle blocks later
  lifecycle transitions for that session until its mirror can be verified.
- Nested caller inputs are copied before awaiting. Cancellation or timeout after
  admission drains the complete operation, including storage and telemetry,
  before propagating. Waiting for admission remains cancellable.
- SQLite primary retains explicit degraded mirror behavior when the secondary
  write raises an operational error; its pending intent and error observation
  remain. Protocol primary raises on that failure. Content conflicts, unverified
  effects and structural wiring errors do not become degraded success.
- Diagnostics use registered `E_DUAL_WRITE:<detail>` errors. Sync telemetry sinks
  run in an owned worker; returned awaitables run on the application loop.
  A missing sink uses the runtime event logger. Sink errors remain observable
  and do not change an already verified backend outcome.

## Migration
1. Replace imports of the removed adapter module with the application module.
   No compatibility forwarder is added. The runtime factory selects the new owner.
2. Supply repositories with absolute SQLite `db_path` and protocol `root` paths, or supply
   the explicit `protocol_root` constructor argument for a custom protocol adapter.
   Invalid primary-mode strings now refuse instead of silently selecting SQLite.
   Relative backend identities and target changes at later admission refuse;
   callers must resolve invocation-root inputs before constructing the coordinator.
3. Preserve journals and adjacent native ownership directories. An old
   `<sqlite-parent>/.orket/dual_write_intents.json` is unbound to a database pair.
   Only an explicitly versioned, valid empty legacy journal permits new admission.
   Nonempty or malformed legacy journals block admission and remain unchanged.
   Automatic attribution of those old intents to a new backend pair is unsupported;
   an offline, evidence-backed migration remains required before replaying them.
4. Repeated initialization is a durable recovery check. Callers must not rely on
   cached initialization to hide intents created by another cooperating owner.

## Limits and verification
- Installed regression diagnosis also exposed a governed-child teardown defect:
  a daemon buffered stdin read could hold Python's shutdown lock after workload
  failure. The reader now uses the raw descriptor on its existing dedicated
  thread. Framing, deadlines and host disconnect normalization are unchanged;
  an actual crashing-child test requires normal exit 1 and retained diagnostics.
  The original Windows timeout lacked child diagnostics, so exact attribution of
  that observation to this separately reproduced shutdown abort remains unproven.
- This is local cooperating-owner admission and verified recovery, not a
  transaction across SQLite and protocol files, hostile-writer fencing,
  authenticated history, power-loss recovery or arbitrary external-effect replay.
- Direct writers that bypass the coordinator do not participate in its native
  ownership protocol. A permanently stuck admitted operation can delay cancellation.
- The original ten failing counterexamples and subsequent source/native process
  observations are retained under `.tmp/c-dual-ledger/`. The canonical remediation
  plan owns current proof disposition: 1,193 source cases and eight fresh installed
  llama.cpp cases pass; installed Linux approval/resume deadline failures remain
  unresolved. This is not hosted CI, full-suite or whole-lane acceptance.

## Versioning
- Candidate core patch `0.6.5`; SDK stays `0.7.0a1`.
- Internal import, journal, callback execution and recovery behavior changes are
  breaking. Core `0.6.5` is retained as a local candidate checkpoint with the
  installed Linux gate open. Work-hours commits and tags remain local.
