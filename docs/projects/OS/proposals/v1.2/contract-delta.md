# v1.2 Contract Delta (Proposal)

Last updated: 2026-02-24
Status: Execution-ready proposal (non-authoritative until promotion)

## Purpose
Define the proposed contract/schema deltas derived from `docs/projects/ideas/Ideas.md`, with explicit compatibility boundaries for `kernel_api/v1` tightening.

Decision baseline:
1. `kernel_api/v1` tightening is locked.
2. No silent semantic swap of existing fields.
3. If semantics evolve, use additive fields or parallel schema branches.

## Baseline (Current Authority)
Current authoritative contracts are listed in:
1. `docs/projects/OS/contract-index.md`
2. `docs/projects/OS/contracts/*`

## Proposed Additions and Changes

### 1. `docs/projects/OS/contracts/stage-order-v1.json` (new)
Purpose:
1. Single source of truth for stage ordering used by comparator/report sorting.

Proposed shape:
1. `contract_version: "kernel_api/v1"`
2. `stage_order: [...]` with explicit deterministic order

### 2. `docs/projects/OS/contracts/error-codes-v1.json` (wrapper-form instance)
Purpose:
1. Canonical registry payload whose full wrapper bytes are digest inputs (D5).

Required digest surface:
1. `{ "contract_version": "...", "codes": { ... } }`

Compatibility constraint:
1. Migration must avoid silent semantic swaps in v1 by using explicit schema compatibility handling during rollout.

### 3. `docs/projects/OS/contracts/capability-decision-record.schema.json` (new)
Purpose:
1. Canonical parity artifact emitted once per tool attempt.

Proposed required fields:
1. `decision_id`, `run_id`, `turn_id`, `tool_name`, `action`, `ordinal`
2. `outcome`, `stage`, `deny_code`, `info_code`, `reason`, `provenance`

Proposed invariants:
1. `allowed` requires provenance; deny/info null.
2. `denied` requires deny_code; provenance null.
3. `skipped` requires `info_code == I_CAPABILITY_SKIPPED`.
4. `unresolved` requires `deny_code == E_CAPABILITY_NOT_RESOLVED`.

### 4. `docs/projects/OS/contracts/turn-result.schema.json` (coexistence patch)
Purpose:
1. Carry current and new capability parity surfaces in one migration window.

Locked coexistence naming:
1. Keep existing `capabilities.decisions` semantics unchanged.
2. Add `capabilities.decisions_v1_2_1` for `CapabilityDecisionRecord[]`.
3. Comparator parity uses `decisions_v1_2_1` once present on both sides.

### 5. `docs/projects/OS/contracts/replay-bundle.schema.json` (new)
Purpose:
1. Sovereign replay input manifest for deterministic compare/replay.

Required fields:
1. `contract_version`
2. `run_envelope`
3. `registry_digest`
4. `digests`
5. `turn_results[]` with `paths` and digest metadata

### 6. `docs/projects/OS/contracts/replay-report.schema.json` (tighten existing)
Purpose:
1. Canonical comparator output with deterministic report identity.

Proposed tightening:
1. Structured `mismatches[]` with required sort fields.
2. Nullable digest fields for schema/ERROR pathways.
3. Explicit `report_id` derivation rule with diagnostic nullification (D6, D8).

### 7. Canonicalization and digest docs (new)
Artifacts:
1. `docs/projects/OS/contracts/canonicalization-rules.md`
2. `docs/projects/OS/contracts/decision-id-derivation.md`
3. `docs/projects/OS/contracts/digest-surfaces.md`

Purpose:
1. Lock byte-level canonicalization and digest inclusion/exclusion surfaces.

## Compatibility Risk Summary
1. Additive contracts (`stage-order`, `replay-bundle`): low.
2. Replay report tightening: medium; keep additive where possible.
3. DecisionRecord coexistence: medium; explicit dual-surface migration reduces break risk.
4. Registry wrapper and digest lock: medium; requires careful compatibility validation.
5. Runtime digest-surface tightening: medium; must be paired with replay vector updates.
