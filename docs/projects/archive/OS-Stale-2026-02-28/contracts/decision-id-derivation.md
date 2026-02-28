# Decision ID Derivation (v1.2)

Last updated: 2026-02-24
Status: Normative for v1.2 execution

## Purpose
Define deterministic `decision_id` derivation for `CapabilityDecisionRecord`.

## Input Projection
1. Build a canonical projection with fields:
   - `contract_version`
   - `run_id`
   - `turn_id`
   - `tool_name`
   - `action`
   - `ordinal`
   - `outcome`
   - `stage`
   - `deny_code`
   - `info_code`
   - `reason`
   - `provenance`
2. Preserve key presence for nullable values (`null`, not omission).

## Derivation
1. Canonicalize projection bytes using `canonicalization-rules.md`.
2. Compute `decision_id = sha256(canonical_bytes)` lowercase hex.

## Stability Constraints
1. Host-local path differences and diagnostic-only text outside the projection must not change `decision_id`.
2. Any parity-relevant field change in projection must change `decision_id`.
