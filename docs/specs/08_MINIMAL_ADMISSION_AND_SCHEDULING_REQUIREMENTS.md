# Minimal Admission and Scheduling Requirements
Last updated: 2026-04-09
Status: Active durable spec authority
Owner: Orket Core
Lane type: Control-plane foundation / minimal scheduler

## Purpose

Define the minimum admission and scheduling semantics required so execution, retries, recovery, reservations, leases, and resource ownership do not conflict.

## Authority note

Reservation and lease enums are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

## Core assertion

Orket does not need a giant scheduler yet.
It does need enough scheduling truth that workloads, retries, recovery, and resource ownership do not fight each other.

## Admission requirements

### AS-01. Admission checks

Before entering `admitted`, a run must pass checks at minimum for:
1. workload validity
2. policy resolution
3. required capability allowance
4. resource preconditions known at admission time
5. concurrency or exclusivity constraints
6. operator gates required prior to start

### AS-02. Admission outputs

Admission must publish:
1. admitted or rejected result
2. reason
3. reservation references if claims were created
4. initial execution mode
5. operator requirement if any

## Reservation semantics

### AS-03. Reservation scopes

The control plane must support reservation scopes at minimum for:
1. resource claims
2. concurrency claims
3. namespace-scoped exclusivity if required by policy

### AS-04. Reservation publication and expiry

If admission or scheduling creates a reservation, it must publish:
1. reservation identifier
2. holder reference
3. reservation kind
4. target scope or resource
5. status
6. expiry or invalidation basis

### AS-05. Promotion to lease

Reservations and leases belong to the same object family but are different authority states.

Promotion from reservation to lease must be:
1. explicit
2. durable
3. supervisor-controlled
4. tied to actual execution ownership or mutation authority

### AS-06. Release and invalidation

Reservation release or invalidation must be explicit on:
1. failure
2. cancellation
3. timeout
4. operator stop

## Scheduling semantics

### AS-07. Minimum scheduling concepts

The control plane must support at minimum:
1. queue eligibility
2. concurrency limit checks
3. retry pacing or backoff
4. blocked-state resumption conditions
5. starvation avoidance intent
6. cancellation handling

### AS-08. Concurrency and exclusivity

Scheduling must respect:
1. reservation exclusivity
2. lease exclusivity
3. destructive capability gating
4. workload-declared serialization requirements
5. operator-imposed holds

### AS-09. Retry pacing

Retries and recovery attempts must be schedulable as distinct work with policy-controlled pacing.
Immediate infinite retry loops are prohibited.

### AS-10. Recovery-aware scheduling

A run in `recovery_pending`, `reconciling`, `operator_blocked`, or `quarantined` must not be scheduled as ordinary executable work until its gating conditions are resolved.

## Prioritization and fairness

### AS-11. Priority model

A minimal priority model may exist, but any priority behavior must not override explicit safety, reservation, lease, or operator constraints.

### AS-12. Starvation prevention

The scheduler must avoid allowing repeated retries or high-frequency workloads to starve:
1. reconciliation work
2. operator-unblocked continuations
3. cleanup-critical tasks

## Cancellation and shutdown

### AS-13. Cancellation semantics

Cancellation must:
1. be an explicit event
2. preserve current attempt truth
3. account for active reservations, leases, and possible cleanup
4. trigger reconciliation where required

## Acceptance criteria

This draft is acceptable only when:
1. admission outputs align with the execution object model
2. reservation truth is explicit, durable, and promotable to lease
3. retries behave like governed scheduled work rather than silent loops
4. safety gates override convenience scheduling
5. blocked and quarantined states are respected
