# Card 007 - Capability Jail

## Scope
Enforce deny-by-default capability and permission boundaries.

## Deliverables
1. Capability decision contract.
2. Tool authorization decision surface.

## Acceptance Criteria
1. Undeclared permissions denied deterministically.
2. Audit fields present for allow/deny outcomes.

## Test Gates
1. Permission deny tests.
2. Side-effect undeclared tests.

## Dependencies
Cards 001 and 005.

## Non-Goals
Host sandbox implementation details.
