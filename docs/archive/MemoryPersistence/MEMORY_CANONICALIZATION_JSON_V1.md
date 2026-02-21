# Memory Canonicalization JSON v1

## Schema Version
`memory.canonicalization.json.v1`

## Purpose
Define one canonical serialization format used for:
1. `normalized_args`
2. `query_fingerprint` inputs
3. `tool_result_fingerprint` inputs
4. `side_effect_fingerprint` inputs
5. `output_shape_hash` structural inputs
6. `commit_payload_fingerprint` inputs

## Required Canonicalization Rules
1. Encoding: UTF-8.
2. Value domain: JSON objects, arrays, and scalars only.
3. Object key order: lexicographic ascending.
4. Float normalization: fixed precision (6 decimal places for v1).
5. NaN/Infinity: prohibited unless pre-normalized to explicit strings by upstream schema policy.
6. Output formatting: minified (no pretty-print whitespace).

## Trace Fields
Any artifact that uses canonicalization must log:
1. `normalization_version` (must be `json-v1` for this spec)
2. Hash algorithm where applicable (default `sha256` in v1 contracts)

## Open Clarifications (Phase 0 Closure Required)
1. Unicode normalization form: `NFC` (required for string canonicalization).
2. Datetime normalization format: ISO 8601 UTC with trailing `Z`.
3. Missing vs `null` policy:
missing means field omitted;
`null` means field explicitly present with null value.
Canonicalization must preserve this distinction.

## Determinism Notes
1. Producers must normalize strings to `NFC` before serialization.
2. Datetime values must be normalized to UTC before canonicalization.
3. Required fields may not be omitted; optional fields may be omitted or explicitly `null` per schema.

## Evolution Rules
1. Changes to required canonicalization behavior require a new version.
2. A new version must provide migration guidance and compatibility tests.
