# Resource Lease and Ownership Requirements
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation / resource truth

## Purpose

Define the minimum reservation, ownership, and lease semantics required for Orket to survive partial execution, crashes, retries, cleanup, and reconciliation without losing authoritative control over resources.

## Authority note

Shared ownership, orphan, reservation, and lease enums are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

## Core assertion

A resource that matters to execution truth must not be tracked only as an incidental adapter detail.

If a resource can:
1. survive an attempt boundary
2. be leaked
3. be mutated
4. block retries
5. require cleanup
6. affect final truth

then it must participate in control-plane ownership and lease semantics.

## Required resource semantics

### RL-01. Resource registration

A resource that enters governed scope must be registered with at minimum:
1. resource identifier
2. resource kind
3. namespace or scope
4. provenance reference
5. current owner if any
6. cleanup authority class
7. current reconciliation status

### RL-02. Ownership classes

Ownership classes are canonical in the glossary.
Ownership class must influence cleanup and recovery rules.

## Reservation and lease semantics

### RL-03. Reservation requirement

A reservation is required whenever:
1. admission or scheduling publishes a claim on capacity, resource scope, or concurrency scope
2. execution has not yet begun ownership or mutation
3. starvation or exclusivity behavior depends on durable claim truth

### RL-04. Reservation-to-lease progression

The control plane must distinguish:
1. reservation as pre-execution claim truth
2. lease as active ownership or mutation authority

Promotion from reservation to lease must be:
1. explicit
2. supervisor-owned
3. durable
4. auditable

### RL-05. Lease requirement

A lease is required whenever:
1. a resource may outlive a step
2. retries or concurrent runs could contend for it
3. cleanup depends on authoritative ownership
4. mutation requires fencing or exclusivity

### RL-05A. Lease publication

Lease truth must be publishable as append-only snapshots.
Where a stable logical `lease_id` survives renewal, expiry, uncertainty, or verified release, publication order must remain reconstructable through lease epoch plus publication timestamp without overwriting earlier lease truth.

### RL-06. Lease epoch fencing

Lease mutation and resource mutation requiring exclusive control must use lease epoch or equivalent fencing semantics strong enough to prevent stale actors from claiming authority after recovery or retry.

## Cleanup authority

### RL-07. Cleanup authority classes

Minimum cleanup authority classes remain:
1. `runtime_cleanup_allowed`
2. `runtime_cleanup_after_reconciliation`
3. `operator_cleanup_required`
4. `adapter_cleanup_only`
5. `cleanup_forbidden_without_external_confirmation`

### RL-08. Cleanup is a governed action

Cleanup is not an invisible maintenance detail.
Where cleanup affects truth, recovery, cost, or external state, it must be recorded as a governed effect.

## Orphans and uncertainty

### RL-09. Orphan classifications

Orphan classifications are canonical in the glossary.

### RL-10. Resource uncertainty

Where resource state cannot be confirmed, the control plane must publish uncertainty rather than assuming deletion, release, or non-existence.

### RL-11. Orphan handling

A verified or suspected orphan must trigger:
1. reconciliation or inventory pass
2. operator escalation
3. bounded cleanup allowed by policy and cleanup authority class

## Lease and lifecycle coupling

### RL-12. Attempt failure with active reservations or leases

If an attempt fails or is interrupted while reservations or active leases exist, the supervisor must determine before unsafe continuation:
1. whether the reservation still holds
2. whether any lease remains valid
3. whether the associated resources remain in expected state
4. whether transfer, release, or revocation is needed
5. whether reconciliation is required

### RL-13. Lease transfer

Lease transfer across attempts or run states must be explicit and recorded.
Implicit carry-forward is prohibited where ownership affects safety or cleanup.

## Shared and external resources

### RL-14. Shared governed resources

Shared governed resources must use namespace and ownership semantics strong enough to prevent one run from cleaning up or mutating another run's resources without explicit policy.

### RL-15. External unowned references

Resources that Orket does not own may still require observation and reconciliation, but lack of ownership must constrain cleanup and mutation claims.

## Acceptance criteria

This draft is acceptable only when:
1. resource truth can survive attempt failure
2. cleanup authority is explicit rather than accidental
3. reservation and lease remain distinguishable and auditable
4. leases fence stale ownership after retries or crashes
5. orphan detection becomes a real control-plane output
6. sandbox lifecycle work can plug into this model without redefining ownership
