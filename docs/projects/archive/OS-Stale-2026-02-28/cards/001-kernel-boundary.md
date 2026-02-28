# Card 001 - Kernel Boundary

## Scope
Define and freeze `orket/kernel/v1` module boundary.

## Deliverables
1. `orket/kernel/v1` package skeleton.
2. Adapter split between sentinel CLI and kernel service.

## Acceptance Criteria
1. Sentinel runs via kernel service entrypoints.
2. No runtime kernel logic in docs path.

## Test Gates
1. Import tests for kernel package.
2. Fire-drill compatibility preserved.

## Dependencies
None.

## Non-Goals
Full runtime rewrite.
