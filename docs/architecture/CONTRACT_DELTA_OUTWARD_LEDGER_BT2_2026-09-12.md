# Outward Ledger Retained Integrity Delta

Owner: Orket Core. Date: 2026-09-12.
Status: BT-2 implementation decision; native/copy behavioral acceptance passed on the recorded Windows/Linux matrix.

## Summary

Affected contracts are `docs/specs/LEDGER_EXPORT_V1.md`, the outward API and
frontend contract, outward event storage, offline verification, and the BT-1
transaction boundary. The canonical architectural-truth plan owns execution and
acceptance. This delta does not reopen the paused formal-proof extension lane.

## Delta

At the opening counterexample checkpoint, export and live verification called `_ensure_hashes`, which rewrote stored
commitments from the currently observed rows. Both traverse at most 5,000 events.
Audit identity was derived from that capped count. Export self-consistency does
not establish retained integrity, completeness or authenticity. BT-2 acceptance
tests must stay red while these defects remain; do not invert them to assert the
old behavior or add expected-failure markers. Native enforcement now follows
`docs/specs/OUTWARD_LEDGER_STORAGE_V2.md`; copied migration is implemented and the
scoped installed-wheel Windows/Linux acceptance now passes. Historical failures
and proof ceilings remain recorded in the canonical plan.

The selected implementation preserves `ledger_export.v1` order and hash recipes
and introduces versioned retained append commitments beneath that export:

1. **One durable append authority.** In the same SQLite writer transaction as the
   event and any BT-1 decision/effect projection, record its canonical event hash,
   immutable per-run append sequence, chain link and retained run head/count.
   Reject caller-supplied mismatched hashes; no ordinary read creates or updates
   commitments. Database failures roll back the whole publication transaction.
2. **Versioned retained chain.** Use a separately named v2 storage/anchor contract
   with explicit domain separation and sequence in its hash input. Reuse the v1
   canonical event hash definition. Retained sequence is allocation order under
   the writer lock, independent of `(turn, at, event_id)` and wall-clock order.
   New code must not reinterpret the old `run_events.chain_hash` field as this v2
   chain. Record exact schemas and hash inputs in the durable storage spec when
   implementing them; no unversioned algorithm change is admitted.
3. **Explicit v1 projection.** After retained integrity and snapshot completeness
   pass, derive the existing v1 order, chain and omission anchors in memory. This
   projection never writes back into storage. Its `ledger_hash` remains the v1
   export commitment. An added retained anchor is separately named and versioned;
   it cannot replace `canonical.ledger_hash` or silently change formal fixtures.
   A late event can change earlier positions in the v1 projection; it cannot
   reorder the retained append history.
4. **A single read snapshot.** Traverse every page under one read-only transaction.
   Query event count and the retained high-water head independently in that same
   snapshot. Verify sequence continuity, payload hashes, chain links, head and
   count, including empty and beyond-5,000 histories. Resource bounds must reject
   or disclose incomplete output. Returned row count alone proves nothing about
   completeness. Opening a verification path must not initialize or migrate an
   old database, insert audit events or create a missing database.
5. **PII export audit.** Commit each required audit event before opening the
   response snapshot. Allocate its identity within serialized append authority;
   concurrent requests and a frozen clock cannot collide. Verification does not
   call the mutating audited-export path. Filtered/redacted views retain the full
   snapshot commitment and omission anchors without claiming omitted-payload
   verification.
6. **Separate verification claims.** Report v1 export self-consistency, retained
   integrity and snapshot completeness separately. A runtime-generated assertion
   inside an export is not independently authenticated evidence. Offline v1
   verification continues to describe only that file and its disclosed anchors.
7. **Prior external anchor.** A retained anchor identifies its schema, run,
   append count and chain head. Verification against a prior independently kept
   anchor checks the corresponding prefix of the retained append history, even
   after later appends. A wrong run, future count or changed prefix fails. An
   attacker who rewrites both local rows and local heads can defeat local-only
   integrity checks; the external anchor detects changes to its committed prefix,
   not alterations beyond it. Signing/protected retention is a distinct boundary.

## Migration plan

1. Preserve original v1 exports byte-for-byte and retain the original database.
   New empty stores may initialize v2 append authority; populated histories must
   not be silently sealed by startup, inspection, export or verification.
2. The explicit offline command is `python -m scripts.governance.migrate_outward_ledger`,
   including retained SQLite backup digests, independent event counts, original
   hash status and restart checks. Its required `--writers-stopped` flag is an
   operator acknowledgement, not automatic process fencing. New output paths are
   mandatory; the candidate is never activated by this command.
   Verify every available v1 commitment against its original recipe and order.
   A mismatch rejects migration and preserves the corrupt input; migration must
   not repair it. Missing commitments require an explicit disclosed legacy import
   using `--allow-unsealed` or quarantine, never retroactive authenticity.
3. Any accepted legacy import records that its retained v2 chain begins at import
   time and preserves the prior provenance/uncertainty. Import cannot grant new
   approval, effect or model execution authority. Quarantined BT-1 histories stay
   quarantined. Preserve original v1 cells, including nulls, without a second writer.
   The complete SQLite backup includes committed WAL pages; its digest is the
   imported origin. Existing native anchors retain their original provenance.
   Schema validation, backfill and complete retained verification occur in one
   transaction. Corruption or interruption rolls that transaction back. Reports
   invalidate prior success before work starts, and failed or interrupted copies
   must remain inactive; restart uses new paths while retaining all prior evidence.
4. Prohibit mixed commitment writers. Uncommitted legacy rows or a mismatched
   retained head prevent new authoritative append/export for that run. A valid
   append boundary does not by itself certify every earlier payload; verification
   still checks the complete retained snapshot.
5. Validate mutation/deletion/order cases twice against identical logical database
   contents, counts 0/4,999/5,000/5,001, page boundaries, concurrent append and audit,
   redaction/filter anchors, external-prefix comparison, malformed commitments,
   copied migration, and the BT-1 crash/publication envelope. Run the real API,
   offline CLI and primary llama.cpp proof; preserve the existing formal fixtures
   and their original claim ceilings.

## Rollback plan

Stop dispatch and export on commitment or migration failure. Retain original
stores, imported copies, anchors, journals and receipts. Rollback cannot resume
the old mutating verifier, mix append writers, reseal corruption or re-execute an
effect to obtain a missing event. A previous binary may inspect its preserved
original database only within its recorded limitations and with dispatch disabled.

## Versioning decision

The retained storage/anchor contract advances to v2. The v1 export/hash format
remains a supported projection and offline compatibility surface. Final schema
and API metadata definitions accompany implementation in the durable specs and
current authority. No engine release/version bump is performed by this design
checkpoint; contributor release policy applies when committing for main.

Existing witness packages and outbound-policy filtering continue to consume the
unchanged v1 projection. Their successful mathematical checks are not proof of
retained-storage authenticity or new multi-turn/workload/formal admission.
