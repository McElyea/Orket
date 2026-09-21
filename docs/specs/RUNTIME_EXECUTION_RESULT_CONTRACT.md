# Runtime execution results

Status: Active contract; scoped BT-4 combined acceptance recorded in the canonical plan
Last updated: 2026-09-21
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

The `orchestrate_card` helper and collection-member supervisor admit synchronous
runtime construction through an owned worker. They retain construction through
cancellation and timeout. If construction returns an owner after interruption,
that owner is closed before interruption is reported and is never dispatched.
Construction failures remain visible; this does not recover resources that a
constructor acquires internally and then fails to return.

`orchestrate_card` selects explicit `RuntimeConstructionInputs`, or captures its
environment/root and asynchronously collects runtime settings before worker
admission. Bound settings and preferences remain authoritative independently;
unbound values use their selected persistence locations through an owned worker.
Locations and bound JSON values are retained before collection waits. Existing
preference migration remains owned by the settings service; this is not an atomic
transaction across independent settings reads. An unbound synchronous settings
read on an event loop remains an error. The helper does not load a second `.env`.
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
