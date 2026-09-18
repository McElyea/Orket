# Flow authoring authority and atomic saves

Owner: Orket Core
Date: 2026-09-18
Status: implemented; focused source and installed proof passes; whole C/D remains open

## Summary and delta

Affected contracts: `FLOW_AUTHORING_SURFACE_V1.md`, `API_FRONTEND_CONTRACT.md`,
the OrketUI host seam and object model, and `CURRENT_AUTHORITY.md`.

Retained real SQLite observations show two guarded writers both returning 200,
caller mutations after an awaited read becoming saved input, and a generated id
collision replacing an existing flow. The existing read/check/upsert is not an
atomic revision guard. Router composition also selects storage and ambient inputs.

The application captures a detached, schema-validated definition, generated
revision and timestamp before its first await. Storage separates insertion from
update. Insertion refuses an existing id (`409 flow_id_conflict`); a guarded update
uses the expected revision in the SQL predicate. At most one writer can consume a
particular current revision. A supplied empty revision is a guard, not omission;
omitted/null guards continue to allow an unconditional save of an existing row.
An update must replace the current revision with a different revision, even when
an injected generator repeats. `created_at` remains unchanged on update.

Application host inputs own flow ids, revisions, timestamps and rooted storage
composition. The router only translates requests, results and application errors.
Application also owns existing single-card run admission and scheduling; run
acceptance still does not claim execution completion or pin a transaction across
later card edits or execution. No additional topology becomes executable.

The side-effecting SQLite adapter prepares the parent directory off the event
loop and retains admitted operations through repeated caller cancellation until
commit/rollback and connection cleanup settle. A cancelled request may already
have committed; cancellation is not rollback proof. A cleanup/storage failure
takes precedence over cancellation. Validation alone does not create flow storage
or mint identities. Authoring drafts with semantic validation errors remain
persistable and cannot run, as before.

## Migration and validation

1. Patch checkpoint 0.6.17; public routes, success shapes and storage schema stay
   compatible. Stale/empty guards and create collisions now fail closed.
2. Internal `AsyncFlowRepository.save_flow` is retired in favor of distinct
   `create_flow` and `update_flow` operations; migrate all callers in this change.
   No compatibility shim or duplicate storage authority is introduced.
   The unused internal `resolve_flow_authoring_db_path` is also retired: the
   application builder selects the path and storage owns directory preparation.
3. Verify public authenticated ASGI authoring against real SQLite, simultaneous
   writes, captured caller inputs, collision refusal, stale/missing controls,
   injected time/ids, isolated roots and nonpersisting validation. Exercise owned
   database lifetime and cleanup on repeated cancellation with observed real SQL.
4. Run affected API/application regressions, current wheel/source parity and
   focused installed proof. Whole-platform/full-quality/provider acceptance
   remains a final C/D and whole-plan obligation; old matrices do not prove this
   new runtime. Preserve all preceding receipts and adverse observations.

## Rollback and state recovery

Rollback on broken public response parity, false success or lost database lifetime.
Revert runtime and authority together, preserving databases and proof. The schema
is unchanged; no destructive migration is needed. Reverting reintroduces the
documented overwrite defects and cannot be described as atomic save safety.

No flow history or cross-resource transaction is introduced. Clients inspect the
current revision after an interrupted request; later saves may supersede it.
Existing rows cannot reconstruct earlier revisions that were already overwritten.
