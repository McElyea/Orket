# Supervisor Runtime Foundations Requirements
Last updated: 2026-03-31
Status: Active requirements companion for open lane
Owner: Orket Core
Lane type: Supervisor runtime foundations / requirements phase

## Authority posture

This document is the scoped requirements authority for the active SupervisorRuntime lane.
It is not the roadmap pointer.

The active lane authority remains `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_IMPLEMENTATION_PLAN.md`.
Brainstorm material under `docs/projects/future/brainstorm/` is planning input only.

## Purpose

Define the smallest coherent requirements packet for the next supervisor-runtime foundations lane.

This requirements packet is intentionally limited to:
1. approval-checkpoint runtime behavior
2. session and context-provider behavior
3. operator control surfaces needed to supervise those behaviors
4. host-owned extension install and validation rules

## Cross-lane invariants

### SRF-01. No second runtime authority
The host remains the sole runtime authority.
Client-facing repos, extension repos, and operator surfaces may present, request, inspect, or validate runtime behavior, but they must not become hidden authority centers.

### SRF-02. No resume by implication
Checkpoint presence, snapshot presence, or saved state presence must never authorize continuation by implication.
Resume must require explicit admissibility and explicit runtime authorization.

### SRF-03. No operator truth rewrite
Operator command, risk acceptance, and attestation must remain visibly distinct from runtime observation and closure truth.

### SRF-04. No memory-scope collapse
Session memory, profile memory, and workspace memory must remain distinguishable.

### SRF-05. No install path without declared capability and permission scope
Any supported extension install path must carry explicit manifest declarations for capability and permission scope.

## Minimal terminology lock

These terms are load-bearing for this requirements lane:

1. `session`: a host-owned continuity object that can outlive any single invocation
2. `invocation`: one admitted runtime execution entry attached to a session or explicitly sessionless
3. `lineage`: the attributable relationship between sessions, invocations, checkpoints, and later continuations
4. `replay`: non-authoritative reconstruction or inspection from preserved artifacts without granting new execution authority
5. `reconstruction boundary`: the point after which inspection may describe prior truth but may not invent authority for continuation or closeout

## Section A - Approval-checkpoint runtime requirements

### SR-01. Approval-required capability class
The lane must define at least one explicit approval-required capability class suitable for direct implementation.

The class must identify:
1. what kind of action is gated
2. who may request it
3. who may approve or reject it
4. what namespace and resource scope it can affect
5. which runtime path owns its truth

### SR-02. Interrupt / approve / reject / resume lifecycle
The lane must define one canonical lifecycle for:
1. interrupting the gated path
2. recording the pending state
3. approving or rejecting the action
4. resuming or terminating execution

The requirements packet must make clear which lifecycle state changes are:
1. operator-visible
2. runtime-authoritative
3. projections only

### SR-03. Checkpoint-backed continuation semantics
The lane must define one checkpoint-backed continuation model for the admitted capability class.

The model must distinguish:
1. same-attempt continuation
2. replacement-attempt continuation
3. replay-only inspection
4. resume-forbidden states

### SR-04. Fail-closed preconditions
The gated runtime path must fail closed when required approval, checkpoint, namespace, or recovery prerequisites are missing or drifted.

The requirements packet must name which missing or drifted preconditions are fatal for:
1. initial execution
2. resumed execution
3. post-interrupt continuation

### SR-05. Approval and resume evidence
The lane must define one evidence story showing:
1. why execution was paused or gated
2. who approved, rejected, or resumed it
3. which checkpoint boundary was used
4. how the resulting execution remained attributable

## Section B - Session and context-provider requirements

### SR-06. Canonical session identity
The lane must define one canonical session identity model distinct from invocation identity.

The requirements packet must state:
1. how a session is created
2. how invocations attach to a session
3. how session lineage is retained
4. what survives between invocations

### SR-07. Memory-scope separation
The lane must define the minimum required boundary between:
1. session memory
2. profile memory
3. workspace memory

The requirements packet must state:
1. which scope owns what kind of state
2. how scopes are read
3. how scopes are written
4. how scopes are cleared or retired

### SR-08. Context-provider pipeline
The lane must define one explicit context-provider model for runtime invocation.

The model must be able to express:
1. memory-derived context
2. retrieval-derived context
3. policy context
4. tool and capability context
5. operator context

### SR-09. Session inspection and cleanup
The lane must define operator-visible rules for:
1. session summary
2. session lineage inspection
3. session cleanup
4. session replay or reconstruction boundaries

### SR-10. Host-owned continuity
The requirements packet must make explicit that session continuity remains host-owned.
Client repos may request or present session state, but they must not become the authority seam for memory retrieval, orchestration, or lifecycle decisions.

## Section C - Operator control surface requirements

### SR-11. Stable operator event and action surface
The lane must define one stable operator surface for the admitted approval and session behaviors.

At minimum it must cover:
1. pending approval visibility
2. hold or interrupt visibility
3. resume and rejection visibility
4. session and checkpoint inspection visibility

### SR-12. Canonical operator actions
The lane must define the operator actions admitted by this packet.

At minimum it must make explicit:
1. hold
2. resume
3. approve
4. reject

The packet must also state which actions are intentionally out of scope.

### SR-13. Inspection surfaces
The lane must define which operator inspection surfaces are required for the first executable packet, including where applicable:
1. checkpoint inventory
2. resource scope or lease view
3. replay boundary inspection
4. approval lineage
5. session lineage

### SR-14. Projection boundary
The operator surface must remain a projection and action layer over runtime truth, not a hidden runtime authority.

The requirements packet must explicitly forbid:
1. endpoint-local truth invention
2. action logs being treated as world-state evidence
3. operator commands rewriting runtime closure truth

### SR-15. Canonical projection source
The lane must name one canonical runtime artifact or event family from which the first operator-visible projections are derived.

That requirement must make explicit:
1. which fields are authoritative runtime truth
2. which fields are operator-visible projections
3. which fields are operator actions or requests
4. how projection consumers fail closed when the canonical source is missing or drifted

## Section D - Host-owned extension contract requirements

### SR-16. Canonical manifest declarations
The lane must define one manifest shape for the first supported installable extension surface.

At minimum it must declare:
1. extension identity
2. version and compatibility
3. capability claims
4. permission scope
5. any required host-side validation inputs

### SR-17. Canonical install / validate / update path
The lane must define one canonical operator path for:
1. install
2. validate
3. update

This lane must not leave extension installation as an implied internal-only workflow.

### SR-18. Host-owned execution rule
The packet must make explicit that installable extensions do not gain runtime authority by being installable.

The host remains authoritative for:
1. policy enforcement
2. capability checks
3. namespace enforcement
4. execution truth
5. auditability

### SR-19. Compatibility and failure rules
The lane must define:
1. version compatibility expectations
2. invalid-manifest failure behavior
3. permission-mismatch failure behavior
4. unsupported-host-version behavior
5. operator-visible diagnostics expectations

### SR-20. Audit and inspectability
The lane must require an inspectable trail for supported extension lifecycle actions.

At minimum the requirements packet must name how operators can determine:
1. what was installed
2. what version is active
3. what permissions were declared
4. why validation passed or failed

## Acceptance criteria

This requirements lane is acceptable only when:
1. the four requirement families are bounded enough for direct implementation planning
2. the host-owned authority rule remains explicit across runtime, sessions, operator surfaces, and extensions
3. at least one direct implementation packet can begin without reopening basic scope questions
4. the direct implementation packet can name one canonical proof path per admitted behavior family
5. roadmap, project index, implementation plan, and requirements companion tell one story

## Proof requirements for this requirements phase

Structural proof:
1. the roadmap points to one active lane path
2. the project index records the same project and canonical folder
3. the paired implementation plan and requirements companion agree on scope and authority posture
4. no active doc implies Graphs reopen or marketplace/cloud scope through this lane

Implementation handoff requirements:
1. the first executable packet must choose exactly one approval-required capability class
2. the first executable packet must choose exactly one interrupt / pending / approve-or-reject / resume lifecycle and exactly one checkpoint-backed continuation rule
3. the first executable packet must name exactly one canonical operator action path, exactly one operator inspection path, and exactly one canonical runtime projection source
4. the first executable packet must name exactly one canonical session identity boundary and keep the terminology lock above intact
5. the first executable packet must name exactly one canonical extension manifest shape, exactly one validation path, exactly one operator-visible diagnostic path, and exactly one unsupported-host-version failure rule
