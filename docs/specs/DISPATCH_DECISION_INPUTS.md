# Dispatch decision input ownership

Status: Active contract for the 0.6.48 candidate
Owner: Orket Core
Last updated: 2026-09-20

Application dispatch captures immutable values before invoking each covered strategy.
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

Loop policies receive tuples of `PlanningCardInput` for backlog checks. The
application captures each dispatch snapshot before subsequent team-replan and
dependency-propagation awaits, and captures the final exhaustion observation after
its repository read. The selected main-loop node is retained before the first
settings await. A terminal recommendation remains separate from accepted build
completion; the application ignores a proposed completion event name.

Per-seat policy methods accept one `SeatPolicyInput` from
`orket/core/contracts/decision_inputs.py`. It contains seat name, captured card
facts, turn status and resolved required-read/write path tuples. Arbitrary issue
parameters and turn-contract dictionaries remain application-owned. The context
builder captures this value once before calling its policy methods; existing
application turn-contract overrides remain authoritative. Guard validators receive
`GuardReviewInput` with rationale, violation and remediation tuples. The pure
default validation has one definition shared with the absent-method default.

Custom seat methods return lists or tuples of plain string names, and gate-mode
methods return a plain string. No-candidate and guard recommendations require
strict boolean fields and reject undeclared keys; exhaustion returns a boolean.
The application copies lists and validates/copies mappings. Missing optional
methods retain their existing defaults, but an entered strategy failure propagates
once: no `TypeError` signature retry remains for seat or guard methods.

Role selection takes a role tuple captured before turn-transition awaits. Its
returned names are validated and copied before loading roles. A later refusal may
follow an already-performed card transition; it does not imply that all preceding
effects were rolled back. These are per-boundary observations, not an atomic
snapshot of the complete application. No new retry-budget or completion policy
is established. Custom-loop migration is explicit in
`docs/architecture/CONTRACT_DELTA_LOOP_INPUTS_D_2026-09-20.md`.

These are trusted in-process strategy contracts, not hostile Python containment.
They do not prevent a plugin from using an independently acquired global reference
or deliberately bypassing Python model protections. They do not establish purity
for other strategy families, freeze all application state, or retire legacy domain
exports. `BT4-FIXTURE-SYNC-RETIRE` retains its explicit 0.7.0 cutover commitment.
