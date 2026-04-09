# Orket Control-Plane Foundation Packet
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation

## Purpose

Define the minimum aligned control-plane foundation required for Orket to:
1. supervise governed workloads
2. classify and recover from execution and truth failures
3. preserve authoritative state through partial or uncertain execution
4. reconcile durable intent against observed world state
5. expose a bounded operator control surface
6. move toward OS-grade governed workload execution without inventing upper-layer behavior too early

## Scope

This packet defines the aligned foundation for:
1. shared control-plane vocabulary and enums
2. current-state migration honesty
3. execution object model
4. workload lifecycle and supervision
5. failure taxonomy and recovery
6. capability and effect model
7. resource reservation, lease, and ownership semantics
8. reconciliation authority
9. operator control surface
10. minimal admission and scheduling requirements
11. effect journal and checkpoint authority
12. namespace and workload composition
13. safe tooling workload integration

## Out of scope

This packet does not define:
1. companion UX behavior
2. memory and retrieval semantics
3. planner sophistication
4. rich DAG orchestration beyond minimum lifecycle needs
5. distributed cluster architecture
6. marketplace-scale packaging semantics
7. broad product positioning

Those surfaces may consume this control plane later, but must not define it.

## Design stance

Orket is treated here as a governed workload runtime whose control plane must satisfy these properties:

1. authority clarity
2. truth by record and observation
3. side-effect awareness
4. durable supervision
5. recoverable state
6. degraded operation
7. current-state honesty

## Core architectural assertion

The control plane must be designed as one machine, but specified as separate interlocking gears.

Implementation order must follow dependency order.
Cross-coupled design that allows later surfaces to redefine earlier nouns is prohibited.

## Authority set

### Shared authority

1. `00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md`

### Current-state honesty

1. `00B_CURRENT_STATE_CROSSWALK.md`

### Requirement authorities

1. `01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md`
2. `02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md`
3. `03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md`
4. `04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md`
5. `05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md`
6. `06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md`
7. `07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md`
8. `08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md`
9. `10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md`
10. `11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md`
11. `12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md`

### Planning companions

1. `09_OS_MASTER_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md`

## Cross-packet invariants

The following invariants apply across the whole packet.

### FP-01. Runtime truth authority

The runtime is the authority for:
1. workload lifecycle transitions
2. failure classification
3. recovery authorization
4. reservation and lease mutation authorization
5. reconciliation result publication
6. operator command validation
7. final execution truth publication

### FP-02. Models are non-authoritative proposers

A model or decision node may:
1. propose work
2. propose tool actions
3. propose explanations
4. propose hypotheses
5. propose recovery candidates where allowed

A model or decision node may not:
1. classify final execution truth
2. assert side effects as completed without authoritative evidence
3. authorize recovery
4. mutate reservation or lease state directly
5. publish reconciliation truth
6. override operator or runtime authority

### FP-03. Narrative is never authority

Natural-language output, including apologies, explanations, or confidence statements, must never fill a proof gap left by missing receipts, missing observations, or missing reconciliation.

### FP-04. Side-effect boundary classification is mandatory

Every failed or interrupted attempt must be classified at minimum as one of:
1. `pre_effect_failure`
2. `effect_boundary_uncertain`
3. `post_effect_observed`

Recovery policy must depend on this classification.

### FP-05. Reservation and lease truth are distinct

`Reservation` and `Lease` are different first-class control-plane objects.

Reservation is pre-execution claim truth.
Lease is active execution ownership or mutation authority.

### FP-06. Receipts and journals are durable control surfaces

Any recovery-relevant event must produce durable machine-readable evidence sufficient to explain:
1. what was attempted
2. under what capability and policy
3. what was observed
4. what remained uncertain
5. what action was authorized next
6. why that action was allowed

### FP-07. Reconciliation precedes unsafe continuation

Where effect uncertainty, resource uncertainty, or contradiction exists, reconciliation must occur before continuation unless policy explicitly permits bounded degraded behavior without continuation.

### FP-08. Operator actions are explicit and auditable

Operator interventions must be explicit recorded inputs and must not be simulated by hidden runtime behavior.

### FP-09. Operator risk acceptance is not evidence

Operator risk acceptance may authorize continuation under bounded conditions.
It may not satisfy evidence requirements for world-state truth.

### FP-10. Final truth is a first-class record

Run closure must publish a first-class `FinalTruthRecord`.
Terminality may be affected by operator action or policy, but truth classification may not be rewritten by command.

### FP-11. Control-plane-first layering

Recovery, resource ownership, capability classes, supervision, effect journaling, and final-truth publication are control-plane concerns.
Tool-specific logic may extend these surfaces but may not redefine their core vocabulary.

## Planning readiness

This packet is ready for implementation planning because it now includes:
1. one shared glossary and enum authority
2. one honest current-state crosswalk
3. explicit reservation and final-truth first-class objects
4. explicit operator evidence boundaries
5. the missing companion requirement families needed by the master plan

## Implementation authority history

No active ControlPlane implementation lane remains after the completed convergence closeout.

The latest archived convergence implementation authority is:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`

The archived packet-v2 implementation authority for this lane is:
1. `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md`

`09_OS_MASTER_PLAN.md` remains architecture direction and planning rationale only.
