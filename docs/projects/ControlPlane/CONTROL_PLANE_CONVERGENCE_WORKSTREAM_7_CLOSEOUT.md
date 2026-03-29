# Control-Plane Convergence Workstream 7 Closeout
Last updated: 2026-03-28
Status: Partial closeout artifact
Owner: Orket Core
Workstream: 7 - Namespace and safe-tooling universalization

## Objective

Record the namespace and safe-tooling slices already landed under Workstream 7 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. governed turn-tool execution now uses an explicit default `issue:<issue_id>` namespace across protocol and non-protocol turns instead of ambient namespace targeting on the default execution pipeline path
2. governed turn-tool admission now publishes issue-scoped namespace reservation, execution lease, shared namespace-resource, and effect-linked governed execution under that explicit namespace authority
3. governed turn-tool existing-run execution, completed-run reuse, and resume preflight now fail closed when namespace, lease, resource, checkpoint, or policy truth drifts from the governed target instead of allowing ambient reuse
4. turn-tool dispatcher compatibility and policy-enforcement paths now fail closed on undeclared mutation scope and old namespace patterns before governed mutation begins
5. default orchestrator scheduler-owned issue transitions and team-replan child workload composition now publish issue-scoped namespace reservations, leases, shared resources, steps, effects, and final truth instead of hiding namespace mutation inside scheduler-local state
6. scheduler and governed turn-tool read or reuse paths now validate the latest namespace resource truth against lease authority instead of trusting lease-only history once durable namespace resource truth exists
7. the platform `no_old_namespaces` guard now enforces the removal boundary against stale namespace shapes

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Workload` | `conflicting` | `conflicting` | Governed turn-tool execution and scheduler-owned mutation paths now share explicit issue-scoped namespace targeting and governed workload publication on the covered paths, but runtime start paths still do not universalize one workload authority family. |
| `Reservation` | `partial` | `partial` | Governed turn-tool admission plus scheduler-owned mutation and child-workload composition now publish issue-scoped namespace reservations with explicit downstream dependency linkage, but broader admission and scheduling paths still do not share one reservation authority family. |
| `Lease` | `partial` | `partial` | Governed turn-tool execution plus scheduler-owned mutation and child-workload composition now publish and release explicit issue-scoped namespace leases, but other subsystems still do not share one universal lease authority family. |
| `Resource` | `partial` | `partial` | Governed turn-tool namespace execution plus scheduler-owned namespace mutation now publish shared namespace-resource truth and fail closed when the latest resource snapshot drifts from the lease, but broader runtime read surfaces still do not consume one universal resource-registry projection. |
| `Effect` | `partial` | `partial` | Governed turn-tool operations and scheduler-owned namespace mutations now publish effect truth under explicit namespace authority instead of ambient targeting, but broader workload execution still does not route effect publication through one universal safe-tooling boundary. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 7 slices:
1. `orket/application/workflows/turn_tool_dispatcher.py`
2. `orket/application/workflows/turn_executor_control_plane.py`
3. `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`
4. `orket/application/services/turn_tool_control_plane_service.py`
5. `orket/application/services/turn_tool_control_plane_state_gate.py`
6. `orket/runtime/execution_pipeline.py`
7. `orket/runtime/workload_adapters.py`
8. `orket/application/services/orchestrator_issue_control_plane_service.py`
9. `orket/application/services/orchestrator_scheduler_control_plane_service.py`
10. `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`
11. `orket/application/services/control_plane_publication_service.py`
12. `orket/core/contracts/control_plane_models.py`
13. `orket/adapters/storage/async_control_plane_record_repository.py`
14. `orket/interfaces/api.py`
15. `orket/interfaces/routers/kernel.py`
16. `orket/orchestration/engine.py`

Representative tests changed or added:
1. `tests/application/test_turn_tool_dispatcher_policy_enforcement.py`
2. `tests/application/test_turn_tool_dispatcher_compatibility.py`
3. `tests/application/test_turn_tool_control_plane_preflight_guards.py`
4. `tests/integration/test_turn_executor_control_plane.py`
5. `tests/platform/test_no_old_namespaces.py`
6. `tests/integration/test_orchestrator_scheduler_control_plane.py`

Docs changed:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_7_CLOSEOUT.md`

## Proof executed

Proof type: `structural`
Observed path: `primary`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/application/test_turn_tool_dispatcher_compatibility.py tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py tests/platform/test_no_old_namespaces.py tests/integration/test_orchestrator_scheduler_control_plane.py`
   Result: `34 passed`

## Compatibility exits

Workstream 7 compatibility exits affected by the slices recorded here:
1. `CE-08` narrowed, not closed
   Reason: governed turn-tool and scheduler-owned mutation paths now enforce explicit namespace targeting, durable namespace-linked reservation or lease or resource authority, and fail-closed safe-tooling guards on the covered paths, but broader runtime workloads and mutation families still do not share one universal namespace and safe-tooling boundary.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. `orket/runtime/workload_adapters.py` and extension-manifest entrypoints
   Reason: the covered governed paths now share explicit namespace authority, but broader runtime start paths still keep multiple workload entry surfaces alive.
2. governed and non-governed mutation paths outside the covered turn-tool and scheduler slices
   Reason: safe-tooling and namespace fail-closed behavior now exists on the covered paths, but it is not yet universal across every workload and resource-targeting family.

## Remaining gaps and blockers

Workstream 7 is still open.

Remaining gaps:
1. the `Workload` row remains `conflicting` because start-path authority is still not universal
2. broader runtime workloads, scheduling, resource targeting, and child composition still do not share one universal namespace authority surface
3. broader governed mutation paths still need to fail closed on undeclared capability scope and journal-free mutation through the same safe-tooling boundary
4. `CE-08` remains open

## Authority-story updates landed with these slices

The following authority docs were updated in this closeout-recording slice:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
2. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_7_CLOSEOUT.md`

## Verdict

Workstream 7 now has a truthful partial closeout artifact for the explicit namespace and safe-tooling hardening already landed on the governed turn-tool and scheduler-owned mutation paths, but the workstream remains open until the broader runtime shares that same fail-closed namespace and capability boundary.
