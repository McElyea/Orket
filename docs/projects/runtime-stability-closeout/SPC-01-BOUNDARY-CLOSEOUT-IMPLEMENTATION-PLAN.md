# SPC-01 Boundary Closeout Implementation Plan

Last updated: 2026-03-13
Status: Active
Owner: Orket Core
Parent lane: `docs/projects/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`
Source requirements: `docs/projects/runtime-stability-green-requirements/03-SPC-01-BOUNDARY-REQUIREMENTS.md`

## 1. Decision Lock

Chosen closeout target: `v0 boundary closeout`.
Explicitly excluded target(s): `full Focus Item 1 closeout`, controller-workload v1 expansion, and new boundary artifacts not already required by the current v0 runtime contract.

## 2. Objective

Close SPC-01 by aligning active runtime-stability requirements to the currently enforced v0 controller/workload boundary and by adding only the proof needed to make that narrower claim truthful.

## 3. In Scope

1. Narrow the active requirement text in `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` to the shipped v0 boundary claim.
2. Keep `docs/specs/CONTROLLER_WORKLOAD_V1.md` as the authority for current controller/workload runtime behavior.
3. Prove the canonical v0 artifact and rejection surfaces already enforced by current runtime paths.

## 4. Explicitly Out Of Scope

1. Implementing `capability_profile.json` as a separate closeout artifact.
2. Implementing `workload_identity.json`.
3. Implementing `runtime_violation.json`.
4. Expanding the controller/workload contract toward the staged v1 planning handoff.

## 5. Planned Changes

### 5.1 Source-Of-Truth Narrowing

1. Update `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` Focus Item 1 so the closeout claim names only the current v0 boundary contract.
2. Remove or narrow any active requirement text that still implies:
   1. `capability_profile.json`
   2. `workload_identity.json`
   3. `runtime_violation.json`
3. Make boundary-violation semantics explicit: for `v0 boundary closeout`, violations are event only, and `runtime_violation.json` is not part of the active closeout contract.
4. Keep the current `docs/specs/CONTROLLER_WORKLOAD_V1.md` wording aligned if any terminology drift remains after the requirement narrowing.

### 5.2 Proof Hardening

1. Keep `tests/platform/test_architecture_volatility_boundaries.py` as the static `contract` boundary guard.
2. Tighten `tests/runtime/test_run_start_artifacts.py` as the `contract` proof for the authoritative v0 artifact set emitted at run start.
3. Tighten `tests/application/test_turn_tool_dispatcher_policy_enforcement.py` as the `integration` proof for fail-closed capability-profile and ring-policy rejection.
4. Re-run `tests/runtime/test_controller_replay_parity.py` as `integration` proof only if the narrowed boundary claim changes replay-visible artifact expectations.

### 5.3 Runtime Code Changes

1. Prefer zero runtime behavior changes.
2. Only modify runtime paths such as `orket/runtime/run_start_artifacts.py` or `orket/application/workflows/turn_tool_dispatcher_support.py` if a currently shipped v0 behavior is under-tested or mismatched with the narrowed claim.

## 6. Verification Plan

1. `contract`: `tests/platform/test_architecture_volatility_boundaries.py`
2. `contract`: `tests/runtime/test_run_start_artifacts.py`
3. `integration`: `tests/application/test_turn_tool_dispatcher_policy_enforcement.py`
4. `integration`: `tests/runtime/test_controller_replay_parity.py` if artifact expectations change
5. Governance: `python scripts/governance/check_docs_project_hygiene.py`

## 7. Exit Criteria

1. Active requirement text no longer overclaims missing boundary artifacts.
2. Current v0 controller/workload behavior is the only closeout claim left active for SPC-01.
3. Boundary-violation semantics are explicit and event only for the v0 closeout contract.
4. The chosen proof files pass against the narrowed closeout claim.
