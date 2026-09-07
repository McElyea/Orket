# Governed Agent Loop V1

Last updated: 2026-09-07
Status: Active durable contract; bounded CLI/runtime Slices 0-5 implemented, continuous supervisor pending
Owner: Orket Core
Accepted requirements source: `docs/projects/archive/governed-agent-loop/GAL09062026-REQUIREMENTS/GOVERNED_AGENT_LOOP_REQUIREMENTS_DEFINITION_PLAN.md`

## Purpose

Define the first governed continuous-agent contract for Orket. The contract
allows one externally packaged agent workload to use one or more local-model
roles across bounded sequential iterations while Orket remains authoritative
for admission, continuation, budgets, effects, recovery, and final truth.

"Continuous" means the host supervisor may remain available and wake durable
work. It does not mean that a model or extension may run an unbounded inference
loop.

## Authority relationship

This contract narrows and composes the existing authority in:

1. `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`;
2. `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`;
3. `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`;
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`;
5. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`;
6. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`;
7. `docs/specs/TRUST_HANDOFF_PACKET1_V1.md`.

Shared control-plane nouns and enums retain the precedence declared by
`docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`. This contract does not create a
second run, effect, checkpoint, recovery, or final-truth regime.

The implementation plan is not semantic authority. Wire schemas and SDK
bindings implemented for this contract must conform to this document.

## Accepted first-slice boundary

The first slice contains:

1. one objective represented by one governed run;
2. one active attempt and one sequential agent iteration at a time;
3. explicit objective, acceptance, policy, capability, model-profile, budget,
   and recovery inputs;
4. one external SDK workload invoked once per admitted iteration;
5. zero or more fixed model roles inside that invocation;
6. host-governed effects and approvals;
7. durable evidence for every continuation and terminal decision;
8. a deterministic fixture path and an Ollama-backed local-model proof path.

The reference extension may use fixed `planner`, `actor`, and `critic` roles.
Those roles are advisory stages inside one workload invocation. They are not
independent agents, child runs, or permission to add parallel fan-out.

The first slice excludes:

1. dynamic role or agent creation;
2. parallel child agents or unrestricted swarms;
3. agent-controlled budget or capability expansion;
4. direct extension access to provider credentials, raw endpoints, Orket
   repositories, or effect executors;
5. automatic resume based only on saved process or extension state;
6. provider process download, startup, or GPU lifecycle management.

## Canonical workload and object mapping

The reserved workload identity is `governed-agent-loop` with contract version
`governed_agent_loop.v1`. It must enter through the sole workload-authority seam
in `orket/application/services/control_plane_workload_catalog.py`.
Bounded CLI admission is implemented and proven through deterministic and live
local-model paths. API admission, durable wakes, and continuous supervision
remain pending their separate proof gates.

The first-slice object mapping is:

1. `WorkloadRecord` defines the governed agent-loop executable contract;
2. one `RunRecord` owns the objective, resolved policy, resolved configuration,
   acceptance basis, budgets, and terminal truth;
3. one `AttemptRecord` represents a bounded execution generation between
   initial start or an explicit recovery decision and attempt closure;
4. each admitted agent iteration is one `StepRecord` within the active attempt;
5. each model call and extension invocation is evidence linked to the iteration
   step, not a new control-plane object type;
6. proposed and admitted mutations use existing `Effect`,
   `EffectJournalEntry`, reservation, lease, and approval authority;
7. checkpoints, checkpoint acceptance, recovery, reconciliation, operator
   actions, and terminal closure use the existing canonical objects;
8. the run closes through one `FinalTruthRecord`.

No `IterationRecord`, agent-owned run record, or extension-owned final record is
introduced in V1.

An iteration identity contains the parent run id, active attempt id, monotonic
iteration ordinal, and canonical step id. Retrying an entire iteration after an
attempt-ending failure requires an explicit `RecoveryDecision` and a new step
under the authorized attempt. It must not overwrite the prior step.

The existing extension execution path publishes its own run and final result.
An agent iteration must use an application-owned invocation adapter beneath
that independent-run lifecycle; it must not mint an unrelated extension run or
close the objective merely because the subprocess returned successfully.

## Extension trust and host capability channel

V1 supports reviewed extension code trusted by the operator. Python import
guards, manifest checks, and subprocess separation are authoring and lifecycle
controls; they do not isolate hostile code from the host OS account. Running
untrusted extensions would require a separately admitted OS isolation contract.

Agent model and memory requests use a bounded host capability broker. The host
retains providers, credentials, stores, budgets, and actual usage records. The
child receives public SDK proxies, a sanitized environment, and non-secret
context. It must not reconstruct raw providers from inherited configuration.

The mandatory manifest capability `agent.iteration.v1` names this broker-backed
protocol surface. The host materializes it from the retained invocation binding;
it is not an effect permission and cannot be granted through child configuration.

The broker validates each request against its retained invocation binding,
capability scope, active attempt, fencing generation, deadline, cancellation,
and remaining budgets. Child-supplied identity alone grants no authority. Frames
carry call identity and bounded payloads; malformed, late, or conflicting
duplicate messages fail closed. Diagnostic output has a separate bounded channel.

### Canonical host/child transport

V1 uses `agent_stdio_ipc.v1`: one subprocess-local, full-duplex framed protocol
over the child process standard-input and standard-output pipes. Each frame is a
four-byte unsigned big-endian payload length followed by one UTF-8 JSON object.
The encoded JSON payload may not exceed 1,048,576 bytes. The first slice permits
one in-flight capability call; later concurrency widening requires a contract
delta and resource-admission proof.

The parent sends the bootstrap frame and retains the binding between the child
process, invocation id, active attempt, fencing generation, capability scope,
budgets, deadline, and cancellation state. The child echoes the parent-issued
invocation id and uses monotonically increasing frame sequence and call ids.
Possession of copied identity fields does not grant authority: the parent also
requires the frame to arrive on the active child's bound pipe and revalidates
all retained state before dispatch. Replayed, stale, duplicate-conflicting,
out-of-order, unknown-version, or oversized frames terminate the invocation as
a protocol failure.

Parent-to-child messages are `bootstrap`, `capability_result`, and `cancel`.
Child-to-parent messages are `ready`, `capability_call`, `progress`, and
`iteration_result`. Protocol frames exclusively own stdout. Child diagnostics
use stderr, are drained independently, and are retained only to a bounded
256-KiB tail with an explicit truncation marker. Diagnostic bytes never become
protocol or completion evidence.

On cancellation, the host stops admitting capability calls immediately, emits
one `cancel` frame, waits a configured cooperative grace period no greater than
30 seconds, then terminates and awaits the child process tree. Broker disconnect
also denies new calls. Provider work that cannot be confirmed stopped retains
an uncertain capacity reservation. The existing request/result-file SDK runner
remains the generic-workload compatibility path and is not the agent adapter.

Memory writes and workload mutations are returned as proposals and may commit
only after the host validates the iteration result. Inference and host audit
writes may already have occurred when the child crashes; those costs and records
must survive independently of the child's final capability report.

The frame state machine is:

1. The parent persists dispatch intent, starts one child, and sends exactly one
   `bootstrap` frame with the `agent_iteration_request.v1` payload.
2. The child sends exactly one `ready` frame before any capability call,
   progress event, or result. Its payload contains only sorted unique
   `supported_protocol_versions` and `supported_contract_versions` arrays.
3. After a matching ready handshake, the child may send one in-flight
   `capability_call` at a time. The parent replies with exactly one matching
   `capability_result` or cancels/terminates the invocation.
4. The child may interleave bounded `progress` frames when no capability call is
   in flight. Progress never changes authority.
5. The child sends at most one `iteration_result`. A valid result ends normal
   child protocol output; any later child frame is a protocol failure.
6. `cancel` may be sent once after bootstrap. It stops admission of new calls
   immediately. A child result received after the retained cancellation epoch
   changes is stale and cannot be accepted.

Frame sequence numbers are strictly monotonic per direction, beginning at one.
Capability call ids are unique within an invocation. A byte-identical duplicate
may be recognized only as an idempotent transport retry while the original call
is still retained; a conflicting duplicate or reuse after completion terminates
the invocation. The parent matches frames to the retained child pipe,
invocation, attempt, fence, deadline, and cancellation epoch before interpreting
the child payload.

The first broker operations are:

| Operation | Child request | Parent result | Authority |
| --- | --- | --- | --- |
| `model.call.v1` | `agent_model_call_request.v1` | `agent_model_call_result.v1` with `agent_model_use_receipt.v1` | Host reserves budget, resolves the target, invokes the provider, and persists the receipt. |
| `memory.query.v1` | `agent_memory_query_request.v1` | `agent_memory_query_result.v1` | Host authorizes scope and returns bounded advisory memory with provenance. |

Memory writes are not broker calls in V1. They remain result proposals committed
only after iteration-result validation. An incomplete length header or payload,
invalid UTF-8/JSON, frame over 1,048,576 encoded bytes, aggregate output over the
issued budget, timeout while reading a frame, unexpected EOF, or invalid state
transition is `protocol_failed`. The host records interrupted publication and
any uncertain provider/effect state before considering recovery.

## Loop submission contract

The versioned submission must carry or reference:

1. objective and acceptance contract;
2. initial authoritative context and artifact references;
3. requested extension workload and supported contract version;
4. allowed capabilities and namespace scope;
5. resolved policy reference and digest;
6. total and per-iteration budgets;
7. completion verifier class and configuration;
8. requested model-profile roles;
9. recovery posture;
10. operator identity and provenance required by the selected start path.

Missing objective, acceptance, policy, budget, verifier, extension, or scope
inputs fail admission closed.

## Canonical wire-schema authority

The canonical Draft 2020-12 schema bytes are packaged at
`orket_extension_sdk/schemas/governed_agent_loop_v1.json` and exposed through
`orket_extension_sdk.load_governed_agent_schema()`. That one document owns the
following V1 object/version pairs:

1. `governed_agent_submission` / `governed_agent_submission.v1`;
2. `agent_iteration_request` / `agent_iteration_request.v1`;
3. `agent_iteration_result` / `agent_iteration_result.v1`;
4. `agent_model_profile_request` / `agent_model_profile_request.v1`;
5. `agent_model_use_receipt` / `agent_model_use_receipt.v1`;
6. `agent_model_call_request` / `agent_model_call_request.v1`;
7. `agent_model_call_result` / `agent_model_call_result.v1`;
8. `agent_memory_query_request` / `agent_memory_query_request.v1`;
9. `agent_memory_query_result` / `agent_memory_query_result.v1`;
10. `agent_effect_proposal` / `agent_effect_proposal.v1`;
11. `agent_progress` / `agent_progress.v1`;
12. `agent_usage` / `agent_usage.v1`;
13. `agent_cancellation` / `agent_cancellation.v1`;
14. `agent_stdio_frame` / `agent_stdio_frame.v1`.

SDK and host bindings must validate against these packaged bytes. Copies under
host-private packages, docs, or external extensions are non-authoritative.

## Agent iteration exchange

The host-issued iteration request must contain:

1. contract version;
2. run, attempt, iteration, step, and trace identity;
3. objective and acceptance references;
4. bounded authoritative context and prior verified-output references plus one
   host-materialized, digest-bound value for every objective, acceptance,
   context, and prior-output reference;
5. admitted capabilities and namespace scope;
6. admitted model-profile role requests;
7. remaining run and iteration budgets plus deadline;
8. accepted checkpoint and recovery references when applicable;
9. cancellation state;
10. extension configuration admitted from the manifest.

The extension result must separate:

1. observations;
2. advisory proposal content;
3. effect proposals;
4. claimed progress and evidence references;
5. completion recommendation and evidence references;
6. typed role or handoff proposals;
7. model and output usage;
8. normalized failure, blocked, or cancellation reason.

An extension result may recommend `continue`, `pause`, `stop`, or `complete`.
Every recommendation is advisory. A generic workload success flag means only
that the invocation returned a valid result; it never means the objective is
verified complete.

Unknown versions, malformed identity, unknown refs, undeclared capabilities,
unbounded inline content, or usage exceeding the issued budget fail closed.

V1 chooses bounded host materialization instead of a child-accessible reference
resolver. JSON content is digested over the SDK canonical JSON UTF-8 bytes;
UTF-8 and base64 content is digested over the exact encoded wire bytes. The host
still verifies reference ownership, provenance, existence, and trust before
materialization. Reference values and materialized entries must form an exact
one-to-one set with the declared kind; extra or missing values fail closed.

Effect proposals include complete bounded arguments or an immutable argument
artifact reference as well as their digest. The host verifies reference access,
digest, target namespace, and approval binding. SDK schema validation alone
cannot verify ownership or truth of referenced evidence.

## Model-profile contract

The extension first requests a host-defined model profile or capability class
for a named role. Each actual inference is a distinct bounded
`agent_model_call_request.v1`; the content and host receipt return through
`agent_model_call_result.v1`. Profile selection is not a model call. Orket
resolves and snapshots:

1. requested and actual provider;
2. requested and actual model identity;
3. prompt/profile contract;
4. context and output limits;
5. supported structured-output and tool-description posture;
6. timeout and cancellation posture;
7. capacity admission and health status.

Provider credentials and raw endpoint policy remain host-owned. Substitution is
allowed only when resolved policy permits it and the actual target and degraded
posture are recorded.

The deterministic integration uses fake host model capabilities. The first live
single-model and multi-model proofs use the existing Ollama provider path under
`docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. The multi-model
proof must resolve at least two distinct installed model identities across the
fixed planner, actor, and critic roles.

The implemented Ollama path resolves exact installed model identities with
provider auto-selection and model auto-load disabled. It fails closed when a
requested identity is unavailable, records actual provider/model identity and
measured provider usage, and does not imply policy authority for silent model
substitution.

Resolve agent targets through the existing provider-runtime target and
local-prompting profile authorities. Concrete installed model choices and
hardware limits are recorded at proof preflight; they are not implied by a role
name. Preserve existing `model.generate` behavior while adding the versioned
agent model surface.

## Continuation authority

After each iteration boundary, an application-owned deterministic governor
evaluates only durable recorded inputs.

1. Continue: `next_iteration_authorized=true` is published with canonical
   `safe_to_continue` posture and a new iteration step may be minted.
2. Pause: no next iteration is minted; the run enters `operator_blocked` and
   requires an accepted operator action before reconsideration.
3. Stop: no next iteration is minted and the run moves toward a terminal state
   and `FinalTruthRecord` publication.
4. Recover: no next iteration is minted until the existing recovery,
   reconciliation, checkpoint, and effect preconditions authorize it.

The extension, a model, a scheduler wake, or checkpoint presence cannot publish
`next_iteration_authorized=true`.

Continuation requires a valid recorded iteration result, reconciled required
effects, admissible context, unexhausted budgets, and no active operator hold or
unsafe condition. A pending approval uses the deterministic
`effect_approval_required` pause rule; an executed but unverified effect uses
`unresolved_effect_boundary` and recovery posture. These states are not
interchangeable. A model recommendation alone is insufficient. Logical
iteration ordinals and explicit observation/time inputs drive replay; replay
does not invoke providers or consult mutable state to fill missing evidence.

## Budget and stop-priority contract

Host-enforced budgets cover at minimum:

1. iteration count;
2. wall-clock deadline and active lease;
3. total and per-role model calls;
4. input and output tokens;
5. effect count and capability classes;
6. output and artifact bytes;
7. repair and consecutive-failure attempts;
8. repeated-state and no-progress thresholds;
9. per-role and total inference concurrency.

Every issued budget is an immutable `agent_budget_snapshot.v1` value with a
stable reference, digest, and one of the scopes `run_limit`, `iteration_limit`,
`run_remaining`, or `iteration_remaining`. The wire snapshot carries all nine
limit families above, including role and effect-capability allocations. Host
semantic validation rejects duplicate roles/capabilities, iteration limits above
run limits, per-role allocations above totals, and scope mismatches. Zero is a
valid exhausted or unused limit; optional capability budgets do not become
positive merely to satisfy schema shape.

The extension receives a read-only remaining-budget snapshot. It cannot expand
or reset any limit.

The broker reserves bounded input/output usage before dispatch and charges every
attempted call, including repair, timeout, and transport retry. Missing provider
usage is recorded as unknown with a conservative reservation, not zero. A token
estimate must name its source; a hard token guarantee requires a supported
counter and output limit. Child-reported totals cannot overwrite host records.

`usage_posture` is exactly one of `measured`, `estimated`, or `unknown`.
Measured and estimated usage require explicit token counts, including legitimate
zero counts. Estimated usage also names its source. Unknown usage requires null
counts. Host `charged_input_tokens` and `charged_output_tokens` are separate,
always-present non-negative counters, so unknown usage never becomes invented
measurement or a zero budget charge.

Cancellation requests provider cancellation and bounded child teardown. If the
provider cannot confirm inference stopped, retain an uncertain capacity
reservation and prevent oversubscribing replacement work. Host deadlines stop
new workload calls; bounded reconciliation, cleanup, and final-truth publication
remain possible under separate control-plane authority.

No-progress and repeated-state rules use versioned projections excluding
incidental timestamps and trace ids. Verifier-observed changes establish
progress; model claims do not reset counters. Pause does not reset a deadline or
replenish a budget.

If several conditions are present in the same unpublished decision snapshot,
the governor resolves them in this order:

1. unresolved effect boundary, policy violation, or required quarantine;
2. accepted operator cancel or terminal-stop action;
3. verified objective satisfaction;
4. expired deadline or execution lease;
5. exhausted capability or effect budget;
6. exhausted iteration, model, token, output, or artifact budget;
7. unrecoverable execution failure;
8. repeated-state or no-progress threshold;
9. advisory continuation when all required evidence and budget remain valid.

An already-published terminal record is never re-ranked. Insufficient evidence
for a completion claim prevents success; policy may authorize another bounded
iteration, require an operator, or close as `blocked`, but may not fabricate
evidence sufficiency.

This priority orders terminal interpretation, not cancellation delivery. A
cancel request always stops new workload dispatch promptly, including while
effect reconciliation is required; residual uncertainty remains recorded.
Verified satisfaction before exhaustion may establish success only from
admissible work and evidence, never from unauthorized late calls.

## Effects, approvals, checkpoints, and recovery

1. Extension-returned effects are proposals only.
2. Each proposal must carry capability, intended target, arguments digest,
   idempotency input, namespace, iteration lineage, and evidence refs.
3. Orket validates and translates an accepted proposal into the existing
   governed tool/effect path.
4. Proposed, approved, executed, observed, uncertain, reconciled, and narrated
   states remain distinct.
5. Approval-required work pauses before the effect and resumes only through the
   admitted runtime-owned approval continuation path.
6. An uncertain effect boundary blocks iteration continuation until the
   existing reconciliation authority permits a next action.
7. A checkpoint records state but grants no resume authority.
8. Recovery requires an explicit `RecoveryDecision`; checkpoint acceptance and
   required re-observation remain separate prerequisites.
9. Later iterations consume only verified effect observations.

The implemented bounded effect composition further requires:

1. one exact `issue:<issue_id>` namespace recorded on and shared by the run,
   request, step, approval, adapter context, proposal, and receipt;
2. `read_file` and `write_file` manifest capabilities are host-bound proposal
   vocabulary and cannot be instantiated from child configuration;
3. a stable proposal-derived approval identity, complete immutable arguments,
   a resume-forbidden pre-effect checkpoint, and the existing pending-gate and
   reservation authorities before an approval-required write;
4. an explicit operator resolution, post-effect observation and journal entry,
   an accepted resume-same-attempt checkpoint, and a separate operator resume
   action before another iteration;
5. denial publishes operator-terminal-stop truth without mutation; a matching
   target found after restart is reconciled and journaled without redispatch;
   failed or contradictory observation remains uncertain and blocks resume.

The first live mutation proof targets the existing issue-scoped `write_file`
approval path. Its exact issue namespace, target run/attempt, approval payload,
checkpoint, and effect lineage must be established by integration proof. A tool
name alone does not admit agent-specific namespaces or replacement-attempt
continuation. Any widening requires a narrower contract delta and updates to
the affected approval/start-path authorities before implementation.

Effect idempotency must be proven for the selected adapter and target. If a
write may have happened before its receipt was persisted, re-observe/reconcile
before retrying. A queue claim or stable id does not create exactly-once effects.

## Context, memory, and handoffs

Each iteration context must be reconstructable from durable references and must
apply deterministic ordering, truncation, redaction, byte/token limits, and
provenance.

Memory scopes remain distinct:

1. extension-private advisory memory;
2. role-private advisory memory;
3. explicitly shared team memory;
4. objective or project memory governed by existing trust policy;
5. authoritative verified records referenced from the control plane.

Raw conversation history is not authoritative state. Cross-agent transfer, when
later admitted, must use the existing trust-handoff boundary with capability
and budget narrowing. V1 fixed role handoffs stay inside one extension
invocation and remain typed advisory data.

Role-private means context filtering within the trusted extension. Roles sharing
one Python process are not security principals; no secret-isolation guarantee
is made between them. Host memory authorization binds scopes to the invocation
and never trusts a requested role label as independent authority.

## Operator and inspection contract

The operator surface must support:

1. submit;
2. inspect;
3. pause through canonical `pause_run`;
4. resume through `approve_continue` or `approve_degraded_continue` with valid
   preconditions;
5. stop through `mark_terminal`;
6. cancel through `cancel_run`;
7. approve or deny a pending effect through the existing approval surface;
8. non-mutating replay of a continuation decision.

Inspection must expose objective, run/attempt/iteration identity, wake and claim
state, requested and resolved model profiles, current budgets, active leases,
last verified progress, context and evidence refs, effect and approval state,
continuation basis, and terminal truth.

Operator-issued control commands are idempotent, authenticated, preconditioned
`OperatorAction` publications. Automated wake/admission decisions retain their
system provenance and must not fabricate an operator action. A rejected command
preserves prior state and emits a durable rejection receipt.

Pause records an immediate hold on new workload calls, then reaches
`operator_blocked` after the in-flight operation has quiesced or been classified
for recovery. It does not falsely claim an executing effect has stopped. Resume
rechecks policy, budgets, approvals, checkpoint acceptance where required, and
effect uncertainty; approval alone cannot clear another hold.

## Continuous supervisor contract

The continuous host component is an application-owned event-driven supervisor.
It may claim manual, API, scheduled, webhook, or recovery wake events from a
durable queue, subject to policy and capacity.

Each claim:

1. has stable identity and an expiring lease;
2. authorizes at most one bounded governor action at a time;
3. is idempotent across competing supervisor instances;
4. preserves uncertain effects and expired-claim truth across restart;
5. releases or expires without leaking tasks, subprocesses, or capacity leases.

A wake event does not itself authorize model inference or continuation. The
governor must still publish the applicable admission or continuation decision.

Claims use atomic compare-and-set acquisition and monotonically changing
fencing generations. Broker calls, result acceptance, and effect dispatch reject
stale owners. An expired lease does not prove the old worker stopped; uncertain
in-flight effects block redispatch until reconciliation. Preserve dispatch intent
and persist result/continuation publication with conflict detection so a crash
cannot authorize two next steps.

Each wake declares whether it targets an existing nonterminal run or a new
scheduled occurrence. Deduplication keys include the occurrence identity;
terminal runs never reopen implicitly. Scheduled and webhook ingress require
explicit timezone/missed-trigger policy, authenticated provenance, and replay
protection. Implement them after durable manual/API wake and recovery proof.

## Completion and final truth

Admitted completion bases are:

1. deterministic predicate;
2. schema or contract validation;
3. verified integration observation;
4. bounded operator attestation or decision where policy permits;
5. model evaluation as advisory evidence only.

Verified `success` requires `completion_satisfied` and an admitted non-advisory
basis with sufficient or policy-admitted attested evidence. Model output alone
cannot produce authoritative success.

All terminal runs publish one `FinalTruthRecord` using the existing result,
completion, evidence, uncertainty, degradation, closure, and terminality
vocabularies.

## Required proof

Implementation admission requires:

1. `unit` proof for deterministic continuation, budget, context, and
   serialization rules;
2. `contract` proof for schemas, version negotiation, manifests, capabilities,
   and fail-closed parsing;
3. `integration` proof for repositories, extension subprocesses, cancellation,
   provider-profile resolution, approvals, effects, queue claims, and recovery;
4. `end-to-end` deterministic fixture proof;
5. `end-to-end` Ollama-backed single-model proof;
6. `end-to-end` Ollama-backed fixed multi-model proof using at least two model
   identities;
7. restart proof with no duplicated effect;
8. an offline inspector or replay view that explains every continuation.

At least one deterministic and each live success proof crosses two admitted
iterations with the next context derived from prior recorded evidence. Use the
same bounded objective, deterministic content verifier, fixtures, and total
budget for single-model and multi-model comparisons. Record correctness, repair
counts, actual model identities, measured/unknown usage, and elapsed time;
successful multi-model invocation alone does not prove improved quality.

Routine live proof must set `ORKET_DISABLE_SANDBOX=1`. Any intentional sandbox
proof must demonstrate teardown in the same execution path.

## Admission diagnostics

1. `E_AGENT_HOST_FEATURE_UNSUPPORTED` means an agent manifest requires a host
   feature that the selected admission surface does not advertise. Refusal
   occurs before child startup.
2. `E_AGENT_RUNTIME_NOT_ADMITTED` means an agent-like workload reached the
   generic extension executor instead of the dedicated governed-agent path.
   Refusal occurs before run-artifact allocation.

## Compatibility and maintenance

1. The agent workload uses the existing `manifest_version: v0` family with
   versioned agent-contract declarations and mandatory `agent.iteration.v1` in
   `required_capabilities` for agent workloads. Existing non-agent workload
   entries remain valid. Optional metadata alone cannot enforce admission.
   New validation rejects unknown fields within typed agent declarations rather
   than silently discarding misspelled contract, budget, or recovery inputs.
2. A host that does not support `governed_agent_loop.v1` must reject the agent
   extension before model or effect work. An older strict validator can reject
   the unknown required capability using its existing diagnostic. The agent
   entrypoint also requires a live host-issued invocation handshake so a
   permissive legacy path cannot silently execute it as a generic workload.
3. The public SDK must not expose private `orket.*` models or repositories.
4. Any semantic change to this contract requires a contract delta and same-
   change updates to SDK bindings, schemas, validation, the reference extension,
   operator docs, and `CURRENT_AUTHORITY.md` as applicable.
5. Package the canonical wire schemas for clean SDK installation and check both
   SDK and host bindings against the same bytes; do not copy schema authority.
   Matching built host/SDK/extension versions and legacy combinations must be
   tested before publishing compatibility claims.
