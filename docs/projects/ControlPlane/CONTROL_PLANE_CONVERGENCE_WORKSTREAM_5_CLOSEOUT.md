# Control-Plane Convergence Workstream 5 Closeout
Last updated: 2026-03-28
Status: Partial closeout artifact
Owner: Orket Core
Workstream: 5 - Reconciliation and operator-action convergence

## Objective

Record the reconciliation and operator-action slices already landed under Workstream 5 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. the sandbox `lost_runtime` closure case now publishes first-class reconciliation authority instead of leaving divergence handling subsystem-local
2. governed turn execution now publishes reconciliation authority for unsafe `resume_mode` closeout, including durable orphan operation-artifact detection before prompt or model work continues
3. the Gitea worker claim-transition failure path now publishes first-class reconciliation authority on the non-sandbox state-backend path
4. the authenticated sandbox stop path now publishes a first-class operator cancel command and preserves the canonical shared sandbox `resource_id` in durable `affected_resource_refs`
5. authenticated session halt and authenticated interaction cancel now publish durable session-scoped or turn-scoped `cancel_run` operator commands instead of remaining endpoint-local behavior only
6. authenticated approval resolutions now publish durable operator risk acceptance for supported grants plus terminal operator commands for denials and expirations, and governed target-side operator actions now carry canonical shared target resource ids when durable execution truth exists
7. supported guard-review pending-gate approvals now publish durable `approve_continue` commands on the pending-gate target
8. authenticated kernel session-end now publishes durable operator cancel commands for governed action runs plus optional bounded `operator_attestation`, both carrying canonical execution-scope resource ids in `affected_resource_refs`
9. approval, kernel, and sandbox read surfaces now preserve richer operator input split and affected transition or resource refs instead of truncating those summaries to receipt-only evidence

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `ReconciliationRecord` | `partial` | `partial` | Reconciliation authority is now durable for sandbox `lost_runtime` closure, unsafe governed turn `resume_mode` closeout including orphan operation-artifact detection, and Gitea worker claim-transition failure, with sandbox operator views now able to surface the latest reconciliation summary when durable truth exists. Broader divergence classes and continuation paths still need to publish the same record family. |
| `OperatorAction` | `partial` | `partial` | Explicit authenticated sandbox stop, session halt, interaction cancel, approval resolution, pending-gate approval, and governed kernel session-end paths now publish first-class operator actions with affected transition and resource refs preserved on supported read surfaces. Broader non-sandbox operator behavior is still not universalized through one shared authority family. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 5 slices:
1. `orket/application/services/sandbox_lifecycle_reconciliation_service.py`
2. `orket/application/services/sandbox_control_plane_reconciliation_service.py`
3. `orket/application/services/turn_tool_control_plane_reconciliation.py`
4. `orket/application/services/turn_tool_control_plane_recovery.py`
5. `orket/application/services/gitea_state_control_plane_claim_failure_service.py`
6. `orket/application/services/pending_gate_control_plane_operator_service.py`
7. `orket/application/services/sandbox_control_plane_operator_service.py`
8. `orket/application/services/tool_approval_control_plane_operator_service.py`
9. `orket/application/services/kernel_action_control_plane_operator_service.py`
10. `orket/application/services/kernel_action_control_plane_view_service.py`
11. `orket/application/services/sandbox_lifecycle_view_service.py`
12. `orket/application/services/control_plane_target_resource_refs.py`
13. `orket/application/services/control_plane_publication_service.py`
14. `orket/interfaces/api.py`
15. `orket/interfaces/routers/sessions.py`
16. `orket/interfaces/routers/approvals.py`
17. `orket/interfaces/routers/kernel.py`
18. `orket/orchestration/engine.py`
19. `orket/orchestration/engine_approvals.py`
20. `orket/orchestration/approval_control_plane_read_model.py`
21. `orket/runtime/operator_override_logging_policy.py`
22. `orket/adapters/storage/async_control_plane_record_repository.py`

Representative tests changed or added:
1. `tests/interfaces/test_api_nervous_system_operator_surfaces.py`
2. `tests/application/test_tool_approval_control_plane_operator_service.py`
3. `tests/application/test_pending_gate_control_plane_operator_service.py`
4. `tests/application/test_kernel_action_control_plane_operator_service.py`
5. `tests/integration/test_sandbox_lifecycle_reconciliation_service.py`
6. `tests/integration/test_gitea_state_worker_control_plane.py`

Docs changed:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_5_CLOSEOUT.md`

## Proof executed

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py tests/application/test_tool_approval_control_plane_operator_service.py tests/application/test_pending_gate_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_operator_service.py tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_gitea_state_worker_control_plane.py`
   Result: `23 passed`

## Compatibility exits

Workstream 5 compatibility exits affected by the slices recorded here:
1. `CE-06` narrowed, not closed
   Reason: explicit reconciliation and operator-action publication now exist on the covered sandbox, governed turn, approval, kernel, and Gitea paths, and touched read surfaces now preserve that durable authority detail, but broader endpoint-local and policy-local operator behavior still survives outside one universal publication family.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. subsystem-local reconciliation behavior outside the recorded sandbox, governed turn, and Gitea slices
   Reason: those covered paths now publish first-class reconciliation authority, but broader divergence handling still remains path-specific.
2. endpoint-local or log-local operator behavior outside the covered authenticated command paths
   Reason: the main authenticated sandbox, session, interaction, approval, pending-gate, and governed-kernel paths now publish first-class operator actions, but broader non-sandbox operator influence is still not universal.

## Remaining gaps and blockers

Workstream 5 is still open.

Remaining gaps:
1. broader divergence classes and safe-continuation paths still need to publish one shared reconciliation family
2. broader non-sandbox operator surfaces still are not published through one universal operator-action authority family
3. final-truth consumers still need wider direct input wiring from reconciliation and operator-action records beyond the already-covered paths
4. `CE-06` remains open

## Authority-story updates landed with these slices

The following authority docs were updated in this closeout-recording slice:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_5_CLOSEOUT.md`

## Verdict

Workstream 5 now has a truthful partial closeout artifact for the reconciliation and operator-action slices already landed on the sandbox, governed turn, approval, kernel, and Gitea paths, but the workstream remains open until those authority families are universal across broader runtime divergence and operator behavior.
