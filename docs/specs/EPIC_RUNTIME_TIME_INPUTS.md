# Epic bootstrap and summary time inputs

Last updated: 2026-09-23
Status: Active contract; scoped acceptance belongs to the architectural-truth plan.

The standard `ExecutionPipeline` receives a `RuntimeInputService`. Epic bootstrap
captures one `utc_now()` value from that service before invoking
`capture_run_start_artifacts(now=...)` in its owned worker. Run identity and the
workspace snapshot consume this explicit value. Bootstrap must not bypass the
selected input service with a second implicit clock read.

The worker remains owned through repeated cancellation and timeout. Directory
publication retries preserve that captured timestamp. A worker failure remains
unresolved; published bootstrap files can precede interruption of ledger startup.
The publication budget, refusal and retained-evidence contract is
`docs/architecture/CONTRACT_DELTA_RUN_START_PUBLICATION_D_2026-09-19.md`.

Epic setup also takes one calendar observation before asset reads. Its separate
sprint capture, configured timezone and baseline ownership are defined in
`REMAINING_RUNTIME_INPUTS.md`. UTC capture precedes the owned timezone lookup.

Epic outcome observation and preparation/publication continue to use that
service's existing UTC input seam. Protocol-ledger event timestamps have their
own explicit `timestamp_factory` port; callers supplying controlled time must
configure both ports consistently for the behavior they are proving. Neither
injected fixture timestamps nor UTC subtraction prove monotonic elapsed time.

An existing immutable `run_identity.json` keeps its original start time when
read again. This change does not rewrite old identity, outcome, ledger or summary
artifacts and introduces no new schema or automatic historical repair.

Summary generation still refuses missing or negative intervals. The separate
generation error is retained; its fallback has `is_degraded: true` and
`duration_ms: null`, preserving the original status and failure reason. That
minimal degraded summary need not contain optional packet projections. It must
not manufacture a nonnegative duration or change a failed run into success.
These failure semantics are defined in `CORE_RUNTIME_STABILITY_REQUIREMENTS.md`.

This boundary does not guarantee a nondecreasing operating-system UTC clock,
explain historical clock reversal, make UTC a monotonic latency measurement,
or close the remaining explicit-input and clock inventory under D. Default
`RuntimeInputService` behavior remains the host UTC clock; controlled clocks
are caller-provided inputs rather than hidden global overrides.

The 0.6.102 turn-artifact migration explicitly forwards this same service's
UTC callback through pipeline wiring and Orchestrator into TurnExecutor/parser.
Parser completion samples after its artifact batch. New local/control-plane
checkpoints share one entry-captured timestamp; retained records keep historical
time. Tool-approval request and hold publication likewise reuse one explicit
turn-clock sample. No new RuntimeConstructionInputs field or lower-level default
clock is introduced. The implementation contract is
`TURN_ARTIFACT_PUBLICATION_CONTRACT.md`; the architectural-truth plan and its
checkpoint receipts own acceptance and publication status.

Guard-rejection pending requests extend explicit time selection in 0.6.103.
After synchronous gate-policy resolution, the orchestrator samples its existing
`turn_clock` once and captures the existing reservation publisher object before
awaiting pending-row creation. The pending repository still owns request identity.
The row's `created_at` and `updated_at` and any hold's `creation_timestamp` share
that sample. Replacing the orchestrator's clock, pending repository or publisher
slot during the admitted row operation does not redirect that request.

A missing publisher slot or selected `None` keeps row-only behavior. A present
publisher must provide the required method: lookup and invocation occur on the
captured object after the pending row returns. A missing or noncallable method
propagates its error, as does later publication failure; the durable row remains.
There is no retry, rollback, atomic row-plus-hold transaction, new clock or resource
owner. Capturing the publisher object does not freeze its internal mutable state.
Accepted gate policy, request/hold schemas and guard-handler failure ordering remain.

The matched local controls compose a real pipeline, SQLite repositories and the
public success handler with a controlled result and final failure sink. They do not
establish provider inference, full epic dispatch, cancellation ownership or general
replay behavior. The migration and validation obligations are in
`../architecture/CONTRACT_DELTA_GUARD_REQUEST_INPUTS_D_2026-09-23.md`.
