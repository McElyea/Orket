# Gitea CLI logging composition

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented after 0.6.114; scoped Windows source closing passed; no version bump.
- Contract: `docs/specs/LOG_WRITE_SETTLEMENT.md`.

## Delta

The reconciliation and worker-coordinator scripts invoked loop logging without
the explicitly prepared application context required by the logging contract.
A real state conflict could replace a reconciliation report with preparation
refusal; another worker's live lease could replace the intended acquisition skip.

Both CLI operation owners now select logging from their already-captured process
root/environment, prepare before HTTP adapter admission, and bind construction,
operation and cleanup in the invocation task. They use the existing queue/writer
and shared native I/O owner. Readiness and argument-policy refusals still precede
this preparation. Logging preparation failure is an additional explicit admission
boundary before HTTP resources are created.

Conflict classification, no-repair behavior, lease ownership, missing-workspace
policy, report locations, diff-ledger output and exit codes are unchanged. In
particular, configured fail-fast missing-workspace policy continues to refuse the
coordinator's existing workspace-less lease event. No workspace is invented to
hide that policy. Optional return remains queue admission, not persistence or a
new process shutdown frontier.

## Verification and limits

Nine integration controls use actual loopback HTTP and SQLite. Seven
execute exact current CLI script bytes in a contained project layout under the
existing native command supervisor, preserving parser/main behavior and checking
real process settlement. Two direct CLI operations hold actual HTTP, change cwd
and logging environment after admission, then verify captured log root/timezone,
physical append after the existing frontier, HTTP-resource closure and caller
context restoration. Native CLI controls do not claim daemon flush at exit.

Existing successful and interrupted Gitea HTTP ownership controls remain in the
closing selection. No new live remote Gitea or installed platform-matrix proof is
claimed. The opening reproduced eight failures with one passing guard. The first
closing passed 24 cases and exposed one fixture comparison error: coordinator
stdout omits the persisted diff ledger. The corrected fixture asserts exact
summary equality and independently verifies the sole initial ledger entry and
its digest; it does not weaken report or exit assertions. All nine controls and
the retained ownership cases pass in the expanded closing below.

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
