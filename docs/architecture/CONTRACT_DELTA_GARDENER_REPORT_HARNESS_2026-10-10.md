# Contract Delta: Gardener report adapter

## Summary
- Owner: Orket Core
- Date: 2026-10-10
- Contracts: `GOVERNED_AGENT_TASK_SUBMISSION.md`, `GARDENER_REPORT_HARNESS.md`.
- Scope: accepted report-only portion of issue #1 and revised PR #2.

## Delta
The source adapter maps Gardener's report dispatch to the existing SDK
submission and host-owned structured report verifier. It replaces the proposed
second verifier/host feature, handcrafted fixture lifecycle and separate accepted
result projection with the public task path and retained iteration result.
Snapshots are immutable committed blobs with bounded complete inventories;
unsafe entries, dirty sources and discovery failures refuse. The adapter uses
the canonical provider default and native process-tree owner.

## Migration and verification
Existing runtime and low-level submissions remain unchanged. Operators install
the trusted report example and explicitly configure its catalog/model and source
wrapper. Original PR-only feature declarations are not supported releases and
are not retained as compatibility aliases. Both Quality selections retain native
adapter controls; live acceptance requires actual Gardener dispatch, llama.cpp,
durable inspect/replay and observed server teardown. Advisory content never
acquires factual or repository-effect authority.

## Rollback
Disable Gardener's configured command to stop new dispatch. Retain existing
input directories and SQLite stores for inspection. Removing the example does
not rewrite historical final truth or undo prior effects.

## Versioning
Patch 0.8.1; additive public report submission and source adapter. Existing
callers need no migration. Whole-runtime and cross-platform acceptance are not
claimed by this scoped release.
