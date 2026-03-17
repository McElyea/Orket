# Truthful Runtime Memory Trust Contract

Last updated: 2026-03-17
Status: Active
Owner: Orket Core
Phase closeout authority: `docs/projects/archive/truthful-runtime/TRH03172026-PHASE-D-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`
2. `docs/specs/RUNTIME_INVARIANTS.md`

## Purpose

Define the durable Phase D contract for memory mutation, conflict handling, and governed trust labeling before memory-derived context is synthesized into prompts.

## Scope

This contract currently covers:
1. memory-class mapping for `session_memory`, `profile_memory`, `episodic_memory`, and legacy `project_memory`
2. required write-policy metadata for runtime-owned memory mutations
3. deterministic conflict resolution for durable profile-memory updates
4. trust-level labeling before governed memory context is synthesized

Out of scope:
1. user-facing `saved` / `used memory` claim language and receipt enforcement
2. non-memory tool families outside the bounded governed-memory synthesis path
3. Phase E promotion, scorecard, and expectation-alignment work

## Canonical Metadata Surface

Stored memory rows participating in this contract must carry these additive metadata keys:
1. `memory_policy_version`
2. `memory_class`
3. `write_threshold`
4. `write_rationale`
5. `trust_level`
6. `conflict_resolution`

These keys are additive. Existing readers may ignore them, but governed synthesis and verification must use them.

## Memory Classes

Stable memory classes:
1. `working_memory`
2. `durable_memory`
3. `reference_context`

Scope mapping:
1. `session_memory -> working_memory`
2. `profile_memory -> durable_memory`
3. `episodic_memory -> reference_context`
4. `project_memory -> reference_context`

Class rules:
1. `working_memory` is turn-bounded session context and does not become durable user truth by itself.
2. `durable_memory` is the only phase-scoped profile-memory authority for cross-session settings and confirmed facts.
3. `reference_context` may inform synthesis but is not durable user truth unless separately promoted through a durable-memory write path.

## Write Threshold Contract

Stable threshold values:
1. `session_turn_capture`
2. `explicit_preference_persist`
3. `confirmed_user_fact`
4. `profile_setting_persist`
5. `reference_context_capture`

Threshold rules:
1. every runtime-owned write must persist a non-empty `write_rationale`
2. session chat inputs default to authoritative `working_memory`; session chat outputs default to advisory `working_memory`
3. `user_fact.*` durable writes require the pre-existing confirmation rule plus the Phase D conflict rules below
4. `project_memory` remains reference-context only and must not silently masquerade as durable user truth

## Conflict Resolution Contract

Stable `conflict_resolution` values:
1. `none`
2. `no_change`
3. `setting_update`
4. `user_correction`
5. `stale_update_rejected`
6. `contradiction_requires_correction`

Conflict rules:
1. a durable write whose value matches the stored value emits `no_change`
2. a durable write with an older observation timestamp than the stored record fails closed with `stale_update_rejected`
3. a contradictory `user_fact.*` write fails closed with `contradiction_requires_correction` unless `metadata.user_correction = true`
4. a contradictory `user_fact.*` write with `metadata.user_correction = true` applies with `user_correction`
5. non-fact durable settings may update without correction only when they are not stale

Timestamp precedence for staleness checks:
1. `observed_at`
2. `source_timestamp`
3. `recorded_at`
4. `timestamp`

## Trust-Level Contract

Stable `trust_level` values:
1. `authoritative`
2. `advisory`
3. `stale_risk`
4. `unverified`

Classification rules:
1. durable memory defaults to `authoritative`
2. working-memory user inputs default to `authoritative`
3. working-memory assistant outputs default to `advisory`
4. reference-context rows default to `advisory` unless they are explicitly stale or unverified
5. explicit `stale_at`, `expires_at`, or `trust_level = stale_risk` marks a row as `stale_risk`

## Governed Synthesis Rule

Governed memory synthesis must:
1. include only `authoritative` and `advisory` rows
2. exclude `stale_risk` and `unverified` rows
3. label included rows with an explicit trust marker before they reach the prompt surface

Current canonical rendering examples:
1. `- [profile][trust=authoritative] companion_setting.role_id: strategist`
2. `- [reference_context][trust=advisory] Decision by architect on ARC-1: ...`

## Live Evidence Authority

1. Live suite: `tests/live/test_truthful_runtime_phase_d_completion_live.py`
2. Contract coverage: `tests/runtime/test_truthful_memory_policy.py`
3. Integration coverage:
   `tests/runtime/test_sdk_memory_provider.py`,
   `tests/application/test_companion_runtime_service.py`,
   `tests/integration/test_memory_rag.py`
