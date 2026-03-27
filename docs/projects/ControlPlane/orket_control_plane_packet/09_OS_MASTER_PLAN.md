# Orket OS Master Plan
Last updated: 2026-03-23
Status: Accepted architecture direction; not active implementation authority
Owner: Orket Core
Lane type: Strategic architecture / planning rationale

## Purpose

Describe the serious architecture target from the current Orket runtime toward an OS-grade governed workload substrate.

This document is planning rationale and architecture direction.
It is not the active implementation authority for the lane.

The archived implementation authority is:
1. [docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md)

## Target statement

Orket's near-term target is best described as:

**a governed workload microkernel plus supervisor, reconciler, and bounded operator plane**

That target becomes OS-grade to the degree that Orket can:
1. admit and run workloads under policy
2. mediate capabilities and side effects
3. supervise failures and retries
4. own reservation, resource, and lease truth
5. reconcile intended versus observed state
6. support degraded modes and operator intervention
7. preserve durable receipts and replayable control-plane history

## Why recovery belongs inside the OS path

Recovery is not a side feature.
It is one of the core mechanisms by which an execution substrate becomes trustworthy enough to deserve OS-like language.

Without recovery:
1. tooling is unsafe
2. partial execution becomes narrative
3. retries become accidental
4. resource truth is lost
5. operator control is shallow

## Accepted authority family

The architecture target now depends on the accepted authority family indexed in:
1. [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)

The most important authority surfaces in that family are:
1. glossary and enums
2. execution object model
3. lifecycle and supervision
4. failure and recovery
5. reservation, resource, and lease truth
6. reconciliation and operator semantics
7. effect journal and checkpoint authority
8. namespace and safe-tooling contracts

## Recommended control-plane architecture

The control plane should be treated as composed of the following major components:

### 1. Workload definition layer

Defines workload contracts:
1. input and output schema
2. capability declarations
3. degraded modes
4. reconciliation hooks
5. operator gate declarations

### 2. Admission and scheduling layer

Owns:
1. admission checks
2. queueing
3. reservation publication
4. concurrency control
5. retry pacing
6. blocked-state resumption gating

### 3. Supervisor

Owns:
1. lifecycle transitions
2. attempt management
3. terminal and quarantine decisions
4. recovery authorization
5. checkpoint acceptance
6. final truth closure

### 4. Effect journal

Owns durable ordered records of:
1. intended effects
2. authorized effects
3. attempted effects
4. observed results
5. uncertainty classes
6. compensation or reconciliation links

### 5. Reservation, lease, and resource registry

Owns:
1. reservation registration
2. resource registration
3. ownership state
4. lease epochs
5. cleanup authority
6. orphan status
7. last observed truth

### 6. Reconciler

Owns:
1. observation collection under defined scope
2. intended versus observed comparison
3. divergence classification
4. safe continuation classification

### 7. Operator plane

Owns:
1. inspection
2. bounded commands
3. explicit human approvals, risk acceptance, and attestations
4. auditable intervention history

## Architecture constraints carried into implementation

The following constraints are now frozen as part of the accepted packet:
1. `Reservation` is first-class.
2. `FinalTruthRecord` is first-class.
3. `recovering` is control-plane activity rather than normal execution.
4. operator risk acceptance is never evidence of world state.
5. operator attestation is policy-bounded and visibly distinct from observation.
6. the effect journal is a normative authority surface, not mere storage.
7. a slim namespace contract exists now rather than being deferred entirely.

## Planning status

The missing companion contracts that previously blocked implementation planning now exist:
1. [10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md)
2. [11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md)
3. [12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md)

The lane's implementation sequencing archive lives in:
1. [docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md)

## Final framing

The goal is not to make Orket look like an OS.
The goal is to make Orket capable of the responsibilities that justify OS-like language for governed AI workloads.

That still means:
1. explicit objects
2. explicit authority
3. explicit supervision
4. explicit reservation, resource, and lease truth
5. explicit reconciliation
6. explicit degraded modes
7. explicit operator control
8. explicit proof
