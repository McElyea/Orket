from __future__ import annotations

from orket.application.services.control_plane_resource_authority_checks import (
    require_resource_snapshot_matches_lease,
)
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run,
    namespace_resource_id_for_run,
    reservation_id_for_run,
)
from orket.core.contracts import EffectJournalEntryRecord, FinalTruthRecord, RunRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import LeaseStatus, ReservationStatus, ResultClass, RunState


async def ensure_existing_run_allows_execution(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    error_type: type[Exception],
) -> FinalTruthRecord | None:
    await _require_turn_tool_resource_authority(
        publication=publication,
        run=run,
        error_type=error_type,
    )
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


async def _require_turn_tool_resource_authority(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    error_type: type[Exception],
) -> None:
    reservation = await publication.repository.get_latest_reservation_record(
        reservation_id=reservation_id_for_run(run_id=run.run_id)
    )
    lease = await publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))

    if run.lifecycle_state is RunState.EXECUTING:
        if reservation is None:
            raise error_type(f"governed turn run {run.run_id} missing reservation authority during execution")
        if reservation.status is not ReservationStatus.PROMOTED_TO_LEASE:
            raise error_type(
                f"governed turn run {run.run_id} has non-promoted reservation during execution"
            )
        if lease is None:
            raise error_type(f"governed turn run {run.run_id} missing lease authority during execution")
        if lease.status is not LeaseStatus.ACTIVE:
            raise error_type(f"governed turn run {run.run_id} has non-active lease during execution")
        if lease.source_reservation_id != reservation.reservation_id:
            raise error_type(f"governed turn run {run.run_id} lease source mismatch during execution")
        resource = await publication.repository.get_latest_resource_record(
            resource_id=namespace_resource_id_for_run(run=run)
        )
        require_resource_snapshot_matches_lease(
            resource=resource,
            lease=lease,
            expected_resource_kind="turn_tool_namespace",
            expected_namespace_scope=str(run.namespace_scope or "").strip(),
            error_context=f"governed turn run {run.run_id} execution",
            error_factory=error_type,
        )
        return

    if run.final_truth_record_id is None or run.lifecycle_state is not RunState.COMPLETED:
        return

    if reservation is None:
        raise error_type(f"governed turn run {run.run_id} missing reservation authority on completed reuse")
    if reservation.status is not ReservationStatus.PROMOTED_TO_LEASE:
        raise error_type(
            f"governed turn run {run.run_id} has non-promoted reservation on completed reuse"
        )
    if lease is None:
        raise error_type(f"governed turn run {run.run_id} missing lease authority on completed reuse")
    if lease.status is not LeaseStatus.RELEASED:
        raise error_type(f"governed turn run {run.run_id} has non-released lease on completed reuse")
    if lease.source_reservation_id != reservation.reservation_id:
        raise error_type(f"governed turn run {run.run_id} lease source mismatch on completed reuse")
    resource = await publication.repository.get_latest_resource_record(
        resource_id=namespace_resource_id_for_run(run=run)
    )
    require_resource_snapshot_matches_lease(
        resource=resource,
        lease=lease,
        expected_resource_kind="turn_tool_namespace",
        expected_namespace_scope=str(run.namespace_scope or "").strip(),
        error_context=f"governed turn run {run.run_id} completed reuse",
        error_factory=error_type,
    )


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
