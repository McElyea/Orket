# Card 002 - Canonicalization

## Scope
Freeze canonical serialization and pointer rules across kernel contracts.

## Deliverables
1. Canonicalization policy docs.
2. Contract fixture examples.
3. Golden digest vectors in `tests/kernel/v1/vectors/digest-v1.json`.
4. TypeScript conformance harness under `conformance/ts/`.
5. Digest declaration validation for `envelope.digest.algorithm` + `envelope.digest.hex`.

## Acceptance Criteria
1. Stable hashes across repeated runs.
2. RFC6901 pointers validated.
3. Python and TypeScript produce identical canonical strings and digest values for committed vectors.
4. Digest failures emit `E_DIGEST_*` codes (not umbrella promotion errors).
5. Canonical bytes rule is enforced (`UTF-8 canonical JSON + exactly one trailing LF`).
6. Byte-gate failures map deterministically (`E_DIGEST_INVALID_UTF8`, `E_DIGEST_TRAILING_NEWLINE_REQUIRED`, `E_DIGEST_NORMALIZATION_MISMATCH`).
7. Numbers are integer-only in v1 with deterministic failure (`E_DETERMINISM_INVALID_NUMBER`).

## Test Gates
1. Canonical serialization fixtures pass.
2. Pointer pattern checks pass.
3. Digest vector parity passes in both runtimes.
4. Committed-vector-only CI behavior is enforced (regen+diff allowed, overwrite forbidden).

## Dependencies
Card 001.

## Non-Goals
Provider-specific optimization.
