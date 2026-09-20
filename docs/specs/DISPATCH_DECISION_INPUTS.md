# Dispatch decision input ownership

Status: Active contract for the 0.6.47 candidate
Owner: Orket Core
Last updated: 2026-09-20

Application dispatch captures immutable values before invoking either strategy.
`PlanningInput`, `PlanningCardInput`, `RoutingInput` and `RoutingSeatInput` are
authoritative in `orket/core/contracts/decision_inputs.py`. They contain frozen
models, scalar facts and immutable sequences; construction copies input lists.
Runtime models, arbitrary parameter dictionaries, repository handles and callbacks
are not part of these contracts.

Planner cards expose ID, status, seat, summary, priority and prerequisite IDs.
The backlog contains dependency-admitted cards; independent-ready cards preserve
their observed order. The target selector is captured with that invocation.
Strategies return card recommendations. Application maps their IDs back to its
inspected records, refuses unknown/non-string/duplicate IDs and ignores proposed
replacement fields. Existing dependency reinspection before turn effects remains
authoritative; a planning snapshot is not continuing authorization after drift.

Routers receive one `RoutingInput`: issue ID, declared issue seat, review flag and
ordered seat/role values. They return a plain string seat recommendation. Invalid
return types fail with `E_CARD_ROUTING_INVALID_RECOMMENDATION` before dispatch.
Application still applies its small-project policy, runtime profile checks,
seat lookup and missing-seat transition. The default strategy preserves original
seat routing and first-integrity-guard ordering for review turns.

Custom planners must read these declared facts instead of mutating card models or
accessing undeclared runtime fields. Custom routers migrate from
`route(issue, team, is_review_turn)` to `route(inputs)`. There is no old-signature
fallback or mutable compatibility payload. Frozen-value mutation errors propagate
before this invocation can authorize dispatch effects.

Evaluator handlers capture their selected node and immutable input facts before
their first await. Failure context contains issue ID, retry counts, error and a
copied tuple of violations. Failure-report publication and subsequent evaluation
use the same captured error. Success context captures initial issue status, content,
seat and review flag; the observed updated status is added after the application
reads the repository. This is an explicit observation sequence, not an atomic
snapshot of the entire runtime or database.

Evaluators implement `evaluate_failure(FailureEvaluationInput)` and
`evaluate_success(SuccessEvaluationInput)`. They cannot borrow the caller's issue,
result, mutable violation list or retained execution turn through these arguments.
The application validates recommendation field types and copies success decisions
and actions into read-only primitive mappings before further evaluator calls.
Success flags require booleans; retry counts require integers without coercing
booleans or strings. Unknown fields fail. An omitted next retry count preserves the
captured count. Existing custom exception/message policies remain available.
These checks do not establish a new retry-budget policy or authorize arbitrary
recommendations; the existing application transition/completion authorities remain.

A failure evaluator refusal may follow an already-published truthful failure
report. It does not erase that report or claim there were no preceding effects.
The changed boundary does not freeze all caller-owned application objects or
rewrite the durable transcript; it prevents borrowed evaluator inputs from
mutating them. Custom-node migration is explicit, with no signature fallback.

These are trusted in-process strategy contracts, not hostile Python containment.
They do not prevent a plugin from using an independently acquired global reference
or deliberately bypassing Python model protections. They do not establish purity
for other strategy families, freeze all application state, or retire legacy domain
exports. `BT4-FIXTURE-SYNC-RETIRE` retains its explicit 0.7.0 cutover commitment.
