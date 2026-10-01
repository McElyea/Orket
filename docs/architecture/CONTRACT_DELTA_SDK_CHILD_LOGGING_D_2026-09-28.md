# SDK coroutine workload logging composition

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented after 0.6.114; actual-child source closing passed; no version bump.
- Contracts: `SDK_WORKLOAD_PROCESS_LIFETIME.md`, `LOG_WRITE_SETTLEMENT.md`.

## Delta

The native SDK child already admits coroutine workload results via `asyncio.run`.
Its synchronous capability wrappers log on their caller's thread. Within a
coroutine workload, a missing application binding could therefore replace both
admitted capability receipts and expected policy denials with logging preparation
refusal. The existing host accepts this coroutine shape; the SDK's separate
Workload Protocol and synchronous convenience helper are unchanged.

For a coroutine result only, native child composition prepares the existing
logging owner from the existing native input selector, then binds the value in
the task that awaits the workload. Failed preparation closes the unadmitted
coroutine. Existing capability ExitStack ownership, error mapping, result
serialization and parent native supervision remain authoritative. Synchronous
workload execution and non-coroutine-awaitable rejection are retained.

Capability APIs remain synchronous. The change does not authorize native-only
model/memory bridges on the loop, change capability admission or instantiate a
fallback model. Optional logging return remains admission only, with no added
child shutdown frontier or durable-log promise.

## Verification and limits

Ten actual-child integration controls use the public SDK subprocess
runner, its unchanged request exchange, native supervisor and result adoption.
Six sync/async variants assert admitted built-in static model results, denied
memory writes and post-capability workload failure. Two controls retain the
existing coroutine-factory shape and rejection of a non-coroutine awaitable.
Every case checks actual child terminal lifetime and removed exchanges; supported
cases assert exact authorization and capability receipts. No real provider is
selected and no logging call is mocked or disabled.

Two trusted-child startup controls inject native writer-start failure before or
after the actual thread start. They retain the coroutine for an exit-time physical
observation and require closure without body execution, exact child failure,
native process cleanup and exchange removal. They add no writer-join or flush claim.

The original eight-case opening had four genuine preparation refusals and four
fixture failures from reading an unpublished returncode field. V2 was not run;
review corrected its comparison to account for separately asserted event metadata.
V3 reads the actual delegated supervisor result and observes six failures/four
passes before correction. The two additional failures are missed preparation
attempts, not evidence that the old host leaked an admitted coroutine.
Receipt: `.tmp/goal-20260928-sdk-turn-composition-opening-v3-readback.json`.

All ten controls pass in the expanded closing below. Existing provider cleanup, native SDK
lifetime, capability/provenance and uncertainty controls remain required guards.
No broader SDK helper typing, installed-platform matrix or full-suite claim is
made by this change.

## Observed source closing

Windows Python 3.11 source closing passes all **464** selected cases in 207.12s,
with **5,605 unchanged Git-visible inputs** and one upstream Starlette warning.
The earlier combined closing passed 410 cases in 170.25s with 5,600 unchanged
inputs. The expanded run retains those cases and adds the SDK observed-publication,
standalone settings and existing construction guards. Evidence:
`.tmp/goal-20260928-captured-inputs-closing-v4-{inputs,readback}.json` and sibling
XML/log; earlier `.tmp/goal-20260928-input-composition-closing-v3-*`.
Proof is live local native/files/SQLite/child and loopback HTTP behavior with
declared supplied-model controls, path primary, result success. No actual model
provider, remote Gitea, current installed wheel or Linux proof is implied.

## Migration and rollback

No workload API or capability permission migration is introduced. Existing
coroutine-capable host execution gains its own logging composition; native-only
capability bridges retain their refusal. If closing exposes a host regression,
restore the child composition change and retain the failed proof; do not alter
capability receipts or erase retained exchanges to manufacture success.
