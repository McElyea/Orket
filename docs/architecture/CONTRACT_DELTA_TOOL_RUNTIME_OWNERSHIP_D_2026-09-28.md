# Tool runtime invocation ownership

Date: 2026-09-28
Status: Bounded D3 correction implemented; Windows source proof passes, installed proof pending

## Boundary and defect

`orket.adapters.tools.runtime.ToolRuntimeExecutor.invoke` is the mapped tool
invocation boundary used by `ToolBox.execute`. The prior unguarded route combined
`asyncio.wait_for` with a raw `asyncio.to_thread` await. Cancelling that await could
let `invoke` publish cancellation or timeout while an admitted synchronous tool
continued its native effects. Repeated cancellation could also abandon the
wait-for cleanup of an asynchronous tool. Source inspection identifies these
paths; it does not establish a runtime result for the new controls.

## Selected contract

The unguarded invocation uses the existing shared `run_owned_io` owner with failure
preservation and one forwarded interruption. The timeout context surrounds that
owner await in the caller task. Both timeout and later caller cancellations reach
the same settlement owner; the child receives at most one forwarded request and
its cleanup remains owned. A synchronous tool runs under `run_owned_thread`.
There is no new settlement loop, dispatcher, rollback, forced thread stop or retry.
The timeout is an interruption request, so completion can exceed the configured
duration while native work or async cleanup finishes.

Successful native completion after interruption does not become successful tool
publication. A deadline without later caller cancellation retains the existing
`tool_timeout` result and optional log admission. Later caller cancellation keeps
cancellation outward. A raised native synchronous failure takes precedence after
settlement, including the callable's own `CancelledError`, `SystemExit`,
`KeyboardInterrupt` or other `BaseException`. A local failure slot populated only
by the admitted native callable distinguishes this failure from caller-only
cancellation. The runtime's existing handlers still translate `TimeoutError` and
the existing ordinary exception family into their existing result envelopes;
the remaining failures reach the awaiting public caller. The slot is read only
after the shared owner has settled the worker. Executor refusal before the
callable starts cannot supply this provenance; no broader admission-cancellation
classification is claimed.

The actual tool callable can return a `BaseException` object as a value. Private
tuple carriers keep that value from the shared owner's deliberate failure-value
interpretation. Dictionaries retain identity, other successful values retain the
existing `{"ok": True, "result": value}` shaping. Async function detection,
timeout conversion/default/clamping, error envelopes, and tool naming are
unchanged. A synchronous function returning an awaitable remains an ordinary
return value, as before. Arguments are trusted and borrowed; context is shallowly
copied with nested identities retained. This correction introduces no recursive
input capture or change to tool selection/provider authority.

An independently created caller `wait_for` can abandon its own wait when that
wrapper is cancelled. The original invocation task must remain pending and be
joined independently through native settlement. This contract cannot make an
arbitrary caller retain a task reference, and does not promise the external
wrapper itself stays pending. Effects can have occurred even when cancellation
or timeout is returned; neither outcome means no effect or permits blind retry.

This unguarded-route correction originally retained `_invoke_guarded` and the
mutation service's separate algorithm. The subsequent bounded guarded correction
is specified in `CONTRACT_DELTA_GUARDED_MUTATION_OWNERSHIP_D_2026-09-28.md`; its
own source/installed proof must be reported separately. This original opening and
closing remain evidence only for the unguarded scope.

## Verification and limits

The proposed integration controls use real file writes and the actual built-in
`ToolBox.execute("nominate_card", ...)` route. A held native append delegates the
real append before controlling acknowledgement. Controls check pending invocation,
SQLite responsiveness, exact failure/value policy, one native invocation, observed
effects and a healthy following tool. Async guards retain real cleanup and count
forwarded cancellations. Fatal controls run in isolated owned child interpreters;
the outer harness checks actual exit, origin and process reap. Test logging uses
explicit preparation and task-local binding, with frontier settlement only in
the fixture to observe optional timeout records. Production optional publication
does not acquire a new required-write guarantee or in-process writer stop API.

The 22 declared cases and existing card/reforger guards require unchanged-source
opening and changed-source closing. Static AST/Ruff checks are structural only.
No live provider, sandbox, remote effect, exotic task factory, infinite native
operation or process-crash guarantee is established. Canonical shared policy is
`docs/specs/SHARED_IO_CANCELLATION.md`; root-owned execution and installed proof
must record actual results before this proposed delta is accepted.


### Observed source proof, 2026-09-28

Opening: 17 failed and 82 passed across 99 cases, including 17 failures among
the 22 new controls. Native work escaped its caller and two fatal controls failed.
Closing: all 99 tool/guard cases pass as a named subset of a 335-case campaign
whose three unrelated new epic fixtures failed. That campaign is not a global
success. It retained 5,621 unchanged Git-visible inputs. Real file/nomination,
SQLite response, cancellation, cleanup, native failure identity and exception-value
controls passed on Windows Python 3.11 (primary, success at this bounded scope).
Evidence: `.tmp/goal-20260928-tool-runtime-opening-v1-*` and
`.tmp/goal-20260928-tool-runtime-closing-epic-opening-v1-*`.
Fresh installed/Linux/provider and guarded failure-precedence acceptance remain open.

## Portable external waiter observation

The first Windows Python 3.12 source campaign retained 805 passes and one fixture
failure in 389.23s (5,628 unchanged inputs): the external wait_for wrapper did not
abandon as the test assumed. Product source is unchanged by this correction.
The fixture now records the actual wrapper state after observed cancellation,
while retaining hard invocation-pending, physical-effect, native-identity and
settlement assertions. All 22 controls pass in the 364-case Python 3.11 and 94-case Python 3.12 source campaigns recorded in the model-stream input delta.
Python 3.11 observes an abandoned/cancelled wrapper; Python 3.12 observes a
retained wrapper receiving the exact captured invocation outcome. Both keep the
real tool pending until release and settled before returning. The original failed
806-case report remains evidence; it is not reclassified as a passing campaign.
