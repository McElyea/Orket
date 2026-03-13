# SPC-06 Core Tool Baseline Closeout Implementation Plan

Last updated: 2026-03-13
Status: Active
Owner: Orket Core
Parent lane: `docs/projects/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`
Source requirements: `docs/projects/runtime-stability-green-requirements/05-SPC-06-CORE-TOOL-BASELINE-REQUIREMENTS.md`

## 1. Decision Lock

Chosen closeout target: `minimal baseline closeout` using the current small core-tool set and the current registry contract as canonical.
Explicitly excluded target(s): expanded OpenClaw-class baseline closeout and richer per-tool registry metadata as required closeout scope in this lane.

## 2. Objective

Close SPC-06 by aligning active baseline-tool requirements to the currently enforced minimal baseline and by proving the current registry and capability-profile contract rather than silently broadening it.

## 3. In Scope

1. Narrow active spec text so the closeout target matches the current core-tool baseline and current registry fields.
2. Credit capability-profile enforcement accurately as part of the closed scope.
3. Prove fail-closed bootstrap validation and dispatcher/artifact behavior for the current metadata contract.

## 4. Explicitly Out Of Scope

1. Promoting additional compatibility tools into the core baseline for this closeout.
2. Making `input_schema`, `output_schema`, `error_schema`, `side_effect_class`, timeout policy, or retry policy mandatory registry fields for this lane.
3. Treating OpenClaw-class workflow breadth as part of the closed core baseline claim.

## 5. Planned Changes

### 5.1 Source-Of-Truth Narrowing

1. Update `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` so the closeout claim matches the current minimal baseline and current registry fields.
2. Update `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md` so richer per-tool metadata is no longer claimed as part of this closeout target.
3. Update `docs/specs/TOOL_CONTRACT_TEMPLATE.md` or `docs/specs/RUNTIME_INVARIANTS.md` only if they currently imply that the richer metadata is already canonical.

### 5.2 Proof Hardening

1. Keep `tests/runtime/test_contract_bootstrap.py` as the primary `contract` proof for fail-closed registry loading.
2. Tighten `tests/application/test_turn_tool_dispatcher_policy_enforcement.py` as `integration` proof for capability-profile and ring-policy enforcement.
3. Tighten `tests/application/test_turn_artifact_writer.py` as `integration` proof if emitted invocation or artifact surfaces need wording or field-alignment checks.
4. Keep the checked-in compatibility reports as structural evidence only; do not treat them as the sole proof for closeout.

### 5.3 Runtime Code Changes

1. Prefer zero registry-schema expansion.
2. Only modify `orket/runtime/contract_bootstrap.py`, `core/tools/tool_registry.yaml`, `orket/application/workflows/tool_invocation_contracts.py`, or `orket/application/workflows/turn_artifact_writer.py` if the narrowed claim exposes a real mismatch in currently shipped metadata handling.

## 6. Verification Plan

1. `contract`: `tests/runtime/test_contract_bootstrap.py`
2. `integration`: `tests/application/test_turn_tool_dispatcher_policy_enforcement.py`
3. `integration`: `tests/application/test_turn_artifact_writer.py` if artifact expectations change
4. Governance: `python scripts/governance/check_docs_project_hygiene.py`

## 7. Exit Criteria

1. Active specs no longer overclaim expanded baseline breadth or richer registry metadata for SPC-06.
2. The minimal core-tool baseline is the only active closeout target.
3. The chosen proof files pass against the narrowed contract.
