from __future__ import annotations

from dataclasses import asdict

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.outward_run_execution_plan import current_step_index
from orket.core.domain.outward_authorization import canonical_json
from orket.core.domain.outward_model_admission import OutwardModelAdmission, admission_digest
from orket.core.domain.outward_runs import OutwardRunRecord


async def admit_model_turn(transaction: OutwardStoreTransaction, run: OutwardRunRecord, *, at: str) -> None:
    if run.status != "running" or run.pending_proposals:
        raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_RUN_STATE")
    inputs = canonical_json(asdict(run))
    await transaction.models.create(OutwardModelAdmission(
        run_id=run.run_id, execution_generation=run.execution_generation, turn=run.current_turn,
        step_index=current_step_index(run), inputs_json=inputs, inputs_digest=admission_digest(inputs),
        state="ready", created_at=at,
    ))


def validate_admission_inputs(admission: OutwardModelAdmission, run: OutwardRunRecord) -> None:
    if canonical_json(asdict(run)) != admission.inputs_json:
        raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_INPUT_DRIFT")
