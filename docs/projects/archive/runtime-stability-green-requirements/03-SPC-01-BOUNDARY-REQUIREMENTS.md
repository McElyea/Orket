# SPC-01 Boundary Closeout Requirements

Last updated: 2026-03-13
Status: Archived
Owner: Orket Core
Parent lane: `docs/projects/archive/runtime-stability-green-requirements/02-IMPLEMENTATION-PLAN.md`
Closeout source: `docs/projects/archive/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`

Archive note: Historical requirements packet preserved after direct SPC-01 closeout completed on 2026-03-13.

## 1. Purpose

Define a bounded, truthful closeout target for the removed `core vs workloads boundary` item.

This packet exists because the repository has meaningful boundary enforcement already, but the stronger active requirement text still overreaches the currently evidenced implementation.

## 2. Scope

In scope:
1. closeout target for Focus Item 1 in `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
2. whether current v0 controller/workload boundary behavior is sufficient for closeout
3. whether the currently missing boundary observability artifacts remain required
4. exact proof needed for honest closeout

Out of scope:
1. implementation of controller-workload v1 bounded parallelism
2. implementation of broader child contract-style support
3. unrelated runtime hardening or observability work

## 3. Current Structural Evidence

Current shipped evidence already covers:
1. static import-boundary enforcement in `tests/platform/test_architecture_volatility_boundaries.py`
2. capability-profile and ring-policy rejection in `tests/application/test_turn_tool_dispatcher_policy_enforcement.py`
3. run-start `run_identity.json`, `capability_manifest.json`, and `run_determinism_class` emission in `orket/runtime/run_start_artifacts.py`
4. current controller/workload runtime truth in `docs/specs/CONTROLLER_WORKLOAD_V1.md`
5. current controller future-scope staging in `docs/projects/archive/controller-workload/CW03082026-Phase2D/07-V1-PLANNING-HANDOFF.md`

Current active requirement text still claims additional coverage for:
1. `capability_profile.json`
2. `workload_identity.json`
3. `runtime_violation.json`
4. a more generalized core/workload split than the currently locked controller-workload v0 contract proves

## 4. Closeout Requirements

### 4.1 Closeout Target Must Be Explicit

The direct implementation plan for SPC-01 must choose one closeout target and record it explicitly:
1. `v0 boundary closeout`
   - close only the currently enforced runtime boundary behavior
   - treat controller-workload v1 work as separate future scope
2. `full Focus Item 1 closeout`
   - implement and prove the broader artifact and boundary contract currently stated in the spec

Recommended default:
1. choose `v0 boundary closeout` unless there is an explicit request to finish the full Focus Item 1 contract now

Acceptance:
1. the chosen target is named
2. the non-chosen target is explicitly excluded
3. source docs do not imply both targets at once

### 4.2 Artifact Contract Must Be Resolved

The direct implementation plan must resolve whether the following artifacts remain part of the active closeout target:
1. `capability_profile.json`
2. `workload_identity.json`
3. `runtime_violation.json`

Required rule:
1. if an artifact remains in scope, it must have:
   1. a canonical emission path
   2. deterministic content rules
   3. an identified producer
   4. a matching proof test
2. if an artifact does not remain in scope, the active source-of-truth doc must be narrowed in the same change that closes SPC-01

Acceptance:
1. every artifact above is either:
   1. implemented and proven, or
   2. removed from the active closeout claim by source-of-truth update

### 4.3 Boundary-Violation Semantics Must Be Resolved

The closeout target must define the authoritative violation surface for boundary failures:
1. event only
2. artifact only
3. both event and artifact

The direct implementation plan must not leave `runtime_violation.json` as an implied requirement without a producer or test path.

Acceptance:
1. boundary-violation reporting semantics are explicit
2. violation reporting is matched by tests at the chosen layer

### 4.4 Controller-Workload Relationship Must Stay Truthful

SPC-01 closeout must not silently absorb staged controller-workload v1 planning into a claim of current completion.

Required rule:
1. if closeout is limited to current v0 behavior, `docs/specs/CONTROLLER_WORKLOAD_V1.md` remains the current runtime authority and staged v1 remains staged
2. if closeout includes broader boundary behavior, the implementation plan must explicitly identify the controller-workload v1 documents that are being superseded or extended

Acceptance:
1. the closeout lane and controller-workload staged lane do not conflict
2. current and future boundary claims remain distinguishable

## 5. Source-of-Truth Docs To Update On Closeout

Potentially affected docs:
1. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
2. `docs/specs/CONTROLLER_WORKLOAD_V1.md`
3. `docs/specs/RUNTIME_INVARIANTS.md`
4. `docs/ROADMAP.md`

Minimum required update set:
1. whichever active spec(s) continue to claim artifacts or behavior not currently implemented

## 6. Likely Runtime/Test Files To Change

Likely runtime paths:
1. `orket/runtime/run_start_artifacts.py`
2. `orket/runtime/execution_pipeline.py`
3. `orket/application/workflows/turn_tool_dispatcher_support.py`
4. `orket/application/workflows/turn_tool_dispatcher.py`

Likely proof paths:
1. `tests/runtime/test_run_start_artifacts.py`
2. `tests/platform/test_architecture_volatility_boundaries.py`
3. `tests/application/test_turn_tool_dispatcher_policy_enforcement.py`
4. `tests/runtime/test_controller_replay_parity.py`

## 7. Verification Requirements

Required eventual proof layers:
1. `contract`
   - artifact immutability and schema checks for any boundary artifacts that remain in scope
2. `integration`
   - policy rejection and violation recording on real dispatcher paths
3. `end-to-end`
   - only required if the chosen closeout target expands current controller-workload behavior beyond v0

Required governance proof:
1. `python scripts/governance/check_docs_project_hygiene.py`

## 8. Completion Criteria

This requirements packet is complete when:
1. the closeout target is narrowed to one explicit boundary scope
2. artifact expectations are no longer ambiguous
3. boundary-violation reporting semantics are explicit
4. exact source-of-truth docs and likely runtime files are identified
5. the direct implementation plan can begin without reopening basic scope questions

## 9. Next Artifact

After acceptance, create a direct implementation plan for SPC-01 closeout or a paired source-of-truth narrowing change if the smaller `v0 boundary closeout` target is chosen.
