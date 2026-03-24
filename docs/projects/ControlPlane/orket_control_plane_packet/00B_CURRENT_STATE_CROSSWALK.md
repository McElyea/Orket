# Current-State Crosswalk
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation / current-state crosswalk

## Purpose

Map current Orket runtime surfaces to the control-plane nouns in this packet.

This document exists to prevent clean-room architecture drift.
It is an honest migration map, not a claim that the current runtime already implements the full control plane.

## Crosswalk

| New control-plane noun | Current surface | Current file or artifact | Status | Migration note | Implementation risk |
| --- | --- | --- | --- | --- | --- |
| `Workload` | Multiple workload-like surfaces exist across runtime workloads, rocks, and extension entrypoints. There is no single unified governed workload object yet. | `orket/runtime/workload_adapters.py`; extension manifests under `extensions/`; workload-facing runtime contracts under `docs/specs/WORKLOAD_CONTRACT_V1.md` | conflicting | The implementation lane must create one canonical workload definition surface instead of continuing with parallel workload nouns. | high |
| `Run` | `ReviewRun` plus run-start artifacts provide the clearest current run-like surface. | `orket/application/review/run_service.py`; `orket/runtime/run_start_artifacts.py`; `orket/runtime/run_summary.py`; [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) section 24 | partial | Current run truth is split between review flow objects and observability artifacts. The control plane needs one authoritative run object. | high |
| `Attempt` | Retry and lane behavior still dominate runtime execution, but first-class attempt contracts and lifecycle guards now exist in core. | `orket/application/review/lanes/`; `orket/runtime/retry_classification_policy.py`; `orket/core/contracts/control_plane_models.py`; `orket/core/domain/control_plane_lifecycle.py`; sandbox restart and recovery services under `orket/application/services/` | partial | The contract family exists, but runtime execution still collapses attempt history into service-local behavior instead of publishing durable attempt records. | high |
| `Step` | Step-like identity exists in tool invocation contracts and protocol hashing, but not as a first-class control-plane object. | `orket/application/workflows/tool_invocation_contracts.py`; `orket/application/workflows/protocol_hashing.py` | partial | Existing `step_id` seams can be promoted into governed step records. | medium |
| `Effect` | Receipts, runtime artifacts, and run summary surfaces still capture parts of effect truth, and a first-class effect-journal authority surface now exists in core. | `workspace/observability/<run_id>/`; `orket/runtime/protocol_receipt_materializer.py`; `orket/runtime/run_summary.py`; `orket/core/contracts/control_plane_effect_journal_models.py`; `orket/core/domain/control_plane_effect_journal.py`; `orket/application/services/control_plane_publication_service.py`; `orket/adapters/storage/async_control_plane_record_repository.py` | partial | The journal model and persistence seam exist, but live workload execution does not yet publish effect truth through that journal by default. | high |
| `Resource` | Sandbox lifecycle services are the clearest current governed resource family. | `orket/application/services/sandbox_runtime_lifecycle_service.py`; `orket/application/services/sandbox_runtime_inspection_service.py`; `orket/application/services/sandbox_lifecycle_view_service.py` | partial | Current sandbox resource truth should become one instance of the general resource model rather than a special-case authority. | medium |
| `Reservation` | First-class reservation contracts and reservation-to-lease progression rules now exist in core, but admission and scheduling do not yet consume them. | `orket/core/contracts/control_plane_models.py`; `orket/core/domain/control_plane_reservations.py` | partial | Reservation authority now exists as code-level truth, but scheduling still needs to publish and enforce it in live paths. | high |
| `Lease` | Lease-like semantics already exist in state backend and coordinator paths, and sandbox lifecycle now publishes first-class lease snapshots on the default runtime path. | `orket/core/contracts/control_plane_models.py`; `orket/core/contracts/state_backend.py`; `orket/core/domain/coordinator_card.py`; `orket/application/services/sandbox_control_plane_lease_service.py`; sandbox cleanup, reconciliation, and lifecycle services under `orket/application/services/`; `orket/adapters/storage/async_control_plane_record_repository.py`; `orket/services/sandbox_orchestrator.py` | partial | Sandbox runtime can now publish pending, active, expired, uncertain, and released lease truth, but admission, scheduling, and other subsystems still do not consume one shared lease authority family. | medium |
| `Checkpoint` | `ReviewSnapshot` and snapshot loading remain useful existing seams, and checkpoint plus checkpoint-acceptance contracts now exist in core. | `orket/application/review/snapshot_loader.py`; `orket/application/review/models.py`; `orket/core/contracts/control_plane_models.py`; `orket/core/contracts/control_plane_effect_journal_models.py`; `orket/core/domain/control_plane_effect_journal.py`; `orket/application/services/control_plane_publication_service.py`; [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) section 24 | partial | Checkpoint existence and acceptance are now representable, but supervisor-owned resumability still is not wired through live execution flows. | medium |
| `RecoveryDecision` | Sandbox recovery and restart policy services still own live recovery behavior, and a durable first-class recovery-decision record family now exists in core. | `orket/application/services/sandbox_runtime_recovery_service.py`; `orket/application/services/sandbox_restart_policy_service.py`; `orket/core/contracts/control_plane_models.py`; `orket/core/domain/control_plane_recovery.py`; `orket/application/services/control_plane_publication_service.py`; `orket/adapters/storage/async_control_plane_record_repository.py` | partial | Recovery authority is now representable and durable, but runtime recovery paths still need to publish decisions instead of keeping them service-local. | high |
| `ReconciliationRecord` | Sandbox reconciliation remains subsystem-specific, but a first-class reconciliation publication path now exists for the `lost_runtime` closure case. | `orket/application/services/sandbox_lifecycle_reconciliation_service.py`; `orket/application/services/sandbox_control_plane_reconciliation_service.py`; `orket/application/services/control_plane_publication_service.py`; `orket/adapters/storage/async_control_plane_record_repository.py`; `orket/core/contracts/control_plane_models.py` | partial | Reconciliation authority is now durable for one important runtime closure path, but broader divergence classes and continuation paths still need to publish the same record family. | medium |
| `OperatorAction` | Operator surfaces exist in APIs and operator-policy artifacts, but not as one first-class control-plane action record. | `orket/interfaces/api.py`; `orket/interfaces/routers/companion.py`; `orket/interfaces/routers/sessions.py`; `orket/runtime/operator_override_logging_policy.py` | partial | Operator inputs must stop being scattered across endpoint behavior, policies, and logs. | medium |
| `FinalTruthRecord` | Run summary and runtime truth contracts still provide legacy closure truth, and a first-class control-plane final-truth record family now exists with partial sandbox workflow, policy, and lifecycle terminal-outcome integration plus `lost_runtime` reconciliation on the default orchestrator path. | `orket/runtime/run_summary.py`; `orket/runtime/runtime_truth_contracts.py`; `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`; `orket/core/contracts/control_plane_models.py`; `orket/core/domain/control_plane_final_truth.py`; `orket/application/services/control_plane_publication_service.py`; `orket/application/services/sandbox_control_plane_closure_service.py`; `orket/application/services/sandbox_control_plane_reconciliation_service.py`; `orket/application/services/sandbox_terminal_outcome_service.py`; `orket/application/services/sandbox_lifecycle_reconciliation_service.py`; `orket/adapters/storage/async_control_plane_record_repository.py`; `orket/services/sandbox_orchestrator.py` | partial | Final-truth authority now exists and sandbox workflow, policy, and lifecycle terminal outcomes plus `lost_runtime` reconciliation can publish it on the main sandbox runtime path, but other runtime closure paths still need to adopt the same authority surface. | high |

## Current-state conclusion

The strongest current alignment exists around:
1. run identity and run-start artifacts
2. sandbox resource, reconciliation, and lease publication services
3. control-plane contract, journal, recovery, lease, and final-truth publication seams in core and application services

The weakest areas, and therefore the primary implementation risks, are:
1. run and attempt authority are not yet runtime-owned durable records
2. reservation truth is not yet wired into admission and scheduling
3. lease truth is still sandbox-specific and not yet shared by admission, scheduling, or non-sandbox runtime paths
4. recovery-decision and operator-action authority are still fragmented in live runtime behavior
5. effect truth is still often reconstructed from artifacts instead of being published through the normative effect journal

## Planning rule

The implementation lane must use this crosswalk to:
1. name which current surfaces are being promoted
2. name which current surfaces are being superseded
3. name which packet noun is still missing in code

If a planned code slice cannot point to a row in this crosswalk, the slice is not specific enough yet.
