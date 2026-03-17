# Truthful Runtime Source Attribution Contract

Last updated: 2026-03-16
Status: Active
Owner: Orket Core
Phase closeout authority: `docs/projects/archive/truthful-runtime/TRH03162026-PHASE-C-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
2. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`

## Purpose

Define the durable packet-2 source-attribution and evidence-first contract for bounded high-stakes truthful-runtime lanes.

## Current Scope

This contract currently covers:
1. one canonical receipt artifact at `agent_output/source_attribution_receipt.json`
2. the packet-2 `source_attribution` summary surface
3. high-stakes gating when `source_attribution_mode = required`

Out of scope:
1. semantic fact-checking of claim text beyond structural source grounding
2. non-workspace citation providers
3. Phase D trust-level synthesis behavior

## Canonical Summary Surface

Packet-2 additive key:
1. `truthful_runtime_packet2.source_attribution`

Minimum emitted shape:

```json
{
  "mode": "required",
  "high_stakes": true,
  "synthesis_status": "verified",
  "claim_count": 1,
  "source_count": 3,
  "missing_requirements": [],
  "artifact_provenance_verified": true,
  "receipt_artifact_path": "agent_output/source_attribution_receipt.json"
}
```

Optional additive fields:
1. `claims`
2. `sources`
3. `receipt_operation_id`

## Mode Rules

Stable `mode` values:
1. `optional`
2. `required`

Stable `synthesis_status` values:
1. `verified`
2. `optional_unverified`
3. `blocked`

Mode semantics:
1. `required` implies `high_stakes = true`
2. `blocked` is emitted only when `mode = required` and `missing_requirements` is non-empty
3. `optional_unverified` is emitted when receipt structure is incomplete but the lane is not gated

## Receipt Contract

Canonical artifact path:
1. `agent_output/source_attribution_receipt.json`

Required claim fields:
1. `claim_id`
2. `claim`
3. `source_ids`

Required source fields:
1. `source_id`
2. `title`
3. `uri`
4. `kind`

Receipt rules:
1. `claims` must be a non-empty list for verified synthesis.
2. `sources` must be a non-empty list for verified synthesis.
3. every claim `source_ids` set must be a subset of declared source `source_id` values.
4. additive metadata is allowed, but the required claim/source fields must remain present and non-empty.

Stable `missing_requirements` values:
1. `source_attribution_receipt_missing`
2. `source_attribution_receipt_invalid_json`
3. `source_attribution_claims_missing`
4. `source_attribution_sources_missing`
5. `source_attribution_claim_source_missing`
6. `source_attribution_source_fields_missing`

## Provenance Coupling

1. `artifact_provenance_verified` is `true` only when `truthful_runtime_artifact_provenance` includes the receipt artifact path.
2. `receipt_operation_id` is emitted only when the authoritative artifact-provenance entry exposes a stable `operation_id`.
3. Source attribution does not replace artifact provenance; it layers claim/source structure on top of it.

## Gate Rule

1. When `synthesis_status = blocked` and the finalized run would otherwise be `done`, the runtime must downgrade the run to `terminal_failure`.
2. The terminal `failure_reason` must be the first stable missing-requirement token.
3. High-stakes source attribution gating must be machine-readable and must not rely on prose-only warnings.

## Live Evidence Authority

1. Provider-backed suite: `tests/live/test_truthful_runtime_phase_c_completion_live.py`
2. Structural integration coverage: `tests/application/test_execution_pipeline_run_ledger.py`
