# Interaction cancellation admission and publication

Owner: Orket Core. Date: 2026-09-19. Effective version: 0.6.27.
Status: Active contract; full architectural-truth acceptance remains open.

## Delta

Previously, `POST /v1/interactions/{session_id}/cancel` reported success and
published `accepted_cancel` after a manager call that silently ignored missing,
idle or terminal targets. A supplied turn identifier could cancel another
session's turn. Request cancellation could also abandon stream or operator-action
publication after state had already changed.

Application `InteractionCancellationService` now captures the manager, publisher,
actor, requested identity and explicit host clock before awaiting. The state
adapter validates session membership under the manager lock. Its immutable core
outcome distinguishes an observed cancellation from missing, idle and terminal
targets. Only a new interruption followed by stream publication permits the
application to publish an accepted operator action. The operation retains both
effects and audit publication through repeated caller cancellation, timeout and
application shutdown. Worker/publication failures propagate.

The HTTP success body remains `{ "ok": true, "target": ... }`. Missing sessions,
missing turns and foreign-session turns return 404. Idle sessions and terminal
turns, including repeat cancellations, return 409 without another accepted action.
Disabled streaming returns 400. An explicit turn operand equal to the session
identifier is still a turn lookup, not permission to cancel the active session.

Operator actions retain the existing command/input classes and result vocabulary.
Both session- and turn-scope records identify the actual interrupted turn in
`receipt_refs`, `affected_transition_refs` and `affected_resource_refs`. The
transition reference is `interaction-turn:<turn_id>:interrupted`; the receipt
reference is `interaction-cancel:<turn_id>`. These are logical references to the
observed interaction, not separate receipt files or workload completion proof.

## Migration

No compatibility shim or database schema migration is introduced. API clients
must handle 404/409 instead of treating every cancellation request as accepted.
Router embeddings replace `control_plane_publication_getter` with an application
`cancellation_service_getter`; without it, the cancellation endpoint returns 503.
`ApiRuntimeContainer.interaction_cancellation()` supplies the standard service.

Direct `InteractionManager.cancel(target)` callers may still ignore its return,
but it now returns an `InteractionCancellation` value. Existing internal unscoped
target lookup remains available for known workload turn identifiers. The HTTP
command always supplies explicit session scope and timestamp. Other manager
clock/environment/identity observations remain existing C/D work.

## Proof and limits

Retained real ASGI counterexamples precede the repair. Integration cases exercise
real manager state, stream events and SQLite operator records. Held event/audit
operations require a concurrent heartbeat within 0.5 seconds and settlement within
3 seconds after fixture release. A real SQLite trigger refuses the audit insert;
the route returns 500, the interruption remains observable, and retry returns 409
without inventing a missing record. Source/native checkpoint results and exact
evidence are recorded in the canonical remediation plan.

State, stream publication and SQLite are separate effects, not one transaction.
If stream or audit publication fails after interruption, the API does not report
success or replay the transition on retry. Operators must inspect the retained
stream/session state and database; automatic repair of missing publications is
not admitted by this change. Process death can still leave an unaudited transition.
No hard deadline for a hung publisher, persistent interaction recovery, provider
termination, universal workload teardown or completion guarantee is claimed.
Anonymous requests under the existing insecure posture still produce no
authenticated operator-action record.

## Rollback

Stop and drain affected applications before a versioned rollback. Restore service,
router and manager contracts together and retain existing operator records.
Previously interrupted turns must not be replayed to manufacture audit evidence.
Rollback is appropriate if the scoped admission or interruption parity gates fail;
it must not silently restore foreign-session cancellation as acceptable behavior.

Version decision: patch checkpoint with breaking cancellation/embedding semantics.
Compatibility status: breaking. Affected audience: all. Migration: required.
