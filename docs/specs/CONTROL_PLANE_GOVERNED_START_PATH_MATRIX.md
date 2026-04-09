# ControlPlane Governed Start-Path Matrix
Last updated: 2026-04-09
Status: Active durable governance companion
Owner: Orket Core

## Purpose

Preserve the active workload-authority decision lock and governed start-path matrix after ControlPlane project closeout.

## Active authorities

1. [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)
2. [docs/specs/WORKLOAD_CONTRACT_V1.md](docs/specs/WORKLOAD_CONTRACT_V1.md)
3. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## Workload Authority Decision Lock

The active workload-authority lock is:

1. exactly one repo seam may mint governed `WorkloadRecord` objects for start paths: `orket/application/services/control_plane_workload_catalog.py`
2. all other workload surfaces may only provide raw input data, call that seam, or read/project an already-built canonical workload record
3. runtime-local adapters, extension models, and workload-specific entrypoints may not import or call low-level control-plane workload builders directly
4. the governed start-path matrix below is a closure gate, not passive inventory: any non-test module that directly consumes workload authority from `control_plane_workload_catalog.py` must appear there with a truthful classification, and rock wrappers must remain routing-only retirement debt rather than regaining standalone workload-authority status
5. touched catalog-resolved publishers may not reintroduce local `workload_id` / `workload_version` authority aliases after receiving canonical `WorkloadRecord` objects from the shared catalog
6. `run_card(...)` is the sole public runtime execution surface, so `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` may survive only as thin compatibility wrappers that normalize inputs and delegate back to it, while rock execution may remain only as routing-only retirement debt rather than a standalone workload-authority surface

## Governed Start-Path Matrix

This matrix is machine-enforced by `tests/application/test_control_plane_workload_authority_governance.py`.

| Start path | Current authority status | Truthful note |
| --- | --- | --- |
| cards epic execution | `projection-resolved` | `run_card(...)` is the canonical public runtime surface, and its normalized dispatcher resolves cards-epic `workload.contract.v1` payloads plus `WorkloadRecord` projection through `control_plane_workload_catalog.py`. |
| atomic issue execution | `projection-resolved` | `run_card(...)` is the canonical public runtime surface for issue execution too; its normalized dispatcher resolves issue cards onto the cards-epic path and `ExecutionPipeline._run_issue_entry(...)` routes those starts through `_run_epic_entry(..., target_issue_id=...)`, so the cards workload projection still resolves through `control_plane_workload_catalog.py`. |
| ODR / run arbiter | `projection-resolved` | `scripts/odr/run_arbiter.py` emits raw `workload.contract.v1` payload and resolves its `WorkloadRecord` through `_resolve_odr_arbiter_control_plane_workload_from_contract(...)`. |
| manual review-run | `catalog-resolved` | `ReviewRunControlPlaneService` consumes `REVIEW_RUN_WORKLOAD` from the shared catalog and carries that canonical `WorkloadRecord` directly into run publication. |
| sandbox runtime | `catalog-resolved` | sandbox start paths consume `sandbox_runtime_workload_for_tech_stack(...)` from the shared catalog. |
| kernel action | `catalog-resolved` | `KernelActionControlPlaneService` consumes `KERNEL_ACTION_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication. |
| governed turn-tool | `catalog-resolved` | `TurnToolControlPlaneService` consumes `TURN_TOOL_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication; `turn_executor_control_plane.py` and `turn_tool_dispatcher_control_plane.py` remain adapter-only routing seams that do not mint workload authority locally. |
| orchestrator issue dispatch | `catalog-resolved` | `OrchestratorIssueControlPlaneService` consumes `ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication. |
| orchestrator scheduler mutation | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD` and carries that canonical `WorkloadRecord` through namespace-mutation helpers. |
| orchestrator child workload composition | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD` and carries that canonical `WorkloadRecord` through namespace-mutation helpers. |
| Gitea state worker | `catalog-resolved` | `GiteaStateControlPlaneExecutionService` consumes `GITEA_STATE_WORKER_EXECUTION_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication. |
| extension workload execution | `projection-resolved` | `ExtensionManager.run_workload(...)` resolves one canonical extension `WorkloadRecord` through the shared seam at workload start and carries that same record through the returned extension result and provenance. |
| rock entrypoints that initiate governed execution | `routing-only` | the legacy CLI `--rock` alias routes through `run_rock(...)`, a thin wrapper over `run_card(...)`; internal rock routing remains routing-only retirement debt and does not mint standalone rock `WorkloadRecord` authority. |

## Surviving Projection-Only Or Temporary Surfaces

The following projection or compatibility surfaces remain allowed:

1. extension-manifest workload metadata surfaces under `orket/extensions/`
2. `orket/runtime/run_start_artifacts.py`
3. `orket/runtime/run_summary.py`
4. `orket/application/review/lanes/`
5. `orket/runtime/retry_classification_policy.py`, `orket/runtime/run_start_contract_artifacts.py`, `scripts/governance/check_retry_classification_policy.py`, and `scripts/governance/run_runtime_truth_acceptance_gate.py`

These surfaces may emit evidence or metadata, but they do not become co-equal workload authority.

## Historical Record

The ControlPlane project closeout archive lives at [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md).
