# Control-Plane Convergence Workstream 6 Closeout
Last updated: 2026-04-08
Status: Archived partial closeout artifact
Owner: Orket Core
Workstream: 6 - Final-truth closure unification

Closeout authority: `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`

## Objective

Record the final-truth slices already landed under Workstream 6 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. a first-class control-plane `FinalTruthRecord` family now exists in core and application authority instead of leaving all terminal closure on legacy summary surfaces
2. sandbox workflow, policy, lifecycle terminal-outcome, and `lost_runtime` reconciliation paths now publish durable final truth on the main sandbox runtime path
3. the governed kernel-action API path now publishes terminal closure for admit, commit, and session-end traces
4. governed turn tooling now publishes terminal closure across protocol and non-protocol turns, including immediate reconciliation-closed termination when unsafe `resume_mode` encounters post-effect or effect-boundary-uncertain truth
5. the Gitea worker path now publishes terminal closure for lease-backed non-sandbox card execution, including blocked pre-effect claim-transition failure
6. sandbox operator views and governed kernel replay or audit views now surface richer final-truth classifications, authoritative result refs, and authority sources when durable closure truth exists

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `FinalTruthRecord` | `partial` | `partial` | Durable final-truth publication now exists on the main sandbox runtime path, the governed kernel action API path, the governed turn-tool execution path, and the lease-backed Gitea worker path, with sandbox and governed-kernel views now surfacing richer final-truth classifications and authority sources. Other runtime closure paths plus legacy summary-backed closure surfaces still survive, so the row remains `partial`. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 6 slices:
1. `orket/core/contracts/control_plane_models.py`
2. `orket/core/domain/control_plane_final_truth.py`
3. `orket/application/services/control_plane_publication_service.py`
4. `orket/application/services/sandbox_control_plane_closure_service.py`
5. `orket/application/services/sandbox_terminal_outcome_service.py`
6. `orket/application/services/sandbox_control_plane_reconciliation_service.py`
7. `orket/application/services/sandbox_lifecycle_reconciliation_service.py`
8. `orket/application/services/sandbox_lifecycle_view_service.py`
9. `orket/application/services/kernel_action_control_plane_service.py`
10. `orket/application/services/kernel_action_control_plane_view_service.py`
11. `orket/application/services/turn_tool_control_plane_service.py`
12. `orket/application/services/gitea_state_control_plane_claim_failure_service.py`
13. `orket/application/services/gitea_state_control_plane_execution_service.py`
14. `orket/application/services/gitea_state_worker.py`
15. `orket/runtime/execution_pipeline.py`
16. `orket/application/workflows/turn_tool_dispatcher.py`
17. `orket/orchestration/engine.py`
18. `orket/application/workflows/orchestrator_ops.py`
19. `orket/interfaces/routers/kernel.py`
20. `orket/services/sandbox_orchestrator.py`
21. `orket/adapters/storage/async_control_plane_record_repository.py`
22. `orket/runtime/run_summary.py`
23. `orket/runtime/runtime_truth_contracts.py`
24. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`

Representative tests changed or added:
1. `tests/contracts/test_control_plane_final_truth_contract.py`
2. `tests/integration/test_sandbox_terminal_outcome_service.py`
3. `tests/integration/test_turn_tool_control_plane_closeout.py`
4. `tests/integration/test_gitea_state_worker_control_plane.py`

Docs changed:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_6_CLOSEOUT.md`

## Proof executed

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_gitea_state_worker_control_plane.py`
   Result: `25 passed`
2. `python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_packet1.py tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_gitea_state_worker_control_plane.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
   Result: `54 passed in 6.92s`

## Compatibility exits

Workstream 6 compatibility exits affected by the slices recorded here:
1. `CE-07` narrowed, not closed
   Reason: governed terminal paths on the sandbox, governed kernel, governed turn-tool, and Gitea worker flows now publish first-class final truth, but legacy closure surfaces under `run_summary.py`, `runtime_truth_contracts.py`, and packet-1 style truth contracts still survive as compatibility and projection surfaces.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. `orket/runtime/run_summary.py`
   Reason: legacy summary output still survives as a compatibility projection surface and is not yet fully retired lane-wide.
2. `orket/runtime/runtime_truth_contracts.py` and `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
   Reason: legacy truth contracts still survive for compatibility and documentation continuity while broader closure paths continue migrating onto `FinalTruthRecord`.

## Remaining gaps and blockers

Workstream 6 is still open.

Remaining gaps:
1. other governed terminal paths still need to fail closed without published final truth
2. older summary-backed closure surfaces still need to be explicitly projection-only everywhere they survive
3. closure input wiring from effect, operator, and reconciliation authority is still not universal on all terminal paths
4. `CE-07` remains open
5. the representative `Slice 6A` proof set was re-verified on `2026-04-08`, so that slice no longer belongs at the front of the open convergence queue even though `CE-07` remains open

## Authority-story updates landed with these slices

The following authority docs were updated in this closeout-recording slice:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_6_CLOSEOUT.md`

## Verdict

Workstream 6 now has a truthful partial closeout artifact for the first-class final-truth publication already landed on the main sandbox, governed kernel, governed turn-tool, and Gitea worker terminal paths, but the workstream remains open until terminal closure is universally gated on `FinalTruthRecord` and legacy summary-backed closure surfaces stop acting like alternate authorities. The representative `Slice 6A` proof set was re-verified on `2026-04-08`, so the next truthful Workstream 6 work now continues through follow-on `Slice 6B`.
