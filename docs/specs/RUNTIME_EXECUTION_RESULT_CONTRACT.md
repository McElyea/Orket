# Runtime execution results

Status: Active contract; scoped BT-4 combined acceptance recorded in the canonical plan
Last updated: 2026-10-01
Owner: Orket Core

## Authority and scope

Named card/epic execution must return a typed application observation through
publication, finalization, orchestration and dispatch. A transcript is supporting
history and cannot establish success. The same result governs CLI output and exit
status. This contract covers normal return, retained failure, approval wait,
incomplete work, cancellation and unresolved publication/recovery observations.

Reuse `RunRecord`, `FinalTruthRecord`, `RunState`, `ResultClass`, evidence
sufficiency and residual-uncertainty vocabulary from the canonical control-plane
contracts. Do not introduce another terminal journal or infer status from log
text, transcript contents, a latest-path artifact, or exception-message parsing.

## Result observations

1. A result retains the public session identity, actual control-plane run/final
   truth records when available, a declared observation kind, durable evidence
   references, a diagnostic reason and the transcript projection.
2. A published result is produced only after the publication owner has verified
   the exact retained plan and all required effects. It retains a digest-bound
   publication reference. The recorded run, final truth and session outcome must
   agree; missing or contradictory evidence cannot become success.
3. Success requires confirmed publication, completed lifecycle, canonical success
   classification, satisfied completion, sufficient evidence and no residual
   uncertainty. Normal coroutine return, terminality or accepted card evidence
   alone is insufficient. Incomplete publication of successful control-plane
   truth remains an unresolved application observation.
4. Approval wait and incomplete work remain non-success observations. They do not
   invent final-truth records or mark an open run completed. The observation must
   distinguish the currently retained lifecycle from the caller's control outcome.
5. Cancellation retains `asyncio.CancelledError` semantics and carries the typed
   observation after owned cleanup. A cancelled caller does not prove that durable
   run state is cancelled, nor does it authorize releasing uncertain admission.
6. Unresolved execution or publication retains known identities/evidence and
   uncertainty. It cannot be normalized into a verified failed terminal state or
   a successful result. Errors before admission retain explicit error behavior;
   no admitted run or durable reference is invented for them.
7. Recovery returns the same kind of typed observation from revalidated retained
   evidence, including retained failures and approval denial. It must not execute
   work again merely to produce a result, or turn a failed record into a transcript
   that looks like success to its caller.
8. Collections retain the declared member set and typed member outcomes. Aggregate
   success requires every declared member to succeed; empty, missing, failed,
   blocked, cancelled or unresolved members forbid success. A collection summary
   is not a synthetic durable terminal record. Later phases must not be admitted
   on an aggregate non-success result. Ordered member session/build identities
   append `-member-<1-based index>` to the explicit group identities, so shared
   repositories cannot reset a prior member or bind different epics to one journal
   request. This cutover does not rewrite previously retained collection history.

## Transport and compatibility

The canonical `run_card` path and existing `run_epic`, `run_issue` and `run_rock`
wrappers carry typed outcomes. Repository callers must consume the explicit
transcript field when they need history, and the typed outcome when deciding
success or further side effects. Do not add list/dict emulation, dynamic delegation,
or another executor to preserve the old return shape. Approval resolution responses
include `runtime_result` when they resume an epic. Extension actions serialize the
typed result only after the success gate; unsuccessful continuation raises
`RuntimeOutcomeError` carrying the observed result.

CLI behavior:

| Observation | Exit |
| --- | --- |
| Verified successful result | 0 |
| Failed, blocked, incomplete, degraded, advisory or unresolved execution | 1 |
| Caller interruption/cancellation | 130 |
| Argument usage error | 2 |

Interactive EOF/explicit quit retains its existing successful command exit.
`--card`, `--epic`, legacy `--rock` and `python main.py` project the same named-run
outcome. Completion wording is emitted only for verified success. Failure output
identifies the run and diagnostic/evidence references without presenting a
transcript as result authority. Cleanup errors cannot preserve a success exit.
Typed cancellation output retains the observed run and evidence references after
cleanup, with exit 130 even when an interrupted collection's ordinary result
projection would be non-success exit 1. A generic interruption before a typed
observation is available cannot invent run identity or references.

## Public helper and collection runtime ownership

Canonical CLI, API host, child-pipeline and legacy-extension routes propagate
their selected complete construction-input object through the existing runtime
factories. Child construction uses parent inputs, then the wiring default, and
refuses when both are absent. Complete objects and legacy environment/root
selectors are exclusive where specified. Async-created runtimes enter the
existing close policy before their context body runs; required close failure
retains precedence over body failure. Exact migration, timing and ownership:
`docs/architecture/CONTRACT_DELTA_ROUTE_INPUT_PROPAGATION_D_2026-09-25.md`.

The `orchestrate_card` helper and collection-member supervisor admit synchronous
runtime construction through an owned worker. They retain construction through
cancellation and timeout. If construction returns an owner after interruption,
that owner is closed before interruption is reported and is never dispatched.
Construction failures remain visible; this does not recover resources that a
constructor acquires internally and then fails to return.

`orchestrate_card` selects explicit `RuntimeConstructionInputs`, or completes
`RuntimeConstructionInputs.capture_async` before admitting the separate runtime
construction worker. Complete default capture uses one retained native operation;
its worker selects cwd, environment and unbound settings location before held
settings reads. Supplied objects retain their identity without recapture. Bound
settings/preferences remain independently authoritative, including empty values.
The worker-start selection point and its context, migration, interruption and
non-atomic-snapshot limits are defined by `SETTINGS_INPUT_OWNERSHIP.md`; the capture
worker is not a second runtime owner. An unbound synchronous settings read on an
event loop remains an error. The helper does not load a second `.env`.
Collection wiring prepares a constructor from selected parent fields before
admitting its worker; it does not defer reading the mutable parent until later.
Runtime ports remain selected object identities, not serialized implementations.
Pipeline composition supplies that runtime's selected construction inputs to its
sandbox, webhook and orchestrator factories. Explicit per-call inputs take
precedence over the wiring service's default; absence retains its prior default.
An inherited wiring service without defaults cannot silently reselect ambient
paths or policy for an already captured child runtime.

Work and required close retain their existing failure semantics. Repeated caller
cancellation cannot release a running close. Cancellation during successful
cleanup is reported after cleanup; cleanup failure cannot preserve caller success.
Existing typed collection member identities and terminal-evidence rules remain.
The factory migration does not make every synchronous public constructor safe to
call on an event loop or complete the broader async-reachability inventory.

## Organization-loop ownership and selection

Async callers await `OrganizationLoop.create(...)` before `run_forever()`.
The factory captures root, environment and independently bound or persisted
runtime settings before owned configuration loading. Direct synchronous
construction remains a pre-loop API and refuses an event-loop thread before I/O.
The canonical `orket runtime --loop` uses the async factory.

Relative organization paths bind to the captured invocation root; the existing
missing-file fallback is `<root>/model/organization.json`. Configuration and
workspace paths, environment selection and the loaded department tuple remain
bound to that owner across later caller changes. Scans give ConfigLoader the
project root, not its `model` subdirectory. Each scan observes current authored
files; this is not an atomic snapshot across departments or scans.

Within each epic, the existing pure critical-path engine chooses the first ready
card. Across candidates, longer ready queues sort first, then higher normalized
numeric priority; ties retain department order and sorted asset order. The schema
normalizes named priorities before selection, so sorting cannot reinterpret a
numeric priority as an unknown named label. This is the existing simplified
weight policy, not a claim of global optimal scheduling or dispatch de-duplication.

Owned configuration/scanning workers settle before cancellation or timeout is
reported; worker failures remain visible. Card construction uses the same shared
runtime owner as the public helper, including closure of a completed owner that
cannot be handed to its interrupted caller. Actual `run_card` results pass
`require_runtime_success` before continuation. Required close retains repeated
cancellation and cannot leave caller success after interrupted or failed cleanup.
The loop's running flag is cleared on exit. The ten-second idle wait and explicit
yield after a card remain unchanged; no forced worker-stop deadline is introduced.

## Runtime CLI construction and inspection

The canonical runtime CLI captures construction inputs after startup settings are
bound, resolves the workspace against that captured root, and admits the engine
through the shared owned factory. A completed engine that cannot transfer to an
interrupted caller closes before interruption is reported. Constructor failures
remain visible under the existing unreturned-resource limit.

Application inspection owns native path resolution, board/replay reads and
manifest output through cancellation, timeout and worker failure. Relative path
resolution binds its invocation root before worker admission. Required engine
close still gates return. Existing typed results, fatal/cancellation exits and
artifact-only replay classification are unchanged. Printed manifest fragments
are not rolled back after interruption.

This does not complete API read migration, all mutable inspection inputs or the
full async inventory. Interactive-driver ownership is specified below.
Argument declarations moved to a grouped module without changing their grammar.

## Interactive driver lifetime

Async embeddings await `OrketDriver.create(...)`; direct synchronous construction
is a pre-loop/worker API and refuses a running loop before I/O. The async factory
captures invocation root, environment and runtime settings before owned
construction. Relative project roots bind to that captured root. Injected port
identities are retained; their internals and authored files are not frozen.

A returned driver owns its provider cleanup, including an explicitly supplied
provider. The shared runtime factory closes a returned driver if interruption
prevents transfer. The existing unreturned-resource limit still applies.
`close()` retains provider cleanup through repeated cancellation and exposes
failure. API chat and the interactive CLI use these ownership primitives; the
CLI uses its post-startup captured inputs and closes on EOF/quit, failure and
interruption. Cleanup failure cannot yield success.

The console worker owns an admitted blocking input read until line, EOF or
failure. EOF is a normal input result; pending cancellation still wins over
normal EOF. Native failures remain visible. No forced thread stop or new input
deadline is introduced. The driver does not close borrowed process stdin.

## Model-stream workload lifetime

Builtin model-stream execution closes its invocation iterator before publishing a
commit or returning. Retained interruption and visible cleanup failure are defined
in [Model-stream lifetime](MODEL_STREAM_LIFETIME.md). Transport/client evidence is
tracked separately from the iterator boundary.

## Verification and limits

Required proof includes actual successful and unsuccessful workloads through the
public runtime and CLI; approval wait/denial; incomplete work; cancellation;
publication/recovery interruption; collection outcomes; and installed execution
outside the checkout on Windows/Linux Python 3.11/3.12. Compare CLI exit and
narration against retained session, control-plane, publication and acceptance
evidence. Use deterministic fixture models for boundaries and separate live
llama.cpp success and unsuccessful flows. Mocked finalizer returns are contract
tests and cannot establish runtime truth.

Command lifetime and connector timing retain their separate contract boundaries.
Scoped BT-4 acceptance does not establish broader host-death, unregistered-worker
or remote-effect recovery; typed results must preserve their uncertainty. Current
implementation/proof status lives in
`docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`.

## Governed-run demo native ownership

The direct asynchronous run, inspection and replay entrypoints retain each admitted
native operation through repeated cancellation or timeout. Scenario/workspace paths
bind before the first owned wait; native resolution, directory observation, file
open/read/write/close and result-path rendering execute through the shared native
I/O owner. Native failure takes precedence over concurrent interruption; scenario
read failures retain the existing ValueError envelope and native cause.

An interrupted operation settles before its caller returns and does not admit later
publication stages. Earlier evidence files or a partially completed bundle may remain;
a failed call does not return a successful execution result. Inspection/replay read
retained evidence without executing recorded actions. Approval-gated and denied
actions remain unexecuted. This is operation ownership, not a bundle transaction or
handle-bound filesystem confinement. Installed/platform acceptance is separate from
the local source controls in `tests/integration/test_governed_demo_ownership.py`.

## Marshaller artifact and ledger publication

Artifact/ledger writers bind their relative construction roots lexically once.
Each publication captures its destination and serialized JSON before a native wait.
The existing compact JSON, UTF-8/LF output and hash algorithm remain authoritative.
`write_check` captures its summary before directory creation; interruption of an
artifact operation settles that operation without admitting later files.

Ledger append retains one directory/append/close/digest-adoption attempt through
interruption. Successful native append adopts the digest before caller cancellation
escapes; native failure takes precedence. Returned records are detached JSON values
matching the physical ledger, including JSON array normalization. Resume retains
native existence/read/close with its captured path. A failed append can leave bytes;
its writer does not claim a new digest. Inspect retained evidence before recovery.
Sequence allocation timing remains unchanged. This does not add concurrent-writer
serialization, cross-process exclusion, whole-run rollback or automatic repair.

Marshaller file commands capture workspace/request/proposal paths, the proposal
sequence, allowed paths and fallback actor identity before their first wait.
List/inspection/replay/promotion retain each native metadata/read/write operation.
Promotion resolves relative repository inputs against its admission directory.
They share the artifact module's native JSON/text operations; existing sorting,
selection/refusal, JSON formatting and Git operation order remain unchanged.
Interruption after a promotion commit can leave that commit and a partial promotion
record without a ledger event. Replay writes its existing `replay_result.json` but
does not reapply the patch. These file-operation guarantees do not claim cancellation
or descendant cleanup for the separate marshaller process adapter.

Attempt execution detaches proposal/request values, binds repository/artifact roots
and captures its policy and artifact owner before publishing the proposal. Native
repository existence, clone removal and tree-digest observation use shared ownership.
Cancellation after a removal can leave the prior clone absent; interruption during
digest observation leaves the applied clone without a completion decision/event.
The marshaller workload captures consumed configuration, path list and fallback actor
before owned path resolution. No event or turn-finalize intent is emitted if that
resolution fails or its successful result is interrupted. Later event/commit authority
and the separate process-adapter limits remain unchanged.

## Governed-action quickstart native ownership

Quickstart captures the invocation workspace and constructs ledger writers with bound
paths. Create retains directory creation, truncate/write/close and construction;
emit captures serialized event values before opening the file and retains append,
close, hash and sequence adoption as one operation. Its returned event is a detached
JSON value. Load retains the complete read/parse/close attempt and existing malformed
line/object errors. Verification keeps its invalid-ledger result envelope.

The demo retains operator input and output callbacks through native settlement; these
synchronous callbacks now run in a worker. Custom callbacks must permit that invocation.
An interactive input has no added deadline: cancellation waits for the admitted input
call to settle. File write and readback verification use the same shared native owner.
Only successful verification permits the effect event. Interruption can leave a file
without that event or a terminal record; successful native ledger work still adopts
its hash/sequence before interruption escapes. Approval, denial, invalid input and
EOF outcomes remain unchanged. No callback, filesystem or whole-run rollback is added.
