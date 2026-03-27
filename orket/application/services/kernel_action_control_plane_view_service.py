from __future__ import annotations

from typing import Any

from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    holder_ref_for_run,
    lease_id_for_run,
    reservation_id_for_run,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService


class KernelActionControlPlaneViewService:
    """Builds read-model summaries for governed kernel-action control-plane state."""

    def __init__(self, *, record_repository, execution_repository) -> None:
        self.record_repository = record_repository
        self.execution_repository = execution_repository

    async def build_summary(self, *, session_id: str, trace_id: str) -> dict[str, Any] | None:
        run_id = KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id)
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            return None
        attempt = None
        steps = []
        if run.current_attempt_id is not None:
            attempt = await self.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
        if attempt is None:
            attempts = await self.execution_repository.list_attempt_records(run_id=run_id)
            if attempts:
                attempt = attempts[-1]
        if attempt is not None:
            steps = await self.execution_repository.list_step_records(attempt_id=attempt.attempt_id)
        recovery_decision = None
        if attempt is not None and attempt.recovery_decision_id is not None:
            recovery_decision = await self.record_repository.get_recovery_decision(
                decision_id=attempt.recovery_decision_id
            )
        final_truth = await self.record_repository.get_final_truth(run_id=run_id)
        effects = await self.record_repository.list_effect_journal_entries(run_id=run_id)
        operator_actions = await self.record_repository.list_operator_actions(target_ref=run_id)
        lease = await self.record_repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
        reservations = await _reservation_candidates(record_repository=self.record_repository, run_id=run_id)
        reservation = _select_reservation_summary_candidate(reservations)
        latest_operator_action = operator_actions[-1] if operator_actions else None
        latest_step = steps[-1] if steps else None
        return {
            "run_id": run.run_id,
            "run_state": run.lifecycle_state.value,
            "current_attempt_id": None if attempt is None else attempt.attempt_id,
            "current_attempt_state": None if attempt is None else attempt.attempt_state.value,
            "current_attempt_side_effect_boundary_class": None
            if attempt is None or attempt.side_effect_boundary_class is None
            else attempt.side_effect_boundary_class.value,
            "current_attempt_failure_class": None if attempt is None else attempt.failure_class,
            "current_attempt_failure_plane": None
            if attempt is None or attempt.failure_plane is None
            else attempt.failure_plane.value,
            "current_attempt_failure_classification": None
            if attempt is None or attempt.failure_classification is None
            else attempt.failure_classification.value,
            "current_recovery_decision_id": None if attempt is None else attempt.recovery_decision_id,
            "current_recovery_action": None
            if recovery_decision is None
            else recovery_decision.authorized_next_action.value,
            "latest_reservation": None if reservation is None else _reservation_summary(reservation),
            "latest_lease": None if lease is None else _lease_summary(lease),
            "step_count": len(steps),
            "latest_step": None
            if latest_step is None
            else {
                "step_id": latest_step.step_id,
                "step_kind": latest_step.step_kind,
                "namespace_scope": latest_step.namespace_scope,
                "observed_result_classification": latest_step.observed_result_classification,
                "closure_classification": latest_step.closure_classification,
                "output_ref": latest_step.output_ref,
                "resources_touched": list(latest_step.resources_touched),
                "receipt_refs": list(latest_step.receipt_refs),
            },
            "final_truth": None
            if final_truth is None
            else {
                "final_truth_record_id": final_truth.final_truth_record_id,
                "result_class": final_truth.result_class.value,
                "completion_classification": final_truth.completion_classification.value,
                "evidence_sufficiency_classification": final_truth.evidence_sufficiency_classification.value,
                "residual_uncertainty_classification": final_truth.residual_uncertainty_classification.value,
                "degradation_classification": final_truth.degradation_classification.value,
                "closure_basis": final_truth.closure_basis.value,
                "terminality_basis": final_truth.terminality_basis.value,
                "authoritative_result_ref": final_truth.authoritative_result_ref,
                "authority_sources": [source.value for source in final_truth.authority_sources],
            },
            "effect_entry_count": len(effects),
            "latest_operator_action": None
            if latest_operator_action is None
            else {
                "action_id": latest_operator_action.action_id,
                "input_class": latest_operator_action.input_class.value,
                "command_class": None
                if latest_operator_action.command_class is None
                else latest_operator_action.command_class.value,
                "risk_acceptance_scope": latest_operator_action.risk_acceptance_scope,
                "attestation_scope": latest_operator_action.attestation_scope,
                "attestation_payload": dict(latest_operator_action.attestation_payload),
                "precondition_basis_ref": latest_operator_action.precondition_basis_ref,
                "result": latest_operator_action.result,
                "actor_ref": latest_operator_action.actor_ref,
                "timestamp": latest_operator_action.timestamp,
                "receipt_refs": list(latest_operator_action.receipt_refs),
            },
        }


def _reservation_summary(record: Any) -> dict[str, Any]:
    return {
        "reservation_id": record.reservation_id,
        "reservation_kind": record.reservation_kind.value,
        "status": record.status.value,
        "holder_ref": record.holder_ref,
        "target_scope_ref": record.target_scope_ref,
        "expiry_or_invalidation_basis": record.expiry_or_invalidation_basis,
        "supervisor_authority_ref": record.supervisor_authority_ref,
        "promoted_lease_id": record.promoted_lease_id,
    }


def _lease_summary(record: Any) -> dict[str, Any]:
    return {
        "lease_id": record.lease_id,
        "resource_id": record.resource_id,
        "holder_ref": record.holder_ref,
        "lease_epoch": record.lease_epoch,
        "status": record.status.value,
        "expiry_basis": record.expiry_basis,
        "cleanup_eligibility_rule": record.cleanup_eligibility_rule,
        "source_reservation_id": record.source_reservation_id,
        "last_confirmed_observation": record.last_confirmed_observation,
    }


async def _reservation_candidates(*, record_repository: Any, run_id: str) -> list[Any]:
    candidates: list[Any] = []
    direct_target = await record_repository.get_latest_reservation_record_for_holder_ref(holder_ref=run_id)
    if direct_target is not None:
        candidates.append(direct_target)
    run_owned = await record_repository.get_latest_reservation_record_for_holder_ref(
        holder_ref=holder_ref_for_run(run_id=run_id)
    )
    if run_owned is not None:
        candidates.append(run_owned)
    canonical = await record_repository.get_latest_reservation_record(reservation_id=reservation_id_for_run(run_id=run_id))
    if canonical is not None:
        candidates.append(canonical)
    deduped: dict[tuple[str, str, str, str | None], Any] = {}
    for record in candidates:
        deduped[(record.reservation_id, record.status.value, record.expiry_or_invalidation_basis, record.promoted_lease_id)] = record
    return list(deduped.values())


def _select_reservation_summary_candidate(records: list[Any]) -> Any | None:
    if not records:
        return None
    rank_by_status = {
        "reservation_promoted_to_lease": 4,
        "reservation_active": 3,
        "reservation_released": 2,
        "reservation_cancelled": 1,
        "reservation_invalidated": 1,
        "reservation_expired": 1,
    }
    return max(
        records,
        key=lambda record: (
            rank_by_status.get(record.status.value, 0),
            2 if record.reservation_kind.value == "operator_hold_reservation" else 1,
            str(record.creation_timestamp),
            str(record.reservation_id),
        ),
    )


__all__ = ["KernelActionControlPlaneViewService"]
