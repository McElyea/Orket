# Control-plane terminal authority

Last updated: 2026-09-24
Status: Active contract; historical-consistency implementation acceptance remains scoped in the architectural-truth plan.

## Common record contract

Run admission identity is immutable after its first write. The shared
`same_run_admission` rule compares every `RunRecord` field except lifecycle state,
current-attempt reference, final-truth reference and state revision. Thus contract/workload
versions, policy/configuration identities and digests, creation time, admission
receipt and namespace cannot be replaced by an ordinary state update. Newly added
fields are immutable unless explicitly admitted as state by that rule.

`ControlPlaneExecutionRepository.save_run_record` compares and writes under one
writer transaction. SQLite standalone writes acquire that transaction; borrowed
ports preserve their caller's transaction ownership. The writer captures the
incoming record before its first await and compares and persists that same input;
caller mutation during a lock wait cannot change the comparison or returned record.
An identical save at the current observed revision or a conditional state update
remains supported. A changed admission raises
`E_CONTROL_PLANE_RUN_AUTHORITY_CONFLICT` and preserves the stored record. Competing
native writers cannot both create different admission authority for one run ID.
The revision contract below does not replace family lifecycle validation, lease fencing or terminal
evidence checks; state fields are not unrestricted execution authorization.

Governed-agent reentry reuses the common admission comparison, retaining the
original creation time when the reentry caller supplies a new observation time.
It additionally binds the expected current attempt. Kernel-action admission
refuses a missing or conflicting retained namespace instead of backfilling it.
Historical namespace migration requires separate admitted evidence; normal
reentry has no authority to choose a replacement scope.

The existing `RunRecord`, `AttemptRecord` and `FinalTruthRecord` remain the
canonical records. A run has one immutable final-truth identity. The shared
SQLite repository accepts an identical retry and refuses a different identity or
payload for that run with `E_CONTROL_PLANE_FINAL_TRUTH_IDENTITY_CONFLICT`.
Standalone publication compares under a writer transaction; a borrowed
control-plane transaction retains commit ownership.

Reads must not choose among multiple retained truths by identifier ordering.
The repository refuses multiple rows or disagreement between indexed identity
and payload with `E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT`. This applies to
old rows as well as new writes. No stored schema or receipt version changes.

`validate_terminal_record_consistency` owns the minimum terminal join:

1. A terminal run, its final-truth reference and its run-bound truth agree.
2. Its current attempt belongs to that run and is terminal with an end timestamp.
3. Completed run, completed attempt and successful truth agree. A failed or
   cancelled run cannot project successful truth or a completed attempt.
4. A nonterminal run without a terminal reference or truth remains nonterminal;
   recovery may retain a closed attempt.

These checks establish record consistency. Family-specific evidence, verifier,
operator, effect and outcome rules remain required. A consistent terminal join
alone does not prove successful work, effect termination or historical authenticity.

Outward result projection and cards epic closeout also apply this validator
before accepting retained terminal records. Their stronger receipt, effect and
closeout checks remain authoritative for those families.

Governed turn-tool finalization and preflight closeout read and publish through
the existing control-plane transaction factory. Run, attempt, terminal truth,
recovery decision and required resource release commit together. A rejected
lease timestamp or interrupted write rolls back the closeout; already observed
tool effects remain retained. The lease timestamp rule remains authoritative:
the runtime does not clamp a reversed clock or turn failed cleanup into success.
Repeated closeout validates retained terminal consistency before returning truth;
it does not silently attach an unreferenced truth to a run.

Preflight abandonment retains an `attempt_abandoned` record with its end time.
Its recovery decision records the failure classification and references that
attempt. The abandoned attempt does not carry the boundary, failure or recovery
link fields reserved by `AttemptRecord` for failed/interrupted attempts. Previously
written invalid records require separate reconciliation and are not rewritten.
Kernel-action pre-effect rejection/error follows the same abandonment contract.
Its view resolves the publisher-owned recovery identity and verifies run, attempt,
policy and failure classification; conflicting bindings or competing decisions
refuse projection. Attempt failure fields remain null. The view's
`current_recovery_*` fields describe the retained decision, including boundary,
failure class, plane and classification. Read-only session abandonment without a
recovery decision projects no recovery reference.
Turn pre-effect recovery and reconciliation now use the explicit application
transaction owner in `turn_tool_recovery_transaction.py`. Both service and workflow
entrypoints compare current run/attempt to captured caller inputs under the writer
transaction; orphan-operation reconciliation also compares checkpoint acceptance.
Recovery decisions, attempt/run transitions, reconciliation, terminal truth and
lease release commit together. A completed reconciliation reports its refusal
after commit. Other exceptions and cancellation roll back these writes while
preserving earlier physical effects and evidence. Scoped source, installed and
native acceptance passes in the architectural-truth plan. This does not fence work
outside that transaction or reconcile already partial historical stores.

## Orchestrator issue-dispatch closeout

`OrchestratorIssueControlPlaneService` requires the composed control-plane
transaction factory. Both transition-driven and observation-driven closeout read
current admission, attempt and resource authority under that transaction. The
closeout step/effect record, recovery decision when required, final truth,
attempt/run transitions, lease release and resource snapshot commit together.
Validation errors, interrupted writes and cancellation roll back this publication.
Previously observed model/tool effects remain retained outside the transaction.

The issue service requires an explicit `now_utc` callable. Execution-pipeline wiring
passes its existing runtime input clock through the orchestrator's
`control_plane_clock`; direct orchestrator composition defaults to the UTC adapter.
Admission captures one supplied timestamp. Borrowed closeout owners retain the
same clock, and the service captures closeout time after acquiring the transaction.
The closeout effect, attempt end and released lease share that captured value. A reversed
UTC input still fails lease validation; it cannot leave successful terminal truth
beside an active lease. Ordered fixture inputs do not establish a monotonic host
wall clock. Repeated closeout validates the common terminal join and released
resource authority before returning without additional writes.

Historical partial closeout is refused, including a completed run with an active
lease or missing final truth. Normal closeout does not backfill, rewrite or resume
that history. Dispatch admission and physical effects are separate operations;
this transaction does not establish atomicity across their complete lifecycle,
automatic recovery or remote fencing. Current acceptance scope is recorded in
the architectural-truth plan.

## Scheduler publication clock

The orchestrator also supplies `control_plane_clock` to scheduler transition and
child-issue publication. Admission, normal closeout and activation-failure cleanup
consume that clock. Direct scheduler construction accepts `now_utc` and otherwise
retains the UTC adapter default. Cleanup observes its supplied clock after the
activation failure; it does not reuse an admission timestamp as a fabricated end.

This wiring does not extend the issue-dispatch atomicity contract to the scheduler.
Scheduler closeout remains a sequence of publications: a reversed timestamp fails
lease validation and can leave partial terminal publication with active authority.
The runtime does not clamp that input or invent a release. Atomic scheduler
closeout and recovery remain architectural-truth work; the scoped clock delta is
`docs/architecture/CONTRACT_DELTA_SCHEDULER_CLOCK_D_2026-09-17.md`.

## Governed tool approval denial

Both immediate approval resolution and retained epic-pause continuation use
`finalize_turn_execution_atomic`. Composition supplies the transaction factory
for the same control-plane store as the execution and publication repositories.
The writer rereads the run and attempt and counts retained governed tool steps
inside that transaction. Denial recovery, attempt/run/final truth and required
lease/resource release commit together. Interrupted writes and rejected lease
timestamps preserve the unfinished child; timestamps are not clamped.

The operator decision and its hold/action records retain their existing separate
authority. Child closeout rollback does not undo a retained denial. Repeating the
same decision may complete an unfinished closeout; contradictory decisions remain
refused. Restarted epic continuation retains its existing claim/recovery rules.

Before accepting a terminal child, both approval consumers read its run, current
attempt and final truth in one existing control-plane transaction. The common
terminal join and dispatch/resource checks must agree. Missing truth, unfinished
attempts and unreleased namespace leases do not authorize parent completion.
This path does not repair historical split records or infer missing effects.

## Gitea worker closeout

The composed Gitea worker settles its owned renewal task before selecting and
dispatching the final remote state transition. Work failure may select the
existing failure state. An error or cancellation during remote closeout or local
publication does not authorize another remote state transition in that invocation.
An unobserved remote outcome stays uncertain; no terminal success is inferred.

After a returned remote outcome, final transition step/effect, recovery decision
when required, run/attempt/final truth and required lease/resource closeout share
the existing SQLite control-plane transaction. The writer verifies the retained
run/attempt and resource identity. Local publication failure or cancellation rolls
back the complete closeout while preserving physical effects and earlier evidence.
Terminal reuse validates the shared terminal join and the required closed resource
state; it does not repair contradictory historical records or change the outcome.

Execution, lease and reservation publishers accept explicit UTC providers.
Claim-failure reconciliation and attempt closeout use the execution service's
selected provider, including after intervening publication awaits. Reservation
creation and promotion retain their explicit `observed_at` override; when absent,
they observe the provider selected at construction. Default composition
uses the existing `RuntimeInputService`; supplied clock values retain their exact
meaning. Reversed timestamps remain rejected and are never clamped to an earlier
record. Deterministic test clocks do not prove that a host wall clock cannot reverse.

Reservation promotion-failure rollback also passes the observed timestamp through
the existing lease guard. A guard refusal publishes neither a rollback lease nor
the subsequent reservation invalidation; it does not substitute the prior lease
timestamp to manufacture a release. Earlier promotion writes, if any, remain;
this does not expand transaction atomicity. The promotion failure remains
available as the exception context. Earlier records created by the clamping path
are retained for explicit reconciliation.

This transaction does not include Gitea itself or establish remote exactly-once
execution, general restart recovery, atomic initial claim, or historical repair.
Retain already split histories and unknown remote outcomes for explicit
reconciliation. The architectural-truth plan records implementation and proof
status; this contract is not a claim that the remaining family gate has passed.

## Governed turn dispatch ownership

`TurnToolControlPlaneService.begin_execution` owns one existing control-plane
writer transaction for policy/configuration snapshots, the run and its current
attempt, admission reservation, execution lease/resource snapshot, reservation
promotion and executing-state transitions. It returns only after commit. Failure
or cancellation during any write rolls back that admission together. Native
process death before commit leaves no partial admission; after commit it retains
the complete admission for identical reentry.

The service borrows that transaction's explicit repository ports. Resume calls
the existing recovery algorithm on those ports, avoiding a nested writer. Its
transaction context and workflow recovery share `turn_tool_transaction`, which
commits a completed reconciliation refusal before reporting it; other failures
roll back. This is not a transaction over physical tool effects, checkpoint
artifact files, the parent runtime ledger or the separate epic publication store.
Earlier partial stores require separately admitted reconciliation; the transaction
does not infer missing historical truth.

New turn admission binds `dispatch_contract: turn_tool.dispatch_intent.v1` in
the existing resolved configuration snapshot and immutable run configuration
digest. Unfinished execution requires that exact declaration, a matching snapshot
identity/digest and a matching digest of the retained payload. Missing, unsupported
or unbound declarations refuse ordinary execution and resume before model/tool
work, admission repair, preflight closure, recovery, new step/effect publication,
and approval-denial or ordinary terminal closure. The check shares each writer's
existing transaction. Runtime code does not backfill the declaration or infer
pre-effect authority from an empty step/effect journal.

Refusal without rewriting retained state is the migration disposition for
unversioned unfinished turns, including older turns that already used dispatch
markers but did not bind this declaration. Preserve their effects and original
evidence for separately admitted reconciliation. This change adds no reconciliation
or replacement endpoint. Coherent completed history remains eligible for existing
artifact/effect-validated reuse without adding a declaration; conflicting terminal
references are refused rather than repaired during reentry.

Canonical governed `TurnExecutor.execute_turn` holds a nonblocking native lock
for the control-plane store and run identity before model work, and through
terminal publication and caller cleanup. The shared `NativeFileLocks` adapter
also supplies epic continuation locks; their retained path and identity contract
is unchanged. Acquisition and release threads remain owned through cancellation.
An active cooperating caller causes reentry/resume refusal before model or tool
dispatch. Explicit ungoverned embedding and artifact-only protocol replay do not
gain this execution guarantee.

After policy/approval checks and replay selection, `prepare_dispatch` commits a
`StepRecord` with `dispatch_started` result and closure classifications before
invoking the toolbox. Its input/operation references bind the admitted call.
Output, capability-used and resources-touched fields remain empty: admission is
not evidence that an effect happened. Compatibility translations share their
parent operation's admission; this does not add remote idempotency to each call.

Observed step replacement and effect-journal publication use one existing
control-plane transaction. They require matching attempt, namespace and call
references. Exceptions and cancellation roll back both writes, preserving the
dispatch marker and any physical effect. An already admitted operation cannot
receive another dispatch from this path.

Before result-file publication awaits, application captures nested arguments,
result, binding metadata and protocol capsule, and resolves the context values
needed by the receipt. Each admitted file worker remains owned until it settles,
including repeated cancellation and elapsed caller timeouts. The enclosing turn
therefore retains its native lock while the worker can still write. A worker error
observed during cancellation remains an error. Cancellation after that worker
settles stops subsequent publication; it does not imply rollback of a written file.
Result files, protocol receipts and control-plane records are not one transaction.
An existing file without coherent dispatch resolution cannot authorize redispatch
or successful completion. Ordinary ungoverned result caching shares file-worker
ownership, but gains no native turn lock. Migration and remaining limits:
`docs/architecture/CONTRACT_DELTA_TOOL_RESULT_WORKERS_D_2026-09-17.md`.

### Governed retained-operation reuse

A governed cache hit is read-only reuse of an already observed operation, not new
dispatch admission. Operation-record and legacy call-keyed hits use the captured
turn service, namespace, run and attempt. They require the existing run execution
gate, current executing attempt, matching durable namespace, same-attempt step,
effect-journal entry and canonical call reference. Missing or conflicting anchors
refuse before toolbox execution, after-tool middleware or new result, receipt,
step or effect publication for that rejected operation.

Record failures use `E_OPERATION_ARTIFACT_INVALID` with the finite record reasons
defined by the protocol contract. Missing step/effect authority uses
`control_plane_anchor_missing`; conflicting dispatch configuration, unresolved
dispatches, reservation/lease/resource authority, run/attempt/namespace or
step/effect/call authority uses `control_plane_anchor_mismatch`. Canonical terminal
join errors at this boundary are translated into the same named anchor-mismatch
family rather than a route-dependent raw final-truth error.

The governed validator reuses the already captured service and native run owner.
Its step, journal, run, gate, attempt and final run observations are separate
repository reads. Reloading the run last refuses run movement through the gate;
it does not create an atomic snapshot or prove that attempt, reservation, lease,
resource, step or journal state cannot move after its own read. The existing
transaction remains authoritative for new dispatch and step/effect publication.
No result file/control-plane transaction is introduced.

The operation result digest proves local file self-consistency only. Step and
effect records do not commit that digest, so coordinated result-plus-digest
replacement is outside this guarantee. Legacy `tool_result_*` reuse remains
call-keyed without a content digest; governed use gains anchor authorization, not
operation-record content integrity. Ungoverned reuse gains no durable control-plane
gate. Cached middleware receives detached values and must preserve canonical
arguments and result; valid reuse does not rewrite the retained operation file.
These rules do not authorize public resume over an already observed effect:
checkpoint admission and retained-effect reconciliation still apply.

Dispatcher refusal remains per call. Independent earlier or later calls can retain
their existing effects and publications, and the dispatcher retains its violation
aggregation and finalization behavior. This is not whole-turn rollback,
stop-on-first-refusal or atomic multi-call execution.

For terminal failure, an invocation-local zero step count cannot override a durable
effect journal for the same attempt. The existing closeout transaction reads that
journal before classifying failure: retained same-attempt effects require
`post_effect_observed`, `tool_execution_failed` and final result `failed`. A truly
empty attempt remains `pre_effect_failure` and `blocked`. Unresolved dispatch
markers still refuse terminal closure; this rule adds no reconciliation of split
step/journal authority and does not infer effects from result files.

An unresolved marker refuses ordinary reentry, resume, preflight abandonment and
terminal closure without releasing execution authority. Error or cancellation
after toolbox entry cannot be labeled a known pre-effect failure. Process death
releases the native lock but does not resolve the marker or prove termination of
remote effects. Explicit trustworthy observation/reconciliation remains required;
this change adds no operator endpoint for asserting an outcome or redispatching.

Stop old writers before deployment and preserve the control-plane store and
`<control-plane-db>.turn-owners/<sha256-run-id>.lock` files. Mixed old/new writers,
replacement of live lock files, different stores, hostile processes and remote
host fencing are outside this host-local ownership contract. Historical unmarked
unfinished attempts refuse continuation under the declaration rule above. No
historical effect is synthesized and no prior outcome is asserted by that refusal.

## Cards epic admission

`CardsEpicControlPlaneService.begin_execution` owns one control-plane transaction
for resolved policy/configuration snapshots, parent run, initial attempt, start
step, start effect journal entry, checkpoint and checkpoint acceptance. Admission
returns those records only after commit. Failure or cancellation at any of these
writes rolls back the entire control-plane admission before epic work dispatch.
It reuses the transaction factory and publication authority used by closeout.

The runtime ledger and epic publication journal retain their existing preparation,
admission and recovery authority in separate stores. This contract does not claim
a transaction across those stores, repair historical orphan parents, or authorize
their reentry. Workload catalog identity, policy digests, invocation identifiers,
approval fencing and `resume_forbidden` semantics remain unchanged. Broader
immutable admission and family conformance remain in BT-5.

## Governed-agent projection and reentry

Inspection takes its run, attempts and truth from the existing transaction-consistent
history reader. It no longer composes that join from independent repository reads.
Missing references, unfinished attempts, conflicting states and multiple truths
cannot produce an accepted terminal projection. Authenticated inspection returns
HTTP 409 with `E_AGENT_TERMINAL_AUTHORITY_CONFLICT`; the CLI returns a nonzero
status. Healthy inspection retains its existing response shape.

Replay loads truth by run identity even when the run's reference is absent. It
reports inconsistent or unreadable authority in diagnostics and cannot report
`matched`. Its scope remains recorded continuation decisions, not full execution
or external-effect verification. The existing bounded history-read limits also
apply to the inspection join; missing or unreadable evidence has no permissive fallback.
Final-truth rows remain subject to the reader's 64 MiB retained-value limit before
JSON interpretation. Oversized truth yields insufficient replay evidence with a
resource-limit diagnostic, even when its parsed records would otherwise agree.

Bounded-loop reentry compares immutable run identity and validates the terminal
join under the existing transaction owner before invocation or verification.
New parent run and attempt records commit together. Retained incomplete parents
or orphan attempts/truth refuse reentry; the reader does not silently backfill them.

Wake claim validation reads committed state through a separate read-only SQLite
connection. It must not take the renewal writer's application lock: terminal and
admission transactions may need the fence while renewal waits for their writer.
Missing wake inventory has no authority; owner, generation, cancellation and lease
checks still use the existing claim predicate. This avoids a local lock cycle and
does not grant stale owners or unbounded writer availability.

## Mutable execution revisions

Run, attempt and step records carry `state_revision`. An unsaved record uses null
and may create only an absent identity. A persisted record has a nonnegative
integer revision. Every update must supply the revision observed by that caller;
the shared store compares it under the existing SQLite writer transaction and
returns the saved record with its next revision. Writers retain that returned
record before another mutation or projection. Identical current saves are no-ops;
stale revisions refuse even when state has returned to an earlier value.

Run admission remains immutable. Attempt identity includes its run, ordinal and
starting snapshot. Its start timestamp may change only when a created attempt
first enters execution, preserving the existing execution-time meaning.
Step identity includes its attempt, kind,
namespace and input reference. The store refuses changes to those fields.
Revision checking covers local state publication, not model/tool ownership or
remote effect fencing. Multi-record atomicity still belongs to the existing
application transaction owners.

Historical records without a revision expose revision zero when read, without
rewriting their stored bytes. A changed, authorized save persists the next
revision. Explicitly null persisted revisions are invalid. This metadata upgrade
does not authorize historical execution: the existing dispatch-declaration,
terminal-consistency and reconciliation gates still apply. Stop older writers;
mixed versions and downgrade to a writer that ignores revisions are unadmitted.
The architectural-truth plan owns the current source/installed proof disposition.

## SDK, legacy extension and manual review closeout

The extension and manual-review application services borrow the existing SQLite
control-plane transaction for terminal publication. The current run and attempt,
closeout step, observed closeout effect, final truth and terminal run reference
are read and written under that owner. An exception or cancellation before commit
rolls back that terminal record set. Earlier workload effects and artifacts remain
outside the closeout transaction; rollback does not undo or authorize their replay.

Repeated closeout validates the common terminal join and the family's expected
step, effect, authority sources and result reference. An identical retained result
is a no-op. Missing or conflicting evidence refuses without repair, including a
different requested outcome. Independent closeout callers serialize under the
writer transaction; they cannot publish competing terminal outcomes.

Manual review's failure boundary may preserve an already coherent terminal result.
It cannot reinterpret that result as a failed review. If failure closeout itself
raises, the boundary logs that secondary error with the run identity and preserves
the originating exception. Review summary reads validate retained terminal evidence
before projection. Failure references consistently use the recorded failure class,
limited to 200 characters. Inconsistent historical references require reconciliation;
normal reads and retries do not rewrite them.

This contract does not add transactional admission, automatic recovery, hostile
extension containment or independent objective verification to these families.
Their distinct executors and existing review replay scope remain explicit in the
governed start-path matrix. Current repair acceptance is owned by the canonical
architectural-truth plan; the original partial histories remain retained.

## Cards, extension and manual-review clock inputs

The cards-epic, extension-workload and manual-review control-plane services accept
an explicit `utc_now` callable returning an aware UTC ISO timestamp string. The
default is the existing host UTC adapter. Service construction selects the
callable; every transaction-scoped service carries that same selection. It must
not silently restore a host clock when borrowing transaction ports.

Execution-pipeline composition supplies its existing `RuntimeInputService` clock
to the cards-epic service. The review factory and both extension-service factories
expose the same clock input. A review host can inject the resulting service through
the existing `review_control_plane_service` port.

Extension-manager construction supplies its selected `utc_now` to workload
execution as well as catalog installation. Async manager preparation exposes that
input. Workload creation identity, start effects and terminal publication consume
the same selected clock. The identity and begin-execution helpers also accept an
explicit clock; already supplied creation time/run identity retain their existing
meaning and do not trigger a replacement time observation.

These are clock-selection boundaries, not one timestamp reused for an entire run.
Creation, journal and closeout observations remain at their existing application
publication points. A closeout observes fresh values after the workload outcome;
an identical terminal retry validates retained records without manufacturing a
new end time. Clock failure propagates through the existing transaction and
failure boundaries. Earlier effects remain retained; no fallback clock, clamped
timestamp, fabricated receipt or automatic replay is introduced.

This does not expand transaction scope, change family terminal authority or prove
a monotonic host wall clock. Selected fixture timestamps are input values and do
not measure elapsed duration. Current acceptance is recorded in the
architectural-truth plan; remaining input owners and Linux clock proof stay open.

## Historical-state disposition

Preserve inconsistent stores and their original receipts, decisions and effects.
Refusal is the current disposition for split terminal histories and competing
truth identities. This cutover does not rewrite historical outcomes, delete a
competing row, synthesize missing completion, or authorize redispatch. Recovery
requires a separately admitted reconciliation path with evidence for that history.
Stopping admission while preserving evidence is the supported rollback posture;
returning to an older permissive writer is not a repair.
Stop older writers before the cutover. Mixed old/new writers are unadmitted;
refusing ambiguous history does not prevent an arbitrary older process from
writing another row outside the new repository contract.

The canonical architectural-truth plan owns source/package identities, copied
history controls, native writer races, interruption proof and remaining gates.
