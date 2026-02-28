# Persistence Snapshot Contract (v1)

Last updated: 2026-02-22
Status: Normative

## Snapshot Rules
1. Snapshot boundaries are explicit and versioned.
2. Snapshot creation is atomic at contract boundary.
3. Snapshot identifiers are immutable.

## Reproducibility
1. Canonical serialization is required for snapshot hashes.
2. Cross-platform canonicalization must produce identical bytes.
3. Canonicalization and digest rules are normatively defined in `State/digest-spec-v1.md`.

## Recovery
1. Crash recovery must not produce partial committed state.
2. Recovery path must emit deterministic error codes.
