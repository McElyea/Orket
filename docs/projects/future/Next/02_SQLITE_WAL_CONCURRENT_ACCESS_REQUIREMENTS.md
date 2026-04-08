# SQLite WAL And Concurrent Access Requirements

Last updated: 2026-04-07
Status: Future requirements draft
Owner: Orket Core

Related authority:
1. `docs/ARCHITECTURE.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/projects/archive/techdebt/TD04072026C/remediation_plan.md`
4. `orket/adapters/storage/card_migrations.py`
5. `orket/adapters/storage/async_repositories.py`
6. `orket/adapters/storage/async_card_repository.py`

## Posture

This is a future requirements draft, not active roadmap execution authority.

The first implementation slice should prove local SQLite behavior under concurrent card and agent access without changing the storage authority model or replacing SQLite.

## Problem

Orket uses SQLite for multiple durable local stores. Some current repository paths serialize writes with process-local locks, but those locks do not prove safety across independent repository instances, readers, writers, or future multi-agent workloads. WAL mode should reduce read/write contention, but it must be verified under the access pattern Orket actually uses.

## Goals

1. Enable SQLite WAL mode for the relevant durable local database initialization paths.
2. Prove concurrent readers and writers can operate against the same database file without `database is locked` failures under the target harness.
3. Prove independent repository instances behave correctly, not only a single instance guarded by one in-process lock.
4. Keep the change minimal and avoid a broad persistence redesign.

## Non-Goals

1. Do not replace SQLite with a server database.
2. Do not claim distributed multi-host concurrency.
3. Do not modify Gitea state authority unless the implementation directly touches that path.
4. Do not mask lock failures with retry loops that hide data loss or false success.
5. Do not treat a single serialized writer test as proof of concurrent access.

## Requirements

1. Initialization for touched SQLite-backed runtime stores must set `PRAGMA journal_mode=WAL` before ordinary schema work where practical.
2. The implementation must verify the effective journal mode and fail or report blocked if WAL cannot be enabled for the database under test.
3. The first slice must cover card storage and session/runtime storage at minimum, because those are the surfaces identified in the existing remediation plan.
4. If the implementation touches control-plane or run-ledger storage, those stores must receive same-change proof or be explicitly reported as out of scope.
5. The concurrent access harness must use independent repository instances pointing at the same database file.
6. The harness must include simultaneous readers and at least one writer.
7. The harness must verify final durable state, not just absence of an exception.
8. The harness must surface `aiosqlite.OperationalError` and `database is locked` as test failures, not skipped or degraded success.
9. Any fallback to non-WAL behavior must be explicitly reported as `blocked` or `degraded`; it must not be presented as primary success.
10. Changed install, bootstrap, runtime, or canonical test commands must update authority docs in the same change.

## Acceptance Proof

Required proof:
1. Integration test with at least 10 concurrent reader coroutines and 1 writer coroutine against one database file.
2. Integration test with two independent repository instances against the same file.
3. Verification that the target database reports WAL mode after initialization.
4. Regression proof that existing card/session repository operations still pass.

Proof classification:
1. WAL mode verification: contract or integration proof.
2. Concurrent reader/writer harness: integration proof.
3. Multi-instance state verification: integration proof.

Completion must report observed path as `primary`, `fallback`, `degraded`, or `blocked`, and observed result as `success`, `failure`, `partial success`, or `environment blocker`.
