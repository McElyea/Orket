# Governed turn terminal transactions

- Owner: Orket Core, architectural-truth BT-5.3–5.
- Date: 2026-09-14.
- Status: scoped source/installed/native proof passes; BT-5 remains open.
- Authority: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

A retained Linux turn reverses its wall-clock timestamps. Lease publication
correctly refuses the decrease, but the old closeout had already committed a
completed run/attempt and successful final truth. Controlled ordinary/protocol
turns reproduce that gap and interruptions at the run/lease writes: six failures
and four controls before repair, with actual file effects retained.

Finalization now reads current authority and closes terminal records plus resource
release under the existing transaction factory. Preflight closeout also owns one
transaction, including admission when needed and the recovery decision. No new
storage schema, timestamp relaxation, provider selection or automatic retry is
introduced. The service constructor requires the explicit transaction factory;
the standard factory supplies the same SQLite store as its record ports.

The six preflight tests now use real SQLite instead of in-memory repositories.
They exposed invalid abandoned-attempt records that the old test doubles never
validated on read. Abandoned attempts retain their terminal timestamp; failure
classification stays on the run-bound recovery decision. Failed/interrupted-only
attempt fields remain absent, preserving the existing schema's restriction.

Historical contradictory or invalid records remain preserved and unadmitted.
Repeated terminal/preflight closeout applies the common consistency validator
instead of silently adding a missing truth reference. Rollback means stopping
admission and preserving evidence; restoring the permissive writer is not repair.

The core remains an uncommitted 0.6.2 candidate. Downstream construction must supply
the transaction owner. Source, exact artifact and installed proof are recorded in
the canonical architectural-truth plan; this change does not close BT-5 or the
clock, recovery, cards admission and capability gates. The same 99 cases pass in
source and four installed Python/platform cells. Actual llama.cpp card CLI success
and expected attribution-failure flows match durable state and exit status;
all four contained governed turns retain released latest leases.
