# Outward Ledger Retained Storage V2

Last updated: 2026-09-12
Status: Active implementation contract; native/copy behavioral acceptance passed on the recorded Windows/Linux matrix
Owner: Orket Core

The architectural-truth plan's BT-2 slice owns acceptance. The contract delta is
`docs/architecture/CONTRACT_DELTA_OUTWARD_LEDGER_BT2_2026-09-12.md`. This contract
preserves `ledger_export.v1`; it does not extend outward workload or formal-proof
admission. `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md` continues to own
authorization, effect execution and atomic terminal publication.

## Retained append authority

`OutwardRunEventStore.append` and its serialized `writer` context use
`OutwardEventAppend` in `orket/adapters/storage/outward_ledger_append_store.py`.
Application services own the transaction and audit identity. A borrowed BT-1
transaction is not committed by the event store. A standalone writer uses
`BEGIN IMMEDIATE`, and commits event, commitment and head together. An exception
propagates to the transaction owner, which rolls back the publication.

Schema migration 2 in the `outward_run_events` namespace creates:

| Table | Retained fields |
| --- | --- |
| `run_events` (existing) | Canonical event identity/payload and original v1 `event_hash`, `chain_hash` cells |
| `outward_ledger_commits_v2` | Unique `event_id`; `run_id`; positive `append_sequence`, unique per run; canonical `event_hash`; v2 `chain_hash` |
| `outward_ledger_heads_v2` | Unique `run_id`; `event_count`; v2 `chain_hash`; `origin_ref` |

Native append computes the canonical v1 event hash, stores it in `run_events`,
and leaves the old `chain_hash` cell null. Caller-supplied event hashes must match;
caller-supplied chain hashes are rejected. Sequence allocation follows the
serialized writer order. Payload JSON is captured once at that boundary before
awaiting any commitment write, so caller mutation cannot split hash and stored
payload. Before append, independent row/commit counts and the
retained tail must agree with the head. This boundary check is not a full-history
verification; every event is checked when taking an integrity snapshot.

The insert guard requires a matching v2 commitment and rejects replacement of
an existing event. Update/delete guards reject changes to committed event rows.
These guards stop old normal writers, including old repair-on-read code. An actor
with authority to modify the database schema can remove guards; retained checks
and external anchors address that distinct threat. No OS containment is claimed.

## Exact chain recipe

`event_hash_for` in `orket/core/domain/outward_ledger.py` remains the single v1
canonical-event hash definition. The v2 append hash is SHA-256 over UTF-8 canonical
JSON with sorted keys, compact separators and `ensure_ascii=False` for exactly:

```json
{
  "schema_version": "outward_ledger_append.v2",
  "run_id": "<run_id>",
  "append_sequence": 1,
  "previous_chain_hash": "GENESIS",
  "origin_ref": "native",
  "event_hash": "<canonical v1 event digest>",
  "stored_event_hash": "<original run_events.event_hash or null>",
  "stored_chain_hash": null
}
```

The final two fields bind the actual retained v1 cells, including absent values.
This permits an explicit import to preserve old cells without reinterpreting
their meaning. `previous_chain_hash` is the preceding v2 append hash or `GENESIS`
for sequence 1. The head count and hash identify the final committed sequence.
A known empty native run has count 0 and `GENESIS`.

`origin_ref` is `native` for newly admitted storage. `legacy:<64 lowercase hex
digits>` identifies a copied-store import tied to its retained backup digest.
The offline import described below implements this provenance boundary. Origin is
bound into every append hash; changing its provenance label changes the chain.

## Read-only snapshot

`OutwardLedgerSnapshotStore` opens the existing database with SQLite `mode=ro`,
enables `query_only`, and holds one read transaction while loading run projection,
independent event count, commitment count, retained head and all event pages.
It neither initializes schema nor creates a missing database. Keyset traversal
uses append sequence; the default page size is 1,000. A concurrent append belongs
to a later snapshot and cannot silently extend the current traversal.

Verification rejects missing/uncommitted rows, gaps, identity/hash/chain changes,
count/head disagreement and malformed stored records. It checks the original v1
cells through the v2 chain. Repeated verification does not change logical database
contents. Ordinary export uses the same read-only snapshot; it never repairs or
seals hashes. Filtered exports derive their omission anchors from the complete
verified snapshot.

The in-memory projection supports at most 100,000 events and 64 MiB of aggregate
UTF-8 `payload_json` bytes. Exceeding either limit rejects the snapshot with
`E_OUTWARD_LEDGER_SNAPSHOT_RESOURCE_LIMIT`. These are resource guards, not
performance acceptance or total-process-memory guarantees. No prefix is labeled
complete. Offline v1 verification also rejects counts above 100,000 and malformed
span bounds before traversing them.

## V1 export compatibility and claim limits

After retained verification, the application derives v1 order
`(run_id, turn, at, event_id)`, chains and omission anchors in memory. Null turns
sort before integer turns. V1 hash inputs and `canonical.ledger_hash` do not
change. A later append can sort earlier in the v1 view while retaining its own
later v2 sequence. The old v1 chain column has no new writer.

Exports add a separate `retained` object containing `anchor`, `integrity: valid`,
`snapshot_completeness: valid`, `authenticity: not_established` and
`authority: runtime_assertion`. These claims concern the source snapshot, not
omitted/redacted payloads or independent authentication of the export file.
Offline v1 verification reports `verification_scope: export_self_consistency`,
`retained_integrity: not_verified`, `snapshot_completeness: not_verified` and
`authenticity: not_established`, even when the input file asserts otherwise.

Live verification returns the v1 result vocabulary plus separate retained
integrity/completeness results and the retained anchor. Integrity rejection returns
`result: invalid` and diagnostics; inability to inspect storage, unsealed legacy
history or resource rejection reports retained integrity as `not_verified`.
Successful live inspection does not establish authenticity against an attacker
who can rewrite both local rows and local heads.

## External prefix anchor and API

An anchor has exactly these fields:

```json
{
  "schema_version": "outward_ledger_anchor.v2",
  "run_id": "<run_id>",
  "event_count": 10,
  "chain_hash": "<64 lowercase hex digits>",
  "origin_ref": "native"
}
```

Count must be a nonnegative integer, excluding booleans. Count 0 requires
`chain_hash: GENESIS`. Other counts require a SHA-256 hex digest. Extra fields,
unknown schemas, malformed origin or mismatched scope are rejected.

Authenticated `GET /v1/runs/{run_id}/ledger/verify` verifies the retained snapshot.
Authenticated `POST` to the same route accepts exactly
`{"external_anchor": <anchor object>}`. A supplied prior anchor checks the
corresponding prefix: report `matched_prefix` on agreement, `invalid` for changed
prefix/wrong scope/future count, `not_supplied` when absent, and `not_checked` if
the local snapshot cannot be verified. External mismatch makes the overall result
invalid while preserving the distinct successful local-integrity result.

The caller must retain the prior anchor independently. A matching anchor does not
prove the caller's anchor is trustworthy, nor does it authenticate the suffix
appended after that anchor. Signing/protected external retention is not provided.

PII exports first validate the retained history, then append their required audit
event under serialized append authority and open the response snapshot afterward.
The application derives audit identity from the allocated append sequence and
records the authenticated actor reference. Concurrent requests at a frozen clock
cannot reuse the capped event count. Verification never takes this audited path.

## Copied legacy migration

Creating v2 metadata tables does not seal populated legacy histories. Such a run
remains unsealed and cannot acquire new append/export authority. Historical
inspection and BT-1 quarantine remain distinct from current dispatch permission.
Do not delete, repair or reseal old rows to make verification pass.

The repository command `python -m scripts.governance.migrate_outward_ledger`,
run from the repository root, requires `--source`,
`--backup`, `--destination` and `--writers-stopped`. The last flag acknowledges
that the operator has stopped incompatible workers, including calls already
authorized to perform effects; it is not automatic process fencing. The source
is opened read-only. The command requires new backup and destination paths,
preserves existing files and SQLite sidecars, and never activates its candidate.
Existing v1 export files must be retained separately; the command does not alter
or discover them.

SQLite's backup API copies a consistent source snapshot, including committed WAL
pages, into the retained backup, then copies that backup into the candidate. The
SHA-256 of the complete closed backup is the imported chain's
`legacy:<backup_sha256>` origin. This digest identifies the retained snapshot;
it is not a claim that the raw source file alone included its WAL history.

One candidate `BEGIN IMMEDIATE` transaction validates canonical run/event schemas,
indexes, migration records and writer guards, applies required schema migrations,
backfills commitments and verifies every run before committing. Unsupported
schemas or custom triggers, partial v2 metadata and orphan events/commitments
are refused. Unrelated retained tables are copied without changing their rows.
Existing v2 histories are fully verified and keep their previous anchors/origins.

Eligible legacy rows are traversed in original v1 order across all pages. Each
non-null event hash and chain hash must match the unchanged v1 recipe; an empty
or mismatched hash is corruption and is never repaired. If either hash cell is
null, importing requires the additional explicit `--allow-unsealed` flag. The
new v2 commitments bind the original cells, including nulls. The command never
updates legacy event cells. Each imported run reports the event count, number of
unsealed events, available hashes checked, derived v1 chain and retained anchor.
Empty legacy runs receive a count-zero `GENESIS` anchor without invented events.
Both import and snapshot verification enforce the same resource limits.

The chain establishes integrity of the imported snapshot from import time.
It cannot recover an event already missing before the backup, prove historical
completeness against an absent earlier export, or establish authenticity.
Approval/effect/model authority is unchanged: generation-0 histories remain
quarantined, and an existing generation is preserved. Importing readable evidence
does not authorize a new model call or effect.

The stable default report is `benchmarks/staging/outward_ledger_migration.json`;
`--out` selects another stable path. Reports use the shared rerun diff ledger and
reject database/sidecar path collisions, including existing hardlink aliases.
`state: started` replaces any previous success before copying. Successful commit
reports `state: complete`, `observed_result: success`, and
`candidate_activated: false`. Refusal reports `state: failed`, a diagnostic and
`candidate_disposition: unverified_do_not_activate`, with nonzero process status.
A killed process may leave `started`; neither that report nor a failed report
admits the candidate. Retain the original, backup and failed candidate, inspect
the failure, and retry using new backup/destination paths. SQLite recovery rolls
back an interrupted transaction; the command does not overwrite or resume it.

## Acceptance boundary and rollback

Native integrity, copied migration, interruption/restart and actual resource
boundaries pass the recorded installed-wheel Windows/Linux Python 3.11/3.12
envelope. The canonical architectural-truth plan records its requirement audit
and retained evidence. This does not establish authenticity, capacity, untested
hosts/providers, core release approval or additional workload/formal admission.
Rollback stops dispatch/export, retaining original databases, copies, anchors,
journals and receipts. It cannot restore old hash-repair behavior or re-execute an
effect to manufacture a missing event.
