# Outward run admission

Status: Active contract; original admission accepted, shared-authority acceptance in progress
Last updated: 2026-09-13
Owner: Orket Core

## Atomic admission

`OutwardRunService.submit` owns initial admission through the existing
`OutwardStoreUnitOfWork`, shared with the API's approval service. After acquiring
the SQLite writer lock, it checks existing run identity and active namespace
ownership, then inserts the run and its `run_submitted` event in one transaction.
The event and the BT-2 ledger head participate in that transaction. The current
shared-authority candidate also admits the catalog workload, run/attempt and
immutable snapshots through `docs/specs/OUTWARD_RUN_AUTHORITY.md`.

Concurrent application instances submitting different run IDs to one active
namespace admit one run; the other receives HTTP 409. Concurrent submissions of
the same ID return the same retained run and publish one initial event. The
existing run-ID idempotency contract remains: a retry returns the accepted run;
it does not replace its task, policy or namespace using a new request body.

Failure or process death before commit leaves neither initial admission nor event.
A retry may then submit normally. An older run missing its admission event remains
inspectable but submission reentry refuses with `E_OUTWARD_ADMISSION_EVENT_MISSING`.
It does not synthesize missing historical events from the current run projection.
Existing generation-zero quarantine and ledger-integrity refusal remain active.

The original admission repair changed no persisted schema. The shared-authority
cutover adds existing control-plane records in the same outward database; explicit
migration preserves old native history. The namespace guarantee
covers callers using this application unit of work on one SQLite database; it is
not filesystem-target isolation or a fence for arbitrary external SQL writers.

## Authority convergence

This transaction now feeds canonical catalog admission and shared final truth.
`OutwardRunRecord` retains the protocol cursor; it does not mint another workload
identity or terminal result. The shared-authority contract names current-input
adoption for old generation-one histories. Its combined acceptance remains open.

Acceptance requires authenticated API conflict/rollback/retry cases, independent
application owners, native process interruption/restart and installed execution.
The original 122-case source and four-cell installed admission envelope passed; retained
evidence is `.tmp/bt5-outward-authority/gate/`. This is local application/database
and native-process proof, with controlled models in the regression cases.
