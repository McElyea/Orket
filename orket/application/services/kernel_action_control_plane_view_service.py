from __future__ import annotations

from typing import Any

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
        final_truth = await self.record_repository.get_final_truth(run_id=run_id)
        effects = await self.record_repository.list_effect_journal_entries(run_id=run_id)
        operator_actions = await self.record_repository.list_operator_actions(target_ref=run_id)
        reservation = await self.record_repository.get_latest_reservation_record_for_holder_ref(holder_ref=run_id)
        latest_operator_action = operator_actions[-1] if operator_actions else None
        latest_step = steps[-1] if steps else None
        return {
            "run_id": run.run_id,
            "run_state": run.lifecycle_state.value,
            "current_attempt_id": None if attempt is None else attempt.attempt_id,
            "current_attempt_state": None if attempt is None else attempt.attempt_state.value,
            "latest_reservation": None if reservation is None else _reservation_summary(reservation),
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


__all__ = ["KernelActionControlPlaneViewService"]
