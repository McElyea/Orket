# Required epic publication log ownership

## Summary
- Owner: Orket Core.
- Date: 2026-09-28.
- Contract: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

## Delta
- Current behavior: three required completion log attempts use bare
  `asyncio.to_thread`; caller interruption can release the publication owner
  while its native log write continues.
- Changed behavior: the existing owned-I/O service retains each native attempt
  through repeated interruption. Native failure wins over cancellation; otherwise
  cancellation escapes after settlement. Store readback still precedes the log,
  and the existing publication transaction records progress only after success.
- The change closes a reached lifetime defect without adding another queue,
  event owner or journal. The existing log schema and event ordering remain.

## Migration Plan
1. No signature, schema or durable-store migration. Custom standard handlers on
   this already-native path continue to execute in a native worker.
2. Exercise each event with healthy, cancelled, timed-out and failed native append
   acknowledgement, inspecting real SQLite effects and matching reentry.
3. Retain existing publication/recovery and owned-I/O regression controls in both
   Quality selections. Supplied workload acceptance is not model/provider proof.

## Rollback Plan
1. A regression in publication or recovery requires repair before acceptance.
2. Reverting loses interruption ownership and reopens the recorded D defect.
3. Earlier store effects and diagnostic appends can persist on failure. Preserve
   the existing journal and acceptance receipts; never reset work to hide them.

## Versioning Decision
- Patch-level lifetime correction on the development candidate after 0.6.114.
- Effective date: 2026-09-28; publication/versioning is a separate checkpoint.
- No stronger delivery, rollback, provider or whole-D claim is admitted.
