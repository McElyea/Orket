# v1.2 Contract Delta (Proposal)

Last updated: 2026-02-24
Status: Draft proposal (non-authoritative)

## Purpose
Define proposed contract/schema deltas derived from `docs/projects/ideas/Ideas.md` before any authoritative promotion.

## Baseline (Current Authority)
Current authoritative contracts are listed in:
1. `docs/projects/OS/contract-index.md`
2. `docs/projects/OS/contracts/*`

## Proposed Additions

### 1. `contracts/stage-order-v1.json` (new)
Purpose:
1. Single source of truth for stage ordering and replay join/sort semantics.

Proposed shape:
1. `contract_version: "kernel_api/v1"`
2. `stage_order: ["base_shape","dto_links","relationship_vocabulary","policy","determinism","ci","lsi","promotion","capability","replay"]`

### 2. `contracts/capability-decision-record.schema.json` (new)
Purpose:
1. Canonical parity artifact emitted once per tool attempt.

Proposed required fields:
1. `decision_id`, `run_id`, `turn_id`, `tool_name`, `action`, `ordinal`
2. `outcome`, `stage`, `deny_code`, `info_code`, `reason`, `provenance`

Proposed invariants:
1. `allowed` => provenance required, deny/info null.
2. `denied` => deny_code required, provenance null.
3. `skipped` => `info_code == I_CAPABILITY_SKIPPED`, deny null, reason required.
4. `unresolved` => `deny_code == E_CAPABILITY_NOT_RESOLVED`.

### 3. `contracts/replay-bundle.schema.json` (new)
Purpose:
1. Sovereign replay input manifest for deterministic compare/replay.

Proposed required fields:
1. `contract_version: "replay_bundle/v1"`
2. `run_envelope`
3. `registry_digest`
4. `digests` (policy/runtime/registry snapshot)
5. `turn_results[]` (`turn_id`, `turn_result_digest`, `paths[]`)

### 4. `contracts/replay-report.schema.json` (tighten existing)
Purpose:
1. Canonical comparator output with deterministic report identity.

Proposed additions/tightening:
1. Explicit `status`, `exit_code`, and structured `mismatches[]`.
2. Stable mismatch sort and canonical `report_id` derivation rule.
3. Diagnostic fields explicitly excluded from `report_id` hash input.

### 5. `contracts/error-codes-v1.json` (extend existing)
Purpose:
1. Include full v1.2 fortress code set for capability/replay/determinism/registry lock.

Proposed additions:
1. `E_REGISTRY_DIGEST_MISMATCH`
2. `E_CANONICALIZATION_ERROR`
3. Confirm full capability and replay code coverage.

### 6. `contracts/turn-result.schema.json` (modify existing)
Purpose:
1. Bind parity decision surface to decision-record schema.

Proposed change:
1. `capabilities.decisions.items` -> reference `capability-decision-record.schema.json`.

## Proposed Clarifying Split
If desired, keep existing capability decision schema for policy evaluation, and add separate parity schema:
1. `capability-evaluation.schema.json` (policy decision logic)
2. `capability-decision-record.schema.json` (replay parity surface)

## Compatibility Risk Summary
1. Additive contracts (`stage-order`, `replay-bundle`): likely minor.
2. Tightening existing replay report: potentially breaking.
3. Changing `turn-result` decisions item reference: potentially breaking.
4. Expanding error registry: minor if additive only.

Final version classification is blocked by decisions in `open-decisions.md`.
