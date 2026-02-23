# Card 002 - Canonicalization

## Scope
Freeze canonical serialization and pointer rules across kernel contracts.

## Deliverables
1. Canonicalization policy docs.
2. Contract fixture examples.

## Acceptance Criteria
1. Stable hashes across repeated runs.
2. RFC6901 pointers validated.

## Test Gates
1. Canonical serialization fixtures pass.
2. Pointer pattern checks pass.

## Dependencies
Card 001.

## Non-Goals
Provider-specific optimization.
