# Public Control Surface Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 4

## Purpose

Define the outward operator and programmatic control surfaces Packet 2 expects.

## Draft requirements

1. Packet 2 must describe one coherent public control surface for runs, approvals, artifacts, replay, and inspection.
2. Public control surfaces must project host-owned authority rather than author it.
3. Event and inspection surfaces must stay compatible with published run, attempt, operator, recovery, and final-truth records.
4. Public surfaces must fail closed on malformed or contradictory underlying authority.
5. Packet 2 must keep transport shape secondary to authority shape.

## Non-goals

1. full frontend product design
2. cloud API product packaging
3. alternate public APIs that bypass host-owned authority
