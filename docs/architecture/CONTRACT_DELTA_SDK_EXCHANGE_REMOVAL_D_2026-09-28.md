# SDK exchange-removal failure and interruption policy

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; scoped Windows source opening/closing recorded below.
- Contract: `docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md`.
- Shared lifetime authority: `docs/specs/SHARED_IO_CANCELLATION.md`.

## Delta

The SDK runner already owns the private exchange's native removal through
identity checks, deletion and absence verification. Its old cleanup policy
converted only `OSError` and `RuntimeError` to typed uncertainty. Other native
failures bypassed that policy. Unexpected ordinary failure could reach the
executor's generic terminal-failure branch before the runner's capability report
was assigned. Native cancellation and fatal failures lost the typed cleanup
uncertainty without entering that ordinary terminalization branch.

Removal now records an actual native failure before reraising through the same
shared I/O owner. Native failure, including `CancelledError`, `SystemExit`,
`KeyboardInterrupt` or another `BaseException`, selects `exchange-remove`
uncertainty with that exact failure as cause. Non-cancellation admission failures
use the same disposition. The existing uncertainty diagnostic preserves its
exact secondary error and typed note; no generic diagnostic marker replaces it.

When the body already selected an error or cancellation, successful cleanup uses
the existing shared finalizer to discard only later caller interruption. The
original body outcome remains exact, including a valid child-reported error's
code and capability report. Actual native cleanup failure still takes precedence
as typed cleanup uncertainty. A local normal-completion flag selects this policy;
an unrelated exception handled by the awaiting caller does not select it.

When the body completed normally, caller-only interruption during successful
removal retains its previous cancellation/timeout behavior. Neither cleanup nor
diagnosis adds a new owner loop, retry, process supervisor or deletion algorithm.

Deletion can partially or completely apply before failure is observed. Retention
prevents another automatic removal attempt; it cannot restore deleted files.
The uncertainty's exchange path identifies the attempted resource and does not
promise its continued existence or complete request/result bytes. Native process
cleanup remains independently required; no uncertainty authorizes redispatch.

## Migration Plan

1. Public signatures and storage formats remain unchanged. Existing callers must
   propagate typed cleanup uncertainty without creating terminal no-effect truth.
2. Apply the opening alone against unchanged product, then repeat the same 22
   declared integration cases after the correction. The proof uses actual
   trusted SDK children, real private exchanges, native deletion holds and
   controlled failures, independent process ancestry/reaping, physical log/file
   observations, exact public exception identities and actual SQLite state.
3. Keep existing successful-body cancellation, exchange ownership, process
   lifetime/control-plane, required publication, supporting diagnostic and
   workload publication/manager guards. Observe the exact retained secondary
   protocol rather than treating any diagnostic note as equivalent.
4. Record observed opening/closing and source bindings in the active plan.
   Controlled native failure is policy proof, not a claim about spontaneous
   filesystem failure rates, hostile containment or actual model inference.

## Scope and limits

Preparation and result-reading failure policies, request/input capture, shared
owner semantics and provider selection remain unchanged. Before native dispatch,
successful cleanup preserves the existing preparation failure without inventing
a child lifetime. An executor/task admission raising cancellation before callback
entry is outside the callback's native-failure distinction. No general provenance
detector for all cancellation sources is introduced.

## Observed source proof

The unchanged-product opening reports **16 failed, 6 passed** in 53.18s,
with 5,615 unchanged Git-visible inputs. The corrected source closing passes
**176 cases** in 238.87s, with **5,616 unchanged inputs**, including all 22 new
cleanup cases and existing exchange/process/control-plane/publication/manager
guards. Real Git-installed manager cases retain EXECUTING state after native
cleanup uncertainty. Actual SDK children, private exchanges, native removal,
independent process readback and SQLite establish live local behavior; supplied
workload code does not establish actual model inference or hostile containment.
Path primary, result success. Evidence:
`.tmp/goal-20260928-sdk-removal-{opening,closing}-v1-*`.
The closing also includes the six unchanged run-start/policy selector modules
before the separately reviewed captured-import change. Installed packages, Linux,
whole-lane gates and provider acceptance remain separate.

## Rollback Plan

If exact outcomes, worker settlement or retained control-plane state regress,
revert this bounded runner/control/contract delta together. Keep failed evidence,
inspect remaining files and establish process termination before operator cleanup.
Do not recreate or erase an exchange to claim rollback or safe replay.

## Versioning Decision

Unpublished development candidate after 0.6.114; no version bump. Scoped source opening/closing is recorded below. Current installed/platform
acceptance, complete D closure and release readiness remain unverified here. Existing event fields and diagnostic protocol stay intact.
