# Required ledger and webhook event input capture

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented after 0.6.114; scoped Windows source closing passed.
- Contract: `docs/specs/LOG_WRITE_SETTLEMENT.md`.

## Delta

Dual-ledger default telemetry omitted the factory workspace and borrowed event
values until native execution. The factory now forwards its absolute workspace;
the existing telemetry owner captures supported values before admission. Its
supporting diagnostic shares that invocation's workspace. Custom sinks retain
borrowed input identity, native invocation and returned-awaitable execution.
Failure classes, counters and standard-handler fallback remain unchanged.

Webhook required publication previously read the handler workspace and borrowed
payload inside its worker. It now selects and detaches them before admission
through the existing pure event-capture authority. Event-time selection remains:
the next event sees its own current workspace. Exact built-in admission refuses
custom hooks, cycles and non-finite values before native event work. Signed ASGI
JSON that projects a non-finite value into an event follows the existing required
publication failure boundary (500); the parser and HTTP validation are unchanged.

Both changes retain their existing native settlement owner. Already committed
ledger effects or webhook delivery deduplication are not rolled back by logging
failure or cancellation. Events cannot acquire lifecycle/replay authority.

## Migration Plan

Direct dual-ledger constructors must supply an absolute `workspace_root`; no
implicit compatibility fallback is added. All 17 current direct constructor
uses in four test consumers are migrated. The public factory signature and
webhook call signatures are unchanged. Custom event conversion belongs before
the required publication boundary; no new conversion hook is admitted there.

The opening selection retained 11 dual-ledger failures and one passing custom
sink control, plus 11 webhook failures and two passing physical-refusal controls.
These are source integration observations in the larger 41-case opening at
`.tmp/goal-20260928-runtime-input-batch-opening-v1-readback.json`; unrelated SDK
and registry fixture failures in that run are not producer counterexamples.
Closing must retain physical logs, SQLite/protocol readback, partial effects,
repeated interruption, exact native failure identity and current lifetime guards.

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

## Rollback Plan

If closing shows a contract regression, restore the product and corresponding
constructor consumers together and retain the failed evidence. Do not delete or
rewrite already committed ledger/dedupe state to simulate rollback. The existing
recovery owners remain authoritative.

## Versioning Decision

Unpublished development change after 0.6.114; no version bump or release acceptance.
Installed/platform, provider and complete required-producer proof remain open.
The direct constructor and stricter event-value contracts are explicit changes.
