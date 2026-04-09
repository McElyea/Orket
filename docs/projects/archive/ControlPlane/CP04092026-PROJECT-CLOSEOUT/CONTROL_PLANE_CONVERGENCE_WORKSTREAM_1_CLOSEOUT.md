# Control-Plane Convergence Workstream 1 Closeout
Last updated: 2026-04-09
Status: Archived Workstream 1 closeout record
Owner: Orket Core
Workstream: 1 - Workload, run, attempt, and step authority convergence

Durable requirements authority:
1. `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`
2. `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`

Archived implementation record:
1. `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CONTROL_PLANE_WORKLOAD_RUN_AUTHORITY_FOLLOW_ON_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CLOSEOUT.md`
3. `docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CLOSEOUT.md`
4. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md`

## Objective

Keep the governed workload-authority lock and start-path matrix active through `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md` after Workstream 1 closure.

## Workstream 1 outcome

Workstream 1 is complete.

Closeout facts:
1. the required `Slice W1A` governed start-path workload-authority proof set remained green on `2026-04-09` without further runtime code changes
2. the required `Slice W1B` run / attempt / step projection proof set remained green on `2026-04-09` without further runtime code changes
3. `Slice W1C` synchronized the roadmap, packet docs, current-authority snapshot, and archive posture so the Workstream 1 closeout could land without leaving a contradictory active queue behind
4. `CE-01` and `CE-02` are closed for the governed start-path and projection-read surfaces covered by this companion

## Workload Authority Decision Lock

The slices recorded here now use this lock:
1. exactly one repo seam may mint governed `WorkloadRecord` objects for start paths: `orket/application/services/control_plane_workload_catalog.py`
2. all other workload surfaces may only provide raw input data, call that seam, or read/project an already-built canonical workload record
3. runtime-local adapters, extension models, and workload-specific entrypoints may not import or call low-level control-plane workload builders directly
4. the governed start-path matrix below is a closure gate, not passive inventory: any non-test module that directly consumes workload authority from `control_plane_workload_catalog.py` must appear there with a truthful classification, and rock wrappers must remain routing-only retirement debt rather than regaining standalone workload-authority status
5. touched catalog-resolved publishers may not reintroduce local `workload_id` / `workload_version` authority aliases after receiving canonical `WorkloadRecord` objects from the shared catalog
6. `run_card(...)` is the sole public runtime execution surface, so `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` may survive only as thin compatibility wrappers that normalize inputs and delegate back to it, while rock execution may remain only as routing-only retirement debt rather than a standalone workload-authority surface

## Governed Start-Path Matrix

The current workload-authority matrix for governed start paths is:

This matrix is now machine-enforced by `tests/application/test_control_plane_workload_authority_governance.py`. That governance test fails if a non-test module directly consumes workload authority from `control_plane_workload_catalog.py` without explicit matrix coverage, if touched catalog-resolved publishers reintroduce local `workload_id` / `workload_version` authority aliases, if the retired workload-adapter shim reappears or non-test repo code imports it, if non-test repo code imports the retired extension manifest alias, if non-CLI runtime callsites drift back onto `run_epic(...)`, `run_issue(...)`, or `run_rock(...)` compatibility wrappers, if public runtime wrappers stop collapsing back to `run_card(...)`, if the extension run-action adapter drifts back to treating `run_rock` as part of its primary run-op set instead of explicit legacy alias normalization, if the canonical `run_card(...)` dispatcher starts minting workload authority directly instead of routing into internal entrypoints, if governed turn-tool runtime entrypoints drift away from the exact adapter-only routing helpers that invoke `TurnToolControlPlaneService` without minting workload authority locally, if the interaction sessions router drifts back to a metadata-returning extension workload lookup instead of the validation-only `has_manifest_entry(...)` probe, if live benchmark tooling drifts back onto the legacy `--rock` CLI alias, back to rock-named runtime identifiers or `run_mode="rock"` in benchmark run metadata, or back to default `live-rock` execution-mode metadata, or if rock routing regains standalone workload-authority status.

| Start path | Current authority status | Truthful note |
| --- | --- | --- |
| cards epic execution | `projection-resolved` | `run_card(...)` is now the canonical public runtime surface, and its normalized dispatcher still resolves cards-epic `workload.contract.v1` payloads plus `WorkloadRecord` projection through `control_plane_workload_catalog.py`. |
| atomic issue execution | `projection-resolved` | `run_card(...)` is now the canonical public runtime surface for issue execution too; its normalized dispatcher resolves issue cards onto the cards-epic path and `ExecutionPipeline._run_issue_entry(...)` routes those starts through `_run_epic_entry(..., target_issue_id=...)`, so the cards workload projection still resolves through `control_plane_workload_catalog.py`. |
| ODR / run arbiter | `projection-resolved` | `scripts/odr/run_arbiter.py` now emits raw `workload.contract.v1` payload and resolves its `WorkloadRecord` through the catalog-local helper `_resolve_odr_arbiter_control_plane_workload_from_contract(...)`. |
| manual review-run | `catalog-resolved` | `ReviewRunControlPlaneService` consumes `REVIEW_RUN_WORKLOAD` from the shared catalog and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| sandbox runtime | `catalog-resolved` | sandbox start paths consume `sandbox_runtime_workload_for_tech_stack(...)` from the shared catalog. |
| kernel action | `catalog-resolved` | `KernelActionControlPlaneService` consumes `KERNEL_ACTION_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| governed turn-tool | `catalog-resolved` | `TurnToolControlPlaneService` consumes `TURN_TOOL_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs; `orket/application/workflows/turn_executor_control_plane.py` and `orket/application/workflows/turn_tool_dispatcher_control_plane.py` remain adapter-only routing seams that invoke that service without minting workload authority locally. |
| orchestrator issue dispatch | `catalog-resolved` | `OrchestratorIssueControlPlaneService` consumes `ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| orchestrator scheduler mutation | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD` and now carries that canonical `WorkloadRecord` through namespace-mutation helpers instead of restating workload string pairs. |
| orchestrator child workload composition | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD` and now carries that canonical `WorkloadRecord` through namespace-mutation helpers instead of restating workload string pairs. |
| Gitea state worker | `catalog-resolved` | `GiteaStateControlPlaneExecutionService` consumes `GITEA_STATE_WORKER_EXECUTION_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| extension workload execution | `projection-resolved` | `ExtensionManager.run_workload(...)` now resolves one canonical extension `WorkloadRecord` through the canonical seam at workload start and carries that same record through the returned extension result and provenance instead of minting it later in provenance generation. |
| rock entrypoints that initiate governed execution | `routing-only` | the legacy CLI `--rock` alias now routes through `run_rock(...)`, a thin wrapper over `run_card(...)`, while the named runtime recommendation surface points to `python main.py --card <card_id>`; the `run_rock(...)` wrappers now survive only as thin convenience wrappers over `run_card(...)` while the module-level `orchestrate_rock` helper is retired entirely, internal rock routing now flows through a generic epic-collection entry plus generic epic-collection runtime selectors that emit collection-shaped runtime payloads instead of a `rock` field, and rock paths still do not mint standalone rock `WorkloadRecord` authority. |

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. extension-manifest workload metadata surfaces under `orket/extensions/`
   Reason: extension manifest parsing now stays separated from canonical control-plane workload authority, and the surviving manifest-facing surfaces remain private compatibility metadata rather than execution authority.
2. `orket/runtime/run_start_artifacts.py`
   Reason: immutable session-scoped runtime bootstrap evidence remains valid as a projection and evidence package, but it cannot truthfully hold invocation-scoped cards epic run ids.
3. `orket/runtime/run_summary.py`
   Reason: legacy runtime summary output remains a projection surface for cards runs and proof paths; the governed read paths now either consume durable run / attempt / step truth directly or fail closed if projection framing drifts, but the summary remains compatibility and proof output rather than primary execution authority.
4. `orket/application/review/lanes/`
   Reason: deterministic and model-assisted review lanes remain evidence-producing review components, with persisted outputs explicitly marking execution state non-authoritative and staying guarded by shared review-bundle validation.
5. `orket/runtime/retry_classification_policy.py`, `orket/runtime/run_start_contract_artifacts.py`, `scripts/governance/check_retry_classification_policy.py`, and `scripts/governance/run_runtime_truth_acceptance_gate.py`
   Reason: retry policy remains projection-only attempt-history guidance with fail-closed validation, not durable attempt authority.

## Remaining broader packet drift

1. Workstream 1 is complete, but broader ControlPlane packet rows outside this companion still remain partial in `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`.
2. Future changes that widen workload authority beyond the matrix or let these surviving projection surfaces read like authority must reopen explicitly through `docs/ROADMAP.md`.

## Verdict

Workstream 1 is complete.

The bounded residual follow-on lane is closed and archived at `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/`. Broader ControlPlane follow-on work now runs through `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CONTROL_PLANE_PROJECT_CLOSEOUT_READINESS_IMPLEMENTATION_PLAN.md`, while the durable governed start-path matrix now lives at `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md` and this file remains the archived Workstream 1 closeout record.
