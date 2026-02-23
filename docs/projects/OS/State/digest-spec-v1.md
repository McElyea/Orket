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
1. Canonical JSON MUST follow RFC 8785 (JCS).
2. Orket v1 constraint: digested structures MUST use integer-only numeric values.
3. Non-finite numbers are forbidden.
4. Encountering non-integer or non-finite numbers MUST fail determinism with a stable code (`E_NON_INTEGER_NUMBER` and/or `E_INTEGER_OUT_OF_RANGE`).

## Digest Input Rules
1. Input bytes are UTF-8 bytes of canonical JSON output.
2. No BOM.
3. No framing prefix/suffix.
4. No trailing newline is appended for digest input.

## Digest Algorithm
1. Hash algorithm: SHA-256.
2. Output encoding: lowercase hex.
3. Pattern: `^[a-f0-9]{64}$`.

## Compliance Requirements
1. Identical JSON values across implementations MUST produce identical digest strings.
2. Cross-language conformance vectors are required in CI.
3. Replay/compare tests MUST use these rules as the only digest authority.

## Non-goals
1. This digest is not a trust primitive.
2. No signing, salting, or key management is defined here.
