# Digest Spec (v1)

Status: Normative
Version: `lsi/v1`

## Purpose and Scope
Define deterministic, cross-language structural digest rules for Orket artifacts and reports.

This spec applies wherever `StructuralDigest` is used, including:
1. Turn transition evidence.
2. Replay parity digests.
3. Artifact and bundle digests.

## Canonicalization Authority
1. Orket v1 uses a JCS-inspired subset. RFC 8785 is inspiration only.
2. Where behavior differs, this spec is authoritative.

## Canonical Bytes Rule
1. `canonical_bytes = UTF8(canonical_json_text) + b"\n"`.
2. Exactly one trailing LF (`0x0A`) is required.
3. CR (`\r`) is forbidden anywhere in canonical bytes.
4. Double LF or trailing padding is forbidden.

Deterministic precedence:
1. Raw bytes validation.
2. UTF-8 validity check.
3. Physical layout checks (exactly one LF, no CR, no extra padding).
4. Canonicalization.
5. Hashing.

## Canonical JSON Subset
### Strings
1. Use literal Unicode (`ensure_ascii=false`).
2. Escape only `"`, `\\`, and control characters (`U+0000` to `U+001F`).

### Numbers
1. Integers only in v1.
2. Allowed range: `[-2^53+1, 2^53-1]`.
3. Out-of-range or non-integer values MUST fail with `E_DETERMINISM_INVALID_NUMBER`.
4. `-0` MUST canonicalize as `0`.

### Objects
1. Keys MUST be sorted by UTF-8 encoded byte sequence, ascending.
2. No insignificant whitespace.

### Arrays
1. Preserve element order.
2. Canonicalize each element recursively.

## Digest Algorithm
1. Algorithm identifier: `sha256` (lowercase).
2. Hash input is canonical bytes (including the required trailing LF).
3. Output encoding is lowercase hex.
4. Pattern: `^[a-f0-9]{64}$`.

## Declared Digest Path (v1 Envelope)
1. Declared digest location is `envelope.digest`.
2. `envelope.digest.algorithm` MUST equal `sha256`.
3. `envelope.digest.hex` MUST be lowercase 64-char hex.
4. Alternate algorithm-as-key shapes are non-normative for v1.

## Digest Failure Mapping
Deterministic precedence by validation path:

Path A (declared digest fields under `envelope.digest`):
1. Missing `envelope.digest` or missing required digest fields -> `E_DIGEST_NON_CANONICAL_JSON`
2. Algorithm mismatch -> `E_DIGEST_ALGORITHM_MISMATCH`
3. Hex format violation -> `E_DIGEST_HEX_INVALID`
4. Hex length mismatch -> `E_DIGEST_LENGTH_MISMATCH`

Path B (canonical bytes and digest verification):
1. Invalid UTF-8 -> `E_DIGEST_INVALID_UTF8`
2. Missing trailing LF -> `E_DIGEST_TRAILING_NEWLINE_REQUIRED`
3. CR/double-LF/padding drift -> `E_DIGEST_NORMALIZATION_MISMATCH`
4. Canonicalization deviation -> `E_DIGEST_NON_CANONICAL_JSON`
5. Digest value mismatch -> `E_DIGEST_VALUE_MISMATCH`

## Compliance Requirements
1. Identical inputs across implementations MUST produce identical canonical strings and digest values.
2. Cross-language conformance vectors are required in CI.
3. CI consumes committed vectors and MUST NOT overwrite them.
4. CI MAY regenerate vectors and compare for parity, but write-back is forbidden in CI.
5. Replay/compare tests MUST use this spec as the only digest authority.

## Golden Vector Contract
1. Vector file path: `tests/kernel/v1/vectors/digest-v1.json`.
2. Top-level shape MUST include:
- `version: "digest-v1"`
- `algorithm: "sha256"`
- `vectors: [...]`
3. Vector kinds:
- Object vectors:
  - `name`, `input`, `canonical`, `digest_hex`
- Raw-byte vectors:
  - `name`, `raw_utf8` or `raw_b64`, `expect_error`
4. Invalid UTF-8 vectors MUST use `raw_b64`.
5. CI consumes committed vectors and may compare regenerated output, but must never overwrite committed vectors.

## Conformance Harness
1. Python maintainer command for vector regeneration: `python scripts/gen_digest_vectors.py`.
2. Python gate: `python -m pytest -q tests/kernel/v1`.
3. TypeScript parity gate: `npm test --prefix conformance/ts`.
4. CI is consume-only for committed vectors; regeneration in CI is diff-only.

## Non-goals
1. This digest is not a trust primitive.
2. No signing, salting, or key management is defined here.
