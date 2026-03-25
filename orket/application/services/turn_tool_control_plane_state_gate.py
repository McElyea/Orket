from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import EffectJournalEntryRecord, FinalTruthRecord, RunRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import ResultClass, RunState


async def ensure_existing_run_allows_execution(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    error_type: type[Exception],
) -> FinalTruthRecord | None:
    if run.final_truth_record_id is not None:
        truth = await publication.repository.get_final_truth(run_id=run.run_id)
        if truth is None:
            raise error_type(
                f"governed turn run {run.run_id} carries final_truth_record_id without durable final truth"
            )
        if run.final_truth_record_id != truth.final_truth_record_id:
            run = run.model_copy(update={"final_truth_record_id": truth.final_truth_record_id})
            await execution_repository.save_run_record(record=run)
        if truth.result_class is ResultClass.SUCCESS and run.lifecycle_state is RunState.COMPLETED:
            return truth
        raise error_type(
            f"governed turn run {run.run_id} already closed with "
            f"{truth.result_class.value} via {truth.closure_basis.value}; execution cannot continue"
        )
    if run.lifecycle_state in {
        RunState.RECOVERY_PENDING,
        RunState.RECONCILING,
        RunState.RECOVERING,
        RunState.OPERATOR_BLOCKED,
        RunState.QUARANTINED,
        RunState.FAILED_TERMINAL,
        RunState.CANCELLED,
        RunState.COMPLETED,
    }:
        raise error_type(
            f"governed turn run {run.run_id} is in {run.lifecycle_state.value}; "
            "explicit recovery or closure is required before execution can continue"
        )
    return None


async def existing_effect_for_operation(
    *,
    publication: ControlPlanePublicationService,
    run_id: str,
    effect_id: str,
) -> EffectJournalEntryRecord | None:
    entries = await publication.repository.list_effect_journal_entries(run_id=run_id)
    for entry in entries:
        if entry.effect_id == effect_id:
            return entry
    return None


__all__ = [
    "ensure_existing_run_allows_execution",
    "existing_effect_for_operation",
]
