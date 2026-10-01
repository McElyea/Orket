# Outward ledger observation ownership

## Summary

- Owner: Orket Core.
- Date: 2026-09-28.
- Contracts: `OUTWARD_LEDGER_STORAGE_V2.md`, `SHARED_IO_CANCELLATION.md`.
- Status: implemented; scoped Windows source controls pass; fresh installed proof pending.
- Effective version: uncommitted candidate after core 0.6.114; no version bump.

## Delta

Public ledger export/verification currently submits native path-agreement and
snapshot preflight work without retaining it through caller interruption. Lexical
SQLite contexts do not by themselves retain acquisition/close through repeated
cancellation. Reader path/page-size settings and external anchor mappings also
remain observable after native waits.

The existing snapshot reader constructs a retained reader from explicit database
path, page-size and borrowed-connection values. This does not clone arbitrary
instance state or promise subclass/instance-hook dispatch. Its standalone
read and direct borrowed-transaction read use the existing shared I/O owner;
application preflight uses the existing owned-thread entrypoint over captured
paths and reader. There is no new owner, proxy, transaction policy or read algorithm.
Standalone roots use the existing file-root policy, including explicit refusal of
drive-relative paths. A supplied connection stays borrowed, and its unused path
is not newly validated.

Successful reads cannot override caller interruption. Uncaught native failure
remains visible after settlement, including original storage wrapper causes.
Application export still raises its current validation envelope; verification
still returns its current invalid report when storage integrity cannot be read.
That invalid report is a failure observation, not successful retained verification.

The external anchor Mapping is detached before the snapshot await. The existing
scalar parser still validates after local verification. Non-mapping values retain
their former invalid behavior instead of being implicitly converted to mappings.
Schema, digest, integrity, authenticity and PII claim rules remain unchanged.

## Migration Plan

1. Public read/export/verify signatures stay unchanged. The concrete reader's
   `capture()` method retains standard settings for application admission; it
   acquires no resource and does not transfer borrowed connection ownership.
   The constructor's existing page-size limits apply to those captured settings.
   There is no new hook/proxy compatibility surface; the sole repository private
   paging fixture now holds the real SQLite cursor acknowledgement instead.
2. Retain the new opening module and paging-fixture seam migration, together with the reviewed
   wake-read helper dependency at its bound hash. Retain native metadata,
   acquisition/query/close, actual deadline, repeated cancellation, independent
   SQLite, root/settings/anchor rotation and error-precedence observations.
3. Retain the controls after product changes, plus existing snapshot paging,
   corruption, no-create/no-repair, resource, anchor, API/CLI and migration guards.
   Both Quality selections include them. Fresh installed/platform acceptance remains pending.
4. Initializer/unit-of-work ownership, PII audit publication, offline copying and
   workspace preparation are separate obligations. This does not close those
   remaining inventory rows or establish whole-D acceptance.

## Verification

The unchanged-product opening ran the 37 new cases and nine existing snapshot
cases: **31 failed, 15 passed** in 4.15s, 5,546 unchanged inputs. Failures comprise
21 premature-return observations, six input-capture failures, two new drive-relative
refusal requirements and two lost native failure observations. Six new cases and
all nine existing cases already passed; none was changed to manufacture a failure.
The revised cursor barrier still observes a real concurrent WAL append. No fixture
or teardown failure was identified. Opening evidence remains immutable.

The 18-selector closing passes **159 tests** in 64.98s on Python 3.11.14. Python
3.12.2 passes the same 46 focused cases in 3.89s. Each binds 5,547 unchanged inputs
and reports one upstream Starlette/httpx warning. The read-only native files/SQLite,
process/restart, API and borrowed-transaction paths are live local proof; mocked
CLI HTTP controls remain contract proof. Path primary; result success. The two
product files match between those runs, and 4,956 historical bindings remain intact.

Whole-package typing then exposed reuse of one local for captured `list[Path]`
and resolved `tuple[Path, ...]`. Naming the captured local `selected_paths` removes
both diagnostics without changing operations. The corrected source passes **57
tests** in 10.90s, including all 46 controls, ledger service and orchestrator
verification. Whole-package Mypy still fails with 652 errors in 193 files; no
passing type gate is claimed. Proof prefixes:
`.tmp/goal-20260928-ledger-read-opening-v2-*`, `-closing-v2-*`,
`-closing-py312-v2-*`, and `.tmp/goal-20260928-ledger-read-typed-closing-v3-*`.
The parity report is `.tmp/goal-20260928-recent-ownership-parity.json`.
No current installed-wheel, Linux, live provider or broader D acceptance follows.

## Rollback Plan

Drain admitted observations before restoring product and contracts together.
Keep retained databases, anchors and proof observations. There is no schema
migration or effect rollback; rollback reopens early-return/input-drift gaps.

## Versioning Decision

Patch scope after 0.6.114. Existing public payloads and SQL/paging algorithms stay
compatible. The explicit interruption and path-capture requirements are new;
broader behavioral acceptance remains in the architectural-truth plan.
