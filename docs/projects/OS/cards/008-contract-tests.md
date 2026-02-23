# Card 008 - Contract Tests

## Scope
Add kernel API compatibility and schema contract gates.

## Deliverables
1. `tests/kernel/v1/*` compatibility tests.
2. Contract fixture validation in CI.

## Acceptance Criteria
1. Versioning policy enforced by tests.
2. Breaking shape changes fail without major version bump.

## Test Gates
1. Full kernel contract suite green.
2. Fire-drill suite green.

## Dependencies
All prior cards.

## Non-Goals
Performance benchmarking.
