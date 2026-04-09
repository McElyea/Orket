# Control-Plane Convergence Workstream 4 Closeout
Last updated: 2026-04-08
Status: Archived partial closeout artifact
Owner: Orket Core
Workstream: 4 - Checkpoint and recovery authority universalization

Closeout authority: `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`

## Objective

Record the checkpoint and recovery slices already landed under Workstream 4 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. the sandbox reclaimable path now publishes first-class checkpoint and checkpoint-acceptance records backed by immutable lifecycle snapshots with `resume_new_attempt_from_checkpoint` semantics
2. governed turn execution now publishes a durable pre-effect `resume_same_attempt` checkpoint plus checkpoint acceptance backed by an immutable checkpoint snapshot artifact before tool execution begins
3. governed turn checkpoint acceptance now carries explicit reservation and lease dependency refs, consumes the accepted immutable snapshot on safe unfinished pre-effect `resume_mode`, fails closed when snapshot identity drifts from the current run or namespace request, and still consumes older governed `resume_new_attempt_from_checkpoint` lineage truthfully when it already exists
4. the Gitea worker path now publishes a durable pre-effect `resume_forbidden` checkpoint plus acceptance from the claimed-card lease observation before worker-owned state mutation begins
5. the sandbox reclaimable path now publishes checkpoint-backed new-attempt recovery decisions after lease-expiry reconciliation, and sandbox operator views preserve the latest checkpoint and recovery summaries across attempt rollover after reacquire
6. governed turn execution now publishes checkpoint-backed same-attempt recovery decisions for unfinished pre-effect `resume_mode`, reconciliation-required recovery decisions for unsafe continuation, immediate reconciliation-rationalized terminal `terminate_run` closeout once post-effect or already-dirty truth exists, and blocked terminal recovery decisions with explicit checkpoint and effect stop basis
7. the Gitea worker path now publishes terminal `terminate_run` recovery decisions for lease-expiry, claim-transition-failure, and runtime-failure closure on claimed non-sandbox card execution

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Checkpoint` | `partial` | `partial` | Sandbox reclaimable execution now publishes durable immutable-snapshot checkpoint authority with explicit acceptance and new-attempt continuation semantics, governed turn execution now publishes durable pre-effect same-attempt checkpoint authority with reservation and lease dependency refs plus fail-closed snapshot identity checks, and the Gitea worker path now publishes a durable pre-effect `resume_forbidden` checkpoint before non-sandbox worker mutation begins. Broader supervisor-owned checkpoint creation is still not wired through every governed execution flow. |
| `RecoveryDecision` | `partial` | `partial` | Sandbox recovery authority now includes checkpoint-backed new-attempt reacquire decisions, governed turn execution now publishes same-attempt pre-effect recovery, reconciliation-required recovery, and blocked terminal `terminate_run` decisions with explicit checkpoint and effect preconditions, and the Gitea worker path now publishes terminal recovery decisions for lease-expiry, claim-transition failure, and runtime failure. Broader restart-policy and non-sandbox recovery paths still do not publish one universal recovery authority family. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 4 slices:
1. `orket/application/services/sandbox_control_plane_checkpoint_service.py`
2. `orket/application/services/gitea_state_control_plane_checkpoint_service.py`
3. `orket/application/services/sandbox_runtime_recovery_service.py`
4. `orket/application/services/sandbox_restart_policy_service.py`
5. `orket/application/services/sandbox_control_plane_execution_service.py`
6. `orket/application/services/sandbox_lifecycle_view_service.py`
7. `orket/application/services/turn_tool_control_plane_recovery.py`
8. `orket/application/services/turn_tool_control_plane_reconciliation.py`
9. `orket/application/services/turn_tool_control_plane_closeout.py`
10. `orket/application/services/turn_tool_control_plane_service.py`
11. `orket/application/services/gitea_state_control_plane_claim_failure_service.py`
12. `orket/application/services/gitea_state_control_plane_execution_service.py`
13. `orket/application/services/gitea_state_worker.py`
14. `orket/application/services/control_plane_publication_service.py`
15. `orket/application/workflows/turn_executor_control_plane.py`
16. `orket/application/workflows/turn_executor_resume_replay.py`
17. `orket/application/workflows/turn_executor_completed_replay.py`
18. `orket/application/workflows/turn_executor_control_plane_evidence.py`
19. `orket/runtime/execution_pipeline.py`
20. `orket/core/contracts/control_plane_models.py`
21. `orket/core/domain/control_plane_recovery.py`
22. `orket/adapters/storage/async_control_plane_record_repository.py`
23. `orket/application/review/snapshot_loader.py`
24. `orket/application/review/models.py`

Representative tests changed or added:
1. `tests/contracts/test_control_plane_recovery_contract.py`
2. `tests/application/test_sandbox_control_plane_checkpoint_service.py`
3. `tests/application/test_kernel_action_control_plane_pre_effect_recovery.py`
4. `tests/integration/test_sandbox_runtime_recovery_service.py`
5. `tests/application/test_turn_tool_control_plane_preflight_guards.py`
6. `tests/integration/test_turn_executor_control_plane.py`

Docs changed:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_4_CLOSEOUT.md`

## Proof executed

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py`
   Result: `42 passed`
2. `python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py`
   Result: `42 passed in 4.62s`

## Compatibility exits

Workstream 4 compatibility exits affected by the slices recorded here:
1. `CE-05` narrowed, not closed
   Reason: checkpoint publication, checkpoint acceptance, and recovery decisions are now durable on the sandbox reclaimable path, the governed turn pre-effect recovery path, and the Gitea worker claimed-card path, but snapshot or saved-state seams still survive and broader runtime recovery does not yet publish one universal supervisor-owned checkpoint and recovery family.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. `orket/application/review/snapshot_loader.py` and `orket/application/review/models.py`
   Reason: review snapshot and bundle evidence still remain useful replay inputs, but snapshot presence alone is not sufficient recovery authority on the covered governed paths.
2. sandbox- and subsystem-local recovery services outside the covered paths
   Reason: sandbox reclaimable recovery, governed turn pre-effect recovery, and Gitea worker closure now publish first-class checkpoint and recovery truth, but broader restart-policy and non-sandbox runtimes still have path-local recovery logic.

## Remaining gaps and blockers

Workstream 4 is still open.

Remaining gaps:
1. broader supervisor-owned checkpoint creation is still not execution-default across governed runtime paths
2. untouched resume paths still need explicit proof that snapshot or saved-state presence alone cannot authorize continuation
3. broader restart-policy and non-sandbox recovery behavior still does not publish one universal recovery authority family
4. `CE-05` remains open
5. the representative `Slice 4A` proof set was re-verified on `2026-04-08`, so that slice no longer belongs at the front of the open convergence queue even though `CE-05` remains open

## Authority-story updates landed with these slices

The following authority docs were updated in this closeout-recording slice:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_4_CLOSEOUT.md`

## Verdict

Workstream 4 now has a truthful partial closeout artifact for the checkpoint and recovery slices already landed on the sandbox reclaimable path, the governed turn pre-effect recovery path, and the Gitea worker claimed-card path, but the workstream remains open until supervisor-owned checkpoint and recovery authority is universal across the broader governed runtime. The representative `Slice 4A` proof set was re-verified on `2026-04-08`, so the next truthful Workstream 4 work now continues through follow-on `Slice 4B`.
