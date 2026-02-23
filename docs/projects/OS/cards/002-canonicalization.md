# Card 002 - Canonicalization

## Scope
Freeze canonical serialization and pointer rules across kernel contracts.

## Deliverables
1. Canonicalization policy docs.
2. Contract fixture examples.
3. Golden digest vectors in `tests/kernel/v1/vectors/digest-v1.json`.
4. TypeScript conformance harness under `conformance/ts/`.

## Acceptance Criteria
1. Stable hashes across repeated runs.
2. RFC6901 pointers validated.
3. Python and TypeScript produce identical canonical strings and digest values for committed vectors.
4. Digest failures emit `E_DIGEST_*` codes (not umbrella promotion errors).

## Test Gates
1. Canonical serialization fixtures pass.
2. Pointer pattern checks pass.
3. Digest vector parity passes in both runtimes.

## Dependencies
Card 001.

## Non-Goals
Provider-specific optimization.
