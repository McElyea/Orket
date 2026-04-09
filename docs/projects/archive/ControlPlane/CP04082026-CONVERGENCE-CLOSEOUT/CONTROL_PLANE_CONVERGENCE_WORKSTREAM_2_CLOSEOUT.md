# Control-Plane Convergence Workstream 2 Closeout
Last updated: 2026-04-08
Status: Archived partial closeout artifact
Owner: Orket Core
Workstream: 2 - Reservation, lease, and resource universalization

Closeout authority: `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`

## Objective

Record the reservation/lease/resource slices already landed under Workstream 2 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. first-class `ResourceRecord` publication and durable-store persistence now exist through the shared control-plane authority, publication, and repository seams
2. the default sandbox lifecycle now publishes shared resource truth on create, create-accepted, active health verification, renew, reacquire, reconciliation, terminal, and cleaned paths instead of keeping sandbox resource state purely subsystem-local
3. sandbox operator views now project the latest durable resource id, kind, current state, and orphan classification
4. same-second sandbox resource publication now resolves by last durable publish order rather than by lexicographic state-string drift
5. the sandbox `handle_healthy` activation path now mirrors active lease publication instead of leaving that path quieter than `mark_deployment_verified`
6. the standalone coordinator API now publishes shared resource truth for claim, renew, expiry-before-reclaim, open-cards expiry observation, release, and fail-closed promotion rollback transitions instead of keeping non-sandbox coordinator ownership purely lease-local
7. the Gitea state-worker path now publishes shared resource truth for claim, renew, expiry, release, claim-failure uncertainty, and promotion rollback instead of keeping non-sandbox worker ownership purely lease-local
8. the governed kernel-action execution path now publishes shared resource truth for execution-lease activation, terminal release, and fail-closed promotion rollback
9. the governed turn-tool namespace path now publishes shared resource truth for namespace-lease activation, terminal release, and fail-closed promotion rollback
10. the orchestrator scheduler-owned namespace mutation path now publishes shared resource truth for namespace activation, terminal release, and fail-closed promotion rollback
11. the orchestrator issue-dispatch slot path now publishes shared resource truth for dispatch-slot activation, terminal release, and fail-closed begin-dispatch rollback
12. the sandbox create-record failure path now publishes a shared resource closeout when a just-published lease must be released before durable lifecycle authority exists, instead of leaving that rollback lease-only
13. the standalone coordinator API now projects the latest shared resource summary on list, claim, renew, complete, and fail responses instead of leaving its read surface lease-centric after durable resource publication
14. governed kernel replay and audit views now project the latest shared resource summary instead of exposing only reservation and lease ownership detail on that read surface
15. approval list and detail target views now project the latest shared resource summary for supported governed target runs instead of exposing only run, step, checkpoint, effect, operator, reservation, and final-truth detail there
16. orchestrator issue-dispatch closeout and reused-run guards now fail closed when the latest shared resource snapshot disagrees with the dispatch lease instead of treating reservation-plus-lease history as sufficient authority
17. orchestrator scheduler reused-run guards now fail closed when the latest shared resource snapshot disagrees with the namespace lease instead of treating reservation-plus-lease history as sufficient authority
18. governed turn-tool existing-run execution and completed-reuse guards now fail closed when the latest shared namespace resource snapshot disagrees with the lease instead of relying only on run state and lease history
19. governed kernel-action existing-run consistency now fails closed when the latest shared execution-scope resource snapshot disagrees with the lease instead of trusting lease-only history when durable execution authority already exists
20. Gitea state-worker terminal expiry and release helpers now republish terminal lease/resource truth when the latest shared resource snapshot drifted away from the already-terminal lease instead of silently trusting lease-only terminal history
21. authenticated kernel admit/commit/session-end responses now surface `control_plane_resource_id` when durable kernel resource truth exists instead of dropping that resource ref on the API read surface
22. async orchestration-engine kernel admit now publishes the governed approval-hold reservation through an application-owned seam before response shaping, and async engine admit/commit/end-session responses now reuse the shared kernel control-plane view projection instead of leaving that response contract router-local
23. approval-resolution operator actions for supported governed turn-tool and kernel-action targets now include the canonical shared target `resource_id` in `affected_resource_refs` when durable execution truth exists instead of exposing only session or issue refs on the approval surface and only run refs on the target-side action
24. governed kernel session-end cancel and attestation operator actions now include the canonical execution-scope `resource_id` in durable `affected_resource_refs`, and governed kernel replay/audit views now surface operator-action affected transition/resource refs instead of truncating that latest operator summary to receipt-only evidence
25. authenticated sandbox cancel operator actions now include the canonical shared sandbox `resource_id` in durable `affected_resource_refs`, and sandbox operator views now surface operator-action affected transition/resource refs instead of truncating that latest operator summary to receipt-only evidence
26. governed turn-tool protocol receipt invocation manifests now carry the canonical governed run, attempt, reservation, lease, and namespace-resource ids when durable turn-tool authority exists instead of stopping at namespace scope alone on that durable invocation-evidence surface
27. approval target views plus approval-resolution operator-action summaries now map default orchestrator issue-dispatch runs and scheduler-owned namespace mutation/child-workload runs onto their canonical shared resource ids instead of limiting that resource projection to governed turn-tool and kernel-action targets
28. the standalone coordinator API now fails closed when renew, expiry, or release would continue while the latest shared coordinator resource snapshot no longer agrees with active lease authority, and now checks stale-expiry plus active lease/resource authority before open-cards listing and before claim/renew/complete/fail store mutation so detected drift cannot silently mutate coordinator ownership first
29. the Gitea worker renew loop now fails closed before backend renew when the latest shared active resource snapshot no longer agrees with the active lease authority, and now blocks and releases the run with explicit resource-drift recovery authority instead of silently extending lease-backed ownership after drift

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Reservation` | `partial` | `partial` | No universal admission closure landed in this slice, but the main governed non-sandbox reservation paths now sit beside shared resource publication instead of promoting into lease-only ownership stories, and governed kernel approval-hold reservation publication on the async engine admit path is now application-owned instead of interface-local. |
| `Lease` | `partial` | `partial` | Shared lease truth now mirrors shared resource truth across sandbox, coordinator, Gitea, kernel-action, turn-tool, scheduler-owned namespace mutation, and issue-dispatch activation or closeout paths. Lease truth still is not universal across every governed runtime path. |
| `Resource` | `partial` | `partial` | A real shared `ResourceRecord` seam now exists across sandbox and the main governed non-sandbox ownership paths, including previously leaky coordinator promotion rollback and sandbox pre-lifecycle create-failure rollback, the coordinator, governed kernel replay or audit, approval target read surfaces, supported approval-resolution operator-action surfaces, governed kernel session-end operator-action surfaces, authenticated sandbox cancel operator-action surfaces, and governed turn-tool protocol receipt invocation manifests now project or reference that durable resource truth directly where supported. Approval target views and approval-resolution operator-action summaries now also map default orchestrator issue-dispatch runs plus scheduler-owned namespace mutation/child-workload runs onto their canonical shared resource ids, not just governed turn-tool and kernel-action targets. Orchestrator issue-dispatch, scheduler, governed turn-tool, governed kernel existing-run or closeout guards, standalone coordinator renew/expiry/release authority, and Gitea worker active renew now fail closed when resource truth drifts from lease truth, with the coordinator open-cards observation plus claim/renew/complete/fail endpoints now preflighting that authority before store mutation. Gitea worker terminal expiry/release helpers now realign terminal resource truth instead of skipping on lease-only terminal history, and async engine kernel admit/commit/end-session responses now reuse that same shared projection contract instead of leaving full resource refs on the router-only path. Remaining gaps are universal read-side adoption beyond those slices and any still-uncovered authority paths, not the major rollback paths already covered here. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 2 slices:
1. `orket/core/contracts/repositories.py`
2. `orket/application/services/control_plane_authority_service.py`
3. `orket/application/services/control_plane_publication_service.py`
4. `orket/adapters/storage/async_control_plane_record_repository.py`
5. `orket/application/services/sandbox_control_plane_resource_service.py`
6. `orket/application/services/sandbox_runtime_lifecycle_service.py`
7. `orket/application/services/sandbox_terminal_outcome_service.py`
8. `orket/application/services/sandbox_runtime_cleanup_service.py`
9. `orket/application/services/sandbox_lifecycle_reconciliation_service.py`
10. `orket/application/services/sandbox_lifecycle_view_service.py`
11. `orket/application/services/coordinator_control_plane_lease_service.py`
12. `orket/application/services/coordinator_control_plane_reservation_service.py`
13. `orket/application/services/gitea_state_control_plane_lease_service.py`
14. `orket/application/services/gitea_state_control_plane_reservation_service.py`
15. `orket/application/services/gitea_state_worker.py`
16. `orket/application/services/kernel_action_control_plane_resource_lifecycle.py`
17. `orket/application/services/kernel_action_control_plane_service.py`
18. `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`
19. `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`
20. `orket/application/services/orchestrator_issue_control_plane_service.py`
21. `orket/services/sandbox_orchestrator.py`
22. `orket/interfaces/coordinator_api.py`
23. `orket/application/services/kernel_action_control_plane_view_service.py`
24. `orket/orchestration/approval_control_plane_read_model.py`
25. `orket/orchestration/engine_approvals.py`
26. `orket/application/services/control_plane_resource_authority_checks.py`
27. `orket/application/services/turn_tool_control_plane_state_gate.py`
28. `orket/interfaces/routers/kernel.py`
29. `orket/orchestration/engine.py`
30. `orket/application/services/kernel_action_pending_approval_reservation.py`
31. `orket/application/services/control_plane_target_resource_refs.py`
32. `orket/application/services/kernel_action_control_plane_operator_service.py`
33. `orket/application/services/sandbox_control_plane_operator_service.py`
34. `orket/application/services/sandbox_lifecycle_view_service.py`
35. `orket/application/workflows/tool_invocation_contracts.py`
36. `orket/application/workflows/turn_tool_dispatcher_protocol.py`

Representative tests changed or added:
1. `tests/application/test_control_plane_publication_service.py`
2. `tests/application/test_sandbox_control_plane_resource_service.py`
3. `tests/application/test_sandbox_control_plane_lease_service.py`
4. `tests/application/test_sandbox_control_plane_reservation_service.py`
5. `tests/application/test_sandbox_control_plane_reconciliation_service.py`
6. `tests/application/test_sandbox_control_plane_closure_service.py`
7. `tests/integration/test_async_control_plane_record_repository.py`
8. `tests/integration/test_sandbox_orchestrator_lifecycle.py`
9. `tests/integration/test_sandbox_lifecycle_reconciliation_service.py`
10. `tests/interfaces/test_coordinator_api_control_plane.py`
11. `tests/integration/test_gitea_state_worker_control_plane.py`
12. `tests/application/test_kernel_action_control_plane_resource_lifecycle.py`
13. `tests/application/test_kernel_action_control_plane_service.py`
14. `tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
15. `tests/application/test_turn_tool_control_plane_preflight_guards.py`
16. `tests/integration/test_turn_executor_control_plane.py`
17. `tests/integration/test_turn_tool_control_plane_closeout.py`
18. `tests/application/test_orchestrator_scheduler_control_plane_mutation_guards.py`
19. `tests/application/test_orchestrator_scheduler_control_plane_service.py`
20. `tests/integration/test_orchestrator_scheduler_control_plane.py`
21. `tests/application/test_orchestrator_issue_control_plane_service.py`
22. `tests/integration/test_orchestrator_issue_control_plane.py`
23. `tests/interfaces/test_api_kernel_lifecycle.py`
24. `tests/application/test_orchestration_engine_kernel_async.py`
25. `tests/application/test_tool_approval_control_plane_operator_service.py`
26. `tests/interfaces/test_api_nervous_system_operator_surfaces.py`
27. `tests/application/test_kernel_action_control_plane_operator_service.py`
28. `tests/application/test_kernel_action_control_plane_view_service.py`
29. `tests/interfaces/test_api_kernel_lifecycle.py`
30. `tests/application/test_sandbox_control_plane_operator_service.py`
31. `tests/integration/test_sandbox_orchestrator_lifecycle.py`
32. `tests/application/test_turn_artifact_writer.py`
33. `tests/application/test_async_protocol_run_ledger.py`
34. `tests/runtime/test_protocol_receipt_materializer.py`
35. `tests/application/test_control_plane_target_resource_refs.py`
36. `tests/interfaces/test_coordinator_api_control_plane.py`
37. `tests/integration/test_gitea_state_worker_control_plane.py`

Docs changed:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_2_CLOSEOUT.md`
3. `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
4. `CURRENT_AUTHORITY.md`

## Proof executed

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_publication_service.py tests/application/test_sandbox_control_plane_resource_service.py tests/application/test_sandbox_control_plane_lease_service.py tests/application/test_sandbox_control_plane_reservation_service.py tests/application/test_sandbox_control_plane_reconciliation_service.py tests/application/test_sandbox_control_plane_closure_service.py tests/integration/test_async_control_plane_record_repository.py tests/integration/test_sandbox_orchestrator_lifecycle.py tests/integration/test_sandbox_lifecycle_reconciliation_service.py`
   Result: `42 passed`
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/application/test_control_plane_publication_service.py`
   Result: `17 passed`
3. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py`
   Result: `8 passed`
4. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_kernel_action_control_plane_resource_lifecycle.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
   Result: `10 passed`
5. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_turn_tool_control_plane_closeout.py`
   Result: `21 passed`
6. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_orchestrator_scheduler_control_plane_service.py tests/application/test_orchestrator_scheduler_control_plane_mutation_guards.py tests/integration/test_orchestrator_scheduler_control_plane.py`
   Result: `11 passed`
7. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_orchestrator_issue_control_plane_service.py tests/integration/test_orchestrator_issue_control_plane.py`
   Result: `12 passed`
8. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
9. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/application/test_sandbox_control_plane_resource_service.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
   Result: `16 passed`
10. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py`
   Result: `5 passed`
11. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
   Result: `4 passed`
12. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_engine_approvals.py tests/interfaces/test_api_approvals.py`
   Result: `14 passed`
13. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_orchestrator_issue_control_plane_service.py tests/application/test_orchestrator_scheduler_control_plane_service.py`
   Result: `19 passed`
14. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/integration/test_orchestrator_issue_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py`
   Result: `4 passed`
15. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py`
   Result: `6 passed`
16. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/integration/test_turn_executor_control_plane.py`
   Result: `10 passed`
17. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_kernel_action_control_plane_service.py`
   Result: `7 passed`
18. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
   Result: `4 passed`
19. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/interfaces/test_api_kernel_lifecycle.py -k "control_plane_resource_id or control_plane_governed_action_truth or observed_policy_reject or pre_effect_policy_reject"`
   Result: `3 passed, 24 deselected`
20. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_orchestration_engine_kernel_async.py tests/interfaces/test_api_kernel_lifecycle.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
   Result: `30 passed`
21. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_tool_approval_control_plane_operator_service.py tests/application/test_engine_approvals.py tests/interfaces/test_api_approvals.py tests/interfaces/test_api_nervous_system_operator_surfaces.py`
   Result: `19 passed`
22. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_kernel_action_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_view_service.py tests/interfaces/test_api_kernel_lifecycle.py`
   Result: `29 passed`
23. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_sandbox_control_plane_operator_service.py tests/integration/test_sandbox_orchestrator_lifecycle.py -k "operator or delete_sandbox"`
   Result: `5 passed, 4 deselected`
24. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_turn_artifact_writer.py tests/application/test_async_protocol_run_ledger.py tests/runtime/test_protocol_receipt_materializer.py tests/integration/test_turn_executor_control_plane.py`
   Result: `41 passed`
25. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_target_resource_refs.py tests/application/test_tool_approval_control_plane_operator_service.py tests/application/test_engine_approvals.py tests/interfaces/test_api_approvals.py`
   Result: `21 passed`
26. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py`
   Result: `9 passed`
27. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py`
   Result: `9 passed`
28. `python -m pytest -q tests/contracts/test_control_plane_reservation_contract.py tests/contracts/test_control_plane_lease_contract.py tests/interfaces/test_coordinator_api_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py`
   Result: `41 passed in 3.42s`

## Compatibility exits

Workstream 2 compatibility exits affected by the slices recorded here:
1. `CE-03` narrowed, not closed
   Reason: the shared `ResourceRecord` seam now exists across sandbox, coordinator, Gitea, kernel-action, turn-tool, scheduler-owned namespace mutation, and issue-dispatch ownership paths, Gitea worker active renew now stops before extending backend ownership on resource drift, and Gitea worker terminal closeout now also heals resource drift instead of trusting lease-only terminal history, but broader read models and any still-uncovered authority paths do not yet consume one universal resource registry family.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. sandbox-specialized lifecycle inventory and inspection under `orket/application/services/sandbox_runtime_*`
   Reason: sandbox remains the strongest current resource family, and the new shared `ResourceRecord` seam currently projects that family rather than replacing every subsystem-local observation path.
2. lease-centric ownership summaries outside sandbox views
   Reason: the coordinator API, governed kernel replay or audit views, approval target views for supported governed runs now including orchestrator issue-dispatch plus scheduler-owned namespace mutation/child-workload runs, approval-resolution operator actions for those supported governed targets, governed kernel session-end operator-action summaries, authenticated sandbox cancel operator-action summaries, and governed turn-tool protocol receipt invocation manifests now project or reference shared resource truth directly, orchestrator issue-dispatch, scheduler, governed turn-tool, governed kernel existing-run guards, standalone coordinator renew/expiry/release plus open-cards observation authority, and Gitea worker active renew now also consume that resource truth as part of validation, while Gitea worker terminal closeout realigns resource truth when drift is detected, but most other non-sandbox views still expose ownership primarily through reservation or lease summaries rather than a shared resource-registry projection.

## Remaining gaps

Workstream 2 is still open.

The main remaining gaps are:
1. non-sandbox governed publication now covers the main authority paths, but broader read surfaces still do not project one shared resource registry family
2. reservation publication is still not universal across every admission and scheduling path
3. lease publication is still not universal across every governed ownership and mutation path
4. broader orphan, stale, invalidation, and cleanup handling is still reconstructable mainly through lease history plus subsystem-local state outside the newly-covered resource publication paths
5. the recorded Workstream 2 `Slice 2A` proof set was re-verified on `2026-04-08`, so that slice no longer belongs at the front of the open convergence queue even though `CE-03` remains open

## Authority-story updates landed with these slices

The following authority docs were updated in the same slices recorded here:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_2_CLOSEOUT.md`
3. `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
4. `CURRENT_AUTHORITY.md`

## Verdict

Workstream 2 has a truthful partial closeout artifact for the recorded shared resource-registry and ownership-convergence slices, but it is still open.

The recorded Workstream 2 `Slice 2A` proof set was re-verified on `2026-04-08` and remains truthful, so it no longer belongs at the front of the open convergence queue. `CE-03` remains open because broader read-side adoption and still-uncovered ownership paths remain outside the recorded closeout claim, so the active follow-on queue now continues through `Slice 2B`.
