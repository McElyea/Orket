# Session snapshot inputs and epic closeout I/O ownership

## Summary
- Change title: Retain admitted snapshot inputs and native closeout operations.
- Owner: Orket Core.
- Date: 2026-09-23.
- Affected contracts: `docs/specs/EPIC_RUNTIME_TIME_INPUTS.md` and
  `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.
- Status: 0.6.104 implementation migration. The architectural-truth plan and
  checkpoint receipts own required acceptance and publication status.

## Delta
- Published .103 samples ambient time for provisional session checkpoints, reads
  nested snapshot values and the SQLite path after lock admission, and rereads the
  snapshot publisher after journal awaits. Selected closeout discovery, metadata,
  content reads and summary publication do not retain admitted native work through
  interruption. Summary payload rendering occurs after directory admission.
- Corrected matched source and installed openings reach 16 defect failures and six
  healthy controls each. The original opening retains 15 reached defect failures,
  one fixture failure and six healthy controls; no observation is overwritten.
- A checkpoint samples the existing selected `turn_clock` once. Snapshot storage
  captures its configured path and serializes nested configuration/transcript before
  the first lock await. Serialization errors therefore precede lock acquisition.
  SQLite `captured_at` remains an observational insertion timestamp; it neither
  replaces the selected checkpoint time nor supplies acceptance authority.
- Public publication and recovery capture the existing snapshot repository object
  before their first journal await. Snapshot effect, confirmation and final readback
  use that object. Capture does not freeze its internal mutable state. Old nullable
  or timestampless snapshots retain their existing schema and recovery semantics.
- The closeout repair must use the existing owned I/O primitives for each admitted
  native observation or file publication. It captures the required lexical roots,
  nested payload values and existing resource objects before suspension. An admitted
  operation settles, including closure, before cancellation or timeout returns.
  Cancellation must not admit later preparation stages or new file observations.
  Summary validation remains first; rendering completes before native directory
  creation and writing, so a serialization error no longer creates a directory.
  Captured summary artifacts/policy are JSON-shaped values, not opaque resources.
- Existing parsing, ordering, tolerant observations, packet projections, publication
  schema, phase authority and accepted BT-1 through BT-5 behavior remain. A native
  failure must retain its diagnostic mapping instead of being hidden by cancellation.
  Completing native work does not force preparation progress to commit afterward.

## Migration Plan
1. Compatibility window: no new public entrypoint, resource owner, clock fallback,
   schema, retry, rollback or cross-store atomic transaction. Required internal
   captured-input arguments must migrate with every caller; no compatibility shim.
2. Keep canonical implementation in the existing application and runtime owners.
   Root-level forwarding modules remain forwarding modules. Use the existing file
   root capture policy; lexical capture is not hostile-writer path confinement.
   Private runtime observation calls supply the selected workspace, ledger and
   cards repository explicitly. Test-only or dead omitted-input wrappers are not
   retained. Focused summary I/O leaves may be extracted without changing the
   public summary generation/publication signatures or adding an I/O owner.
3. Preserve both matched openings and their exact input copies, including the
   originally unreached composed fixture and the corrected protocol-ledger route.
4. Require selected-clock, nested-value/path/publisher mutation, healthy old-plan,
   actual held discovery/metadata/content/write, repeated cancellation/timeout,
   late native failure and physical file readback controls. The composed public epic
   must retain its durable prefix and recover without another workload dispatch.
5. Require unchanged independent SQLite <0.5s, canonical C, all prior case identities,
   frozen source and installed Windows proof, package parity and required CLI audits.
   Structural inspection or a passing mixed-package diagnostic is not acceptance.

## Rollback Plan
1. Failed acceptance, input drift, lost durable prefix, hidden native failure or
   changed accepted recovery behavior prevents publication.
2. Correct the unpublished candidate under a fresh proof phase, or revert bounded
   implementation and corresponding authority together; retain every observation.
3. No historical record repair, deletion, automatic retry or invented progress.

## Versioning Decision
- Compatible patch within the active 0.6 lane: 0.6.104, subject to required proof.
- Scope does not establish provider inference, Linux application acceptance, global
  logging shutdown, hostile-filesystem confinement, hard native deadlines, complete
  async reachability, full 89% coverage, CAP acceptance or lane completion.
