# Kernel control-plane publication inputs

Status: Active contract; explicit runtime state, input and lifetime ownership expanded in 0.6.77
Last updated: 2026-09-21

Each asynchronous public kernel admission, commit and session-end invocation
captures its request before calling the kernel or awaiting publication. Session,
trace, proposal, result claims and operator/attestation values used after a wait
remain the values selected at invocation entry.

Each direct control-plane admission, commit and session-end publication captures
its request, response and ledger items before its first await. Collection uses
the existing SDK immutable JSON value and produces detached, operation-owned
views for application effects. Nested caller mutations cannot replace proposal
or policy snapshots, change a commit result, supply later execution evidence,
or rewrite selected receipt digests and timestamps.

These boundaries accept JSON payloads. Non-finite numbers and unsupported object
types are refused by the existing immutable JSON codec before publication;
they are not replaced with fabricated values. Existing stable JSON inputs,
kernel digest rules, namespace checks, retry guards and terminal classifications
retain their behavior. Capture does not validate that a caller-supplied receipt
is authentic or enlarge the authority of that caller.

This contract does not make kernel in-memory state durable, make multiple stores
transactional, roll back prior kernel events, or reclassify claimed output as an
independently observed effect. Failure and cancellation preserve the existing
authority and ownership semantics. Other kernel clocks and runtime inputs remain
separate D obligations.

Acceptance retains before-change real-SQLite counterexamples for changed
admission snapshots, false-success commit publication and changed closeout time,
then proves both direct publication and the public engine path against held
repository operations. Source and installed proof also retain stable-input,
namespace, retry, recovery and terminal-authority regressions.
## Kernel public state ownership (0.6.76 implementation contract)

Synchronous Kernel action-path entrypoints capture their request JSON before
validation, hashing or state-lock waits. Admission, commit and approval state own
their stored values; event publication owns its body before hashing. Returned
admission, approval, cache and ledger observations are detached from retained
state, including nested dictionaries/lists. Caller mutation cannot rewrite
authorization, stored resolutions or historical event bytes/digests.

Credential issuance and commit share one pure accepted-admission/approval identity
rule. ACCEPT_TO_UNIFY permits progression; NEEDS_APPROVAL requires an APPROVED
record for the same session, proposal and admission-decision digest. Other
decisions refuse. Commit retains the existing admission-event precondition and
serializes authorization, same-key lookup, canonical-state change, event
publication and cached response under the runtime lock. Concurrent identical
commit keys return the same retained response and publish one commit event.

Existing key fields, response/reason vocabulary, packet1 approve/deny behavior and
caller-observed execution fields remain authoritative. These observations do not
prove actual connector execution. Event failure can follow state mutation; no
durable or all-or-nothing state/ledger transaction is introduced. Deliberate access
to an explicit owner from trusted Python is not contained. Other synchronous
owner and clock/environment inputs remain separate D obligations. Credential expiry
continues to be observed after consume-lock acquisition as specified in
`KERNEL_POLICY_INPUTS.md`.

The application owns affected async Kernel calls through workers and retains
their required control-plane publication through cancellation, repeated
cancellation and caller timeout. Caller completion waits for admitted work and
publication to settle; worker/publication failure remains visible. Cancellation
can therefore follow an already-published state transition and cannot imply no
effect. Observation-only workers also settle before cancellation returns.

One immutable application environment snapshot is captured before worker
admission and carried through the owned continuation. Nested composition reuses
that snapshot; explicit empty environment is authoritative. Scoped context is
reset at exit and cannot leak into another invocation. Policy/key composition
consumes the snapshot and passes explicit values to pure decisions. It is never
selected from HTTP JSON. This preserves policy capture when synchronous calls
move off the event loop; it does not make every runtime environment input owned.

A failure after commit-event append but before response-cache publication can
leave an event that a retry repeats. Successful same-key reuse does not
establish crash/failure atomicity; inspect retained partial state first.

## Explicit Kernel runtime ownership (0.6.77 implementation contract)

One standard engine owns one `KernelRuntime` and one `KernelRuntimeLifetime`.
Ledger, admission, approval, canonical state, credential records, commit cache and
native lock belong to that runtime. Equal session identifiers in independent
applications do not identify shared authority. Kernel state remains volatile:
replacing an application creates empty Kernel state even if its durable SQLite
control-plane records still exist. No restart reconstruction is implied.

`KernelV1Gateway` binds its runtime for native calls. Async engine mutation and
approval calls bind the same owner through the existing application lifetime
supervisor and owned worker/publication helpers. Close stops new admission,
retains admitted publication (including required same-task nested approval reads),
then closes the native owner before other engine resources. Inherited context in
a different child task cannot bypass closed admission. Close joins native lock
holders off the event loop. Worker/publication failure and repeated close failure
remain visible; interruption is not evidence of rollback.

Direct action-path callers must create an explicit owner, bind it with
`owner.activate()` and close it after related work. Async direct embeddings can
use `async with KernelRuntime.open() as owner` and must retain every worker they
start. This convenience context closes the native owner; engine publication
supervision belongs to `KernelRuntimeLifetime`. Unbound calls and closed owners
refuse; there is no default singleton, global-map alias or reset-test hook.
Synchronous native close and gateway invocation refuse a running event loop;
use the engine's async methods or an owned native worker. Custom engine gateways
must expose their owned `runtime`; direct calls bypassing the composed gateway
do not select the engine's state. Trusted Python remains outside containment.

At owner construction, clock, secret-token and credential-id callables are
selected from `RuntimeInputService`. Later replacement of that source object's
methods cannot replace these selected ports. Frozen UTC `KernelObservation`
values may be passed explicitly to projection, admission, approval resolution,
commit and session-end runtime entrypoints; event publication receives an
explicit timestamp. Events from one transition share its observation. Credential
issue/consume retain their typed inputs; default consume captures its key before
validation and observes expiry only after acquiring the native lock. Existing
environment capture and exact authority checks remain in force.

Validator filesystem/policy caching and UUID inputs, complete decision-node and
adapter classification, and other async owners remain D work. This scoped
contract does not establish durable Kernel transactions, hostile Python/OS
isolation, per-user API authorization or whole-lane acceptance.
