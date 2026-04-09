# Workload Lifecycle and Supervision Requirements
Last updated: 2026-04-09
Status: Active durable spec authority
Owner: Orket Core
Lane type: Control-plane foundation

## Purpose

Define the legal lifecycle of governed workloads and the supervisor authority that owns transitions, failure classification gates, recovery entry, reconciliation entry, quarantine, and closure.

## Authority note

Shared state enums are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

This document defines the semantics, guardrails, and supervisory rules for those states.

## Core assertion

A loop is not a supervisor.

Orket requires a supervisor-shaped control-plane component that is authoritative for lifecycle transitions and that preserves execution truth across retries, interruptions, reconciliation, and operator intervention.

## Lifecycle objects in scope

This document governs state transitions for:
1. runs
2. attempts
3. reservations where directly coupled to admission and scheduling
4. leases where directly coupled to run state
5. operator holds and quarantine states

## State semantics

### WL-01. Run states

The run states listed in the glossary are canonical.

The following state meanings are especially important:
1. `recovery_pending` means the prior attempt ended and the supervisor has not yet authorized the next action.
2. `reconciling` means observation and comparison work is in progress.
3. `recovering` means an authorized control-plane recovery action is in progress.
4. `operator_blocked` means continuation requires explicit human input but the run is not yet quarantined.
5. `quarantined` means the run is intentionally isolated from automatic continuation because safety or authority boundaries have been crossed.

### WL-02. Attempt states

The attempt states listed in the glossary are canonical.

Attempt state must not be inferred only from run state.

## Supervisor authority

### WL-03. Supervisor ownership

The supervisor is the sole authority for:
1. run lifecycle transitions
2. attempt creation and closure
3. reservation promotion to lease where execution authority begins
4. transition into recovery, reconciliation, quarantine, operator-blocked, and terminal states
5. checkpoint acceptance for resume
6. final closure of run truth surfaces

### WL-04. Supervisor inputs

The supervisor may base decisions only on:
1. validated runtime state
2. policy resolution
3. step and effect receipts
4. reservation and lease state
5. reconciliation records
6. operator actions
7. authoritative adapter observations

The supervisor must not use:
1. unvalidated model narrative
2. speculative explanation text
3. hidden implementation heuristics with no recorded basis

## Guard and action tables

### WL-05. Transition guard and action requirements

The following transitions require normative guard and action behavior.

| Transition | Guard | Required receipts or evidence | Allowed actor | Forbidden shortcuts | Resulting truth constraints |
| --- | --- | --- | --- | --- | --- |
| `admitted -> executing` | admission accepted; required reservations or prerequisites exist | admission decision receipt; reservation references if applicable | supervisor | starting execution without admission receipt | run remains attributable to admission and initial execution mode |
| `executing -> recovery_pending` | attempt ended without truthful closure | failed or interrupted attempt record; side-effect boundary classification | supervisor | immediate blind retry | run may not return to `executing` until recovery decision exists |
| `recovery_pending -> reconciling` | policy or uncertainty requires observation before recovery | reconciliation trigger basis; required scope | supervisor | treating unresolved uncertainty as pre-effect convenience | continuation must wait for reconciliation output |
| `reconciling -> recovering` | reconciliation published a continuation class that requires control-plane recovery work | reconciliation record; authorized recovery decision | supervisor | treating reconciliation itself as execution restart | `recovering` remains control-plane work only |
| `recovering -> executing` | authorized recovery work is complete and workload execution may continue | recovery action receipt; attempt bootstrap or resume basis | supervisor | continuing execution without recovery completion receipt | resumed or replacement execution re-enters `executing`, not `recovering` |
| `executing -> operator_blocked` | bounded human decision is required but quarantine is not yet warranted | operator requirement basis; unresolved decision surface | supervisor | hidden human assumptions; hidden pause | run truth must remain explicitly blocked pending operator input |
| `executing -> quarantined` | contradiction, unsafe ownership, or policy breach requires isolation | violation basis; quarantine reason | supervisor | continuing in degraded mode by convenience | automatic continuation is disabled until explicit release path exists |
| `operator_blocked -> recovering` | explicit operator input permits a control-plane recovery action | operator action receipt; recovery decision | supervisor | treating operator input as world-state evidence | operator input may change continuation but not truth classification |
| `quarantined -> failed_terminal` | safe continuation remains unavailable | terminal decision basis; any required operator or policy confirmation | supervisor | auto-releasing quarantine into terminal closure with no basis | final closure must remain explicit about why continuation stopped |
| `operator_blocked -> failed_terminal` | operator or policy chooses terminal stop instead of continuation | operator action or policy basis; closure basis | supervisor | marking terminal as successful completion | terminality may change, truth classification may not be rewritten by command |

### WL-06. Additional transition rules

1. `recovering` must not be used for ordinary workload execution.
2. Resumed execution from checkpoint or replacement execution in a new attempt returns to `executing`.
3. `reconciling` and `recovering` are distinct run states and must not be merged into one implementation state.
4. Illegal transitions must:
   1. be rejected
   2. emit a structured supervisory error
   3. preserve prior valid state
   4. avoid partial state mutation

## Checkpoints and interrupted attempts

### WL-07. Checkpoint use

Where checkpoints exist, the supervisor must classify them as:
1. resumable without re-observation
2. resumable only after re-observation
3. non-resumable

Resume behavior must be policy-controlled and never implied by mere existence of saved state.

### WL-08. Interrupted attempt handling

Interrupted attempts must be classified distinctly from deterministic failures.
At minimum the supervisor must determine:
1. whether the attempt ended before any effect was attempted
2. whether effect boundary is uncertain
3. whether reservation or lease ownership may still persist
4. whether checkpoint state remains valid
5. whether reconciliation is required before any retry

## Quarantine and degraded modes

### WL-09. Quarantine triggers

A run must be eligible for quarantine at minimum when:
1. repeated unsupported claims occur
2. contradiction persists across retries
3. an effect boundary remains unresolved after required reconciliation
4. lease ownership is inconsistent or unsafe
5. a policy-critical supervisory invariant is violated
6. operator-only continuation is required and repeated release would be unsafe

### WL-10. Degraded continuation

The supervisor may continue execution in an explicitly declared degraded mode only if:
1. the degraded mode is workload-legal
2. the capability and effect class permits it
3. the resulting truth surface is explicit about downgrade
4. unsafe mutation paths are blocked
5. operator requirements are respected

## Final run closure

### WL-11. Final closure surface

Run closure must publish at minimum:
1. final lifecycle state
2. final truth record reference
3. final attempt identifier
4. whether recovery occurred
5. whether reconciliation occurred
6. whether any effect uncertainty remains
7. whether operator intervention occurred
8. authoritative result or non-result reference

## Acceptance criteria

This lifecycle and supervision draft is acceptable only when:
1. all subordinate control-plane drafts can reference the same states without reinterpretation
2. risky transitions are defined by guards and required evidence, not just by arrows
3. `recovering` is kept distinct from ordinary execution
4. quarantine is a first-class controlled state rather than an implementation accident
5. checkpoints and resumed execution have explicit supervisory authority
6. terminal state publication explains why continuation stopped without allowing operator commands to rewrite truth
