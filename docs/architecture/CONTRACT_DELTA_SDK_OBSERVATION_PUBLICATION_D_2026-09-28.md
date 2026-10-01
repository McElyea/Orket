# SDK required lifetime-observation failure policy

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented after 0.6.114; scoped Windows source closing passed.
- Contracts: `SDK_WORKLOAD_PROCESS_LIFETIME.md`, `LOG_WRITE_SETTLEMENT.md`.

## Delta

Required lifetime publication precedes SDK result reading and adoption. Ordinary
publication failures selected typed uncertainty, but fatal native failures bypassed
that policy and native cancellation could select clean cancellation. Both paths
could remove an unadopted result exchange after failed required publication.

The existing SDK owner now contains that publication through the same native
worker owner and records the identity of a native failure. A failed native attempt,
including fatal or cancellation outcomes, selects `lifetime-observation` uncertainty
with its exact cause and retains the exchange without reading/adopting its result.
Successful publication interrupted only by its caller keeps the existing confirmed
cancellation/removal path. No second cancellation or process supervisor is added.

The observed event captures its workspace and pure built-in projection before
native admission. The public workspace was already captured before dispatch;
this is not a newly discovered public mutation race. Supporting uncertainty
captures its event inside the existing diagnostic supervisor and preserves its
exact `diagnostic_error` and typed note. Native timestamps remain native.

## Migration Plan

Callers already propagate `SdkSubprocessExecutionUncertain` without terminalizing
the control-plane run. They must retain that policy for these additional native
publication failures. A physically appended event is not result adoption, and
an unresolved exchange is not permission to redispatch or erase evidence.

The 15-case real-child opening observed eight failures and seven passes. Native
CancelledError, SystemExit, KeyboardInterrupt and BaseException, each with and
without repeated caller interruption, lost typed uncertainty and removed the
exchange. Ordinary failure, successful publication, caller-only cancellation,
timeout request, child error and missing-result guards passed. Receipt:
`.tmp/goal-20260928-sdk-observation-standalone-opening-v1-readback.json`.
Physical append and request/result bytes, independent process ancestry/reaping,
error identity, retained state and an actual subsequent command are required
closing observations. Controlled acknowledgement failures are not spontaneous
filesystem faults or hostile-code containment proof.

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

If closing exposes a policy regression, restore the SDK publication delta and
retain the failed observations. Preserve existing exchanges and establish process
termination before operator removal. Do not manufacture terminal results or
rewrite control-plane records to recover a passing test.

## Versioning Decision

Unpublished development change after 0.6.114; no version bump. Existing event
schemas and public call signatures remain. Exchange-removal failure precedence,
full-suite/installed/platform acceptance and actual-provider proof remain separate.
