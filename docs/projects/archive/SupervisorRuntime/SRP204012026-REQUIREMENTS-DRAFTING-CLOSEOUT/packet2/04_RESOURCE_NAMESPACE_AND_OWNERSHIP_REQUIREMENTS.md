# Resource Namespace And Ownership Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 2

## Purpose

Define resource targeting, namespace boundaries, and active ownership as one default-path authority family.

## Draft requirements

1. Reservation must remain explicit admission or claim truth where exclusivity or scheduling is involved.
2. Lease must remain explicit active ownership truth for governed mutation or exclusive control.
3. Resource truth must converge toward one general model rather than subsystem-specific authority families.
4. Namespace must be an explicit boundary for mutation, ownership, child composition, and resource targeting.
5. Packet 2 must deny ambient namespace visibility or implicit shared-resource mutation.

## Non-goals

1. full multitenant platform design
2. distributed lock-service design
3. sandbox-only special casing as a permanent authority story
