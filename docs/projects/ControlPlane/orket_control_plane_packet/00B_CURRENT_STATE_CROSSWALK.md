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
| `Attempt` | Retry and lane behavior exist, but there is no durable first-class attempt object with append-only history. | `orket/application/review/lanes/`; `orket/runtime/retry_classification_policy.py`; sandbox restart and recovery services under `orket/application/services/` | missing | Current retry surfaces must stop collapsing history into loop behavior. | high |
| `Step` | Step-like identity exists in tool invocation contracts and protocol hashing, but not as a first-class control-plane object. | `orket/application/workflows/tool_invocation_contracts.py`; `orket/application/workflows/protocol_hashing.py` | partial | Existing `step_id` seams can be promoted into governed step records. | medium |
| `Effect` | Receipts, runtime artifacts, and run summary surfaces capture parts of effect truth, but not as one authoritative effect model. | `workspace/observability/<run_id>/`; `orket/runtime/protocol_receipt_materializer.py`; `orket/runtime/run_summary.py` | partial | The new effect journal must stop effect truth from being reconstructed after the fact. | high |
| `Resource` | Sandbox lifecycle services are the clearest current governed resource family. | `orket/application/services/sandbox_runtime_lifecycle_service.py`; `orket/application/services/sandbox_runtime_inspection_service.py`; `orket/application/services/sandbox_lifecycle_view_service.py` | partial | Current sandbox resource truth should become one instance of the general resource model rather than a special-case authority. | medium |
| `Reservation` | No first-class reservation object exists today. | no canonical current surface | missing | Admission, exclusivity, and starvation behavior cannot remain implicit once scheduling publishes reservation truth. | high |
| `Lease` | Lease-like semantics already exist in state backend and coordinator paths, but not as a generalized control-plane lease model. | `orket/core/contracts/state_backend.py`; `orket/core/domain/coordinator_card.py`; sandbox cleanup and lifecycle services under `orket/application/services/` | partial | Existing lease seams are useful but too narrow and too subsystem-specific. | medium |
| `Checkpoint` | `ReviewSnapshot` and snapshot loading provide a partial checkpoint seam. | `orket/application/review/snapshot_loader.py`; `orket/application/review/models.py`; [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) section 24 | partial | Snapshot existence must not imply resumability. Checkpoint acceptance still needs supervisor-owned rules. | medium |
| `RecoveryDecision` | Sandbox recovery and restart policy services contain parts of recovery logic, but not a durable first-class recovery-decision record. | `orket/application/services/sandbox_runtime_recovery_service.py`; `orket/application/services/sandbox_restart_policy_service.py` | partial | Recovery authority must move from service-local logic into durable control-plane objects. | high |
| `ReconciliationRecord` | Sandbox reconciliation exists but is not yet generalized as an authoritative reconciliation record family. | `orket/application/services/sandbox_lifecycle_reconciliation_service.py` | partial | Current reconciliation work is subsystem-specific and must be promoted into a general record model with stable divergence classes. | medium |
| `OperatorAction` | Operator surfaces exist in APIs and operator-policy artifacts, but not as one first-class control-plane action record. | `orket/interfaces/api.py`; `orket/interfaces/routers/companion.py`; `orket/interfaces/routers/sessions.py`; `orket/runtime/operator_override_logging_policy.py` | partial | Operator inputs must stop being scattered across endpoint behavior, policies, and logs. | medium |
| `FinalTruthRecord` | Run summary and runtime truth contracts provide partial closure truth today. | `orket/runtime/run_summary.py`; `orket/runtime/runtime_truth_contracts.py`; `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` | partial | Current closure truth is useful but not yet a first-class control-plane record tied to recovery, reconciliation, and terminality. | high |

## Current-state conclusion

The strongest current alignment exists around:
1. run identity and run-start artifacts
2. sandbox resource and reconciliation services
3. run summary and truthful-runtime classification work

The weakest areas, and therefore the primary implementation risks, are:
1. missing first-class `Reservation`
2. missing first-class `Attempt`
3. missing first-class `FinalTruthRecord`
4. fragmented recovery-decision and operator-action authority
5. effect truth reconstructed from artifacts rather than published through a normative effect journal

## Planning rule

The implementation lane must use this crosswalk to:
1. name which current surfaces are being promoted
2. name which current surfaces are being superseded
3. name which packet noun is still missing in code

If a planned code slice cannot point to a row in this crosswalk, the slice is not specific enough yet.
