from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from orket.adapters.storage.outward_store_transaction import OutwardStoreUnitOfWork
from orket.application.services.outward_control_plane_service import require_outward_authority
from orket.application.services.outward_model_admission_inputs import validate_admission_inputs
from orket.application.services.outward_model_recovery_records import (
    model_recovery_commitment,
    model_recovery_records,
    validate_model_attempt_history,
)
from orket.application.services.outward_run_execution_plan import current_step_index
from orket.core.domain.outward_model_admission import OutwardModelAdmission
from orket.core.domain.outward_model_recovery import OutwardModelRecoveryRequest


class OutwardModelRecoveryService:
    def __init__(self, unit_of_work: OutwardStoreUnitOfWork, utc_now: Callable[[], str]) -> None:
        self.unit_of_work, self.utc_now = unit_of_work, utc_now

    async def inspect(self, run_id: str) -> dict[str, Any]:
        async with self.unit_of_work.transaction() as transaction:
            run = await transaction.get_run(run_id)
            if run is None:
                raise ValueError(f"Run '{run_id}' not found")
            attempts = await transaction.models.list_attempts(run_id, run.execution_generation, run.current_turn, current_step_index(run))
            await validate_model_attempt_history(transaction, attempts)
            return {"run_id": run_id, "admission": _summary(attempts[-1]) if attempts else None,
                    "attempts": [_summary(attempt) for attempt in attempts]}

    async def recover(
        self, run_id: str, *, request_id: str, execution_generation: int, turn: int, step_index: int,
        expected_owner_id: str, expected_fencing_generation: int, operator_ref: str,
    ) -> dict[str, Any]:
        return await self._recover(OutwardModelRecoveryRequest(
            run_id, request_id, execution_generation, turn, step_index,
            expected_owner_id, expected_fencing_generation, operator_ref,
        ))

    async def _recover(self, request: OutwardModelRecoveryRequest) -> dict[str, Any]:
        async with self.unit_of_work.transaction() as transaction:
            run = await transaction.get_run(request.run_id)
            if run is None:
                raise ValueError(f"Run '{request.run_id}' not found")
            await require_outward_authority(transaction, run)
            attempts = await transaction.models.list_attempts(request.run_id, request.execution_generation, request.turn, request.step_index)
            await validate_model_attempt_history(transaction, attempts)
            if not attempts:
                raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_MISSING")
            previous = attempts[-1]
            retained = await transaction.recovery.get(request.decision_id)
            if retained is not None:
                decision, action = retained
                if action.precondition_basis_ref != request.digest_ref or action.actor_ref != request.operator_ref:
                    raise RuntimeError("E_OUTWARD_MODEL_RECOVERY_REQUEST_CONFLICT")
                if previous.recovery_decision_id != request.decision_id or decision.new_attempt_id != previous.attempt_id:
                    raise RuntimeError("E_OUTWARD_MODEL_RECOVERY_SUPERSEDED")
                return _summary(previous)
            if previous.state != "claimed":
                raise RuntimeError("E_OUTWARD_MODEL_RECOVERY_REQUIRES_UNOBSERVED_CLAIM")
            if previous.owner_id != request.expected_owner_id or previous.fencing_generation != request.expected_fencing_generation:
                raise RuntimeError("E_OUTWARD_MODEL_RECOVERY_STALE_OWNER")
            validate_admission_inputs(previous, run)
            at = self.utc_now()
            records = model_recovery_records(request, previous, at=at)
            replacement = replace(previous, state="ready", owner_id=None, claimed_at=None, created_at=at,
                                  fencing_generation=previous.fencing_generation + 1, evidence_layout_version=2,
                                  recovery_decision_id=request.decision_id, recovery_records_digest=model_recovery_commitment(records))
            await transaction.recovery.save(*records)
            await transaction.models.create(replacement)
            return _summary(replacement)


def _summary(attempt: OutwardModelAdmission) -> dict[str, Any]:
    return {"run_id": attempt.run_id, "execution_generation": attempt.execution_generation,
            "turn": attempt.turn, "step_index": attempt.step_index, "attempt_id": attempt.attempt_id,
            "state": attempt.state, "owner_id": attempt.owner_id, "fencing_generation": attempt.fencing_generation,
            "inputs_digest": attempt.inputs_digest, "result_digest": attempt.result_digest,
            "evidence_layout_version": attempt.evidence_layout_version, "recovery_decision_id": attempt.recovery_decision_id,
            "created_at": attempt.created_at, "claimed_at": attempt.claimed_at,
            "observed_at": attempt.observed_at, "published_at": attempt.published_at}
