# Standalone coordinator lifecycle

Last updated: 2026-09-18
Status: active bounded standalone coordinator contract
Owner: Orket Core

## Composition and storage

`orket.interfaces.coordinator_api.create_coordinator_app(...)` creates one
application-owned `CoordinatorRuntimeService` per FastAPI application. Importing
the transport module creates no app, card store, repository or durable directory.
The module-default `app`, `store` and control-plane owner aliases are retired.
For an ASGI server supporting factories, start with:

```sh
python -m uvicorn orket.interfaces.coordinator_api:create_coordinator_app --factory
```

Embedded callers retain the returned app and run its lifespan, or explicitly
await `app.state.coordinator.close()` when managing the owner themselves. Tests
and embeddings may supply a store, publication service and runtime input service.
The standalone coordinator remains separate from the main `/v1` API.

Composition captures the project root and a copy of the environment. The default
control-plane file is `<project>/.orket/durable/db/control_plane_records.sqlite3`.
An absolute `ORKET_DURABLE_ROOT` selects that root; a relative value resolves
against the captured project root. Later environment or working-directory
changes cannot rebind this owner. Directory creation is retained worker I/O on
the first admitted operation. A supplied publication service selects its own
repository and does not create the default directory.

Card state remains in memory. Separate applications have separate stores and
lifetime owners; operators must also select separate durable roots when they
need isolated control-plane histories. Sharing one SQLite path does not create
a multi-process coordinator or grant safe shared card ownership. Embedded
setup/reset operations on `owner.store` are outside request admission and must
not run concurrently with coordinator requests.

## Operations and inputs

The existing routes remain `GET /cards?state=open` and
`POST /cards/{id}/claim|renew|complete|fail`. Existing successful response fields,
non-hedged reservation/lease/resource summaries, hedged first-completion behavior
and expected 400/403/404/409 mappings remain. Request-schema validation uses 422.
Invalid nonfinite durations use 400. Complete/fail results must be canonicalizable
JSON; nonfinite or otherwise unrepresentable result values use 400.

Application captures nested complete/fail results before the first await and
the store retains a detached result after return. Each admitted operation takes
explicit UTC and monotonic-seconds observations from its runtime input service.
Store expiry and control-plane expiry publication use that same monotonic
observation; publication uses the captured UTC observation. These observations
are taken after serialized admission, before card effects. Nonfinite monotonic
values are refused before expiry effects. UTC order is not clamped: existing
lease timestamp rules still reject a reversed observation. An ordered test
clock does not prove the host wall clock reliable.

## Admission, interruption and failure

One application owner serializes transitions through store work, reservation and
lease/resource publication, and response projection. A queued renewal cannot
pass an admitted claim's unfinished publication. Expected store refusals remain
request errors and do not close the application.

Caller cancellation, including repeated cancellation, retains the admitted
transition until its workers and publications settle. Cancellation can follow
a completed mutation. No automatic rollback or retry is implied. An observed
transition failure takes precedence over cancellation.

Closing stops new admission with 503 and awaits the admitted transition. Queued
requests recheck admission before effects. Cancellation of a close waiter also
retains this drain; the owner closes after successful settlement. A transition
or its descendant cannot await its own owner close. The guarantee covers the
application transition, not transport delivery or arbitrary response streaming.

Unexpected transition failures are logged and retained. That owner refuses
later admission with 503 and cannot report successful shutdown. The failing
request returns 500 when a response can still be sent. Operators must inspect
retained state: the card store may have changed before a SQLite publication
fails. Existing authority-drift preflights still prevent the relevant store
mutation; failed claim promotion retains its existing invalidation/release
closeout. No endpoint clears failure or repairs state automatically.

## Proof ceiling

This is per-owner lifetime retention, with actual local HTTP/ASGI, thread and
SQLite proof. It does not establish a transaction across memory and SQLite,
crash recovery, cross-process fencing, arbitrary shared-root operation or a hard
shutdown deadline. Published control-plane history does not restore an in-memory
card queue after restart. Preserve the failed owner and durable observations for
operator reconciliation; starting a fresh owner is not evidence of recovery.

Migration and scoped evidence:
`docs/architecture/CONTRACT_DELTA_COORDINATOR_AUTHORITY_CD_2026-09-18.md`.
