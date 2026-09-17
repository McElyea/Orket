from __future__ import annotations

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.core.contracts.control_plane_models import OperatorActionRecord, RecoveryDecisionRecord
from orket.core.domain.control_plane_enums import (
    OperatorCommandClass,
    OperatorInputClass,
    RecoveryActionClass,
    SideEffectBoundaryClass,
)
from orket.core.domain.outward_authorization import canonical_json
from orket.core.domain.outward_model_admission import OutwardModelAdmission, admission_digest, model_attempt_id
from orket.core.domain.outward_model_recovery import OutwardModelRecoveryRequest


def model_recovery_records(
    request: OutwardModelRecoveryRequest, previous: OutwardModelAdmission, *, at: str,
) -> tuple[RecoveryDecisionRecord, OperatorActionRecord]:
    replacement_id = model_attempt_id(previous.run_id, previous.execution_generation, previous.turn,
                                      previous.step_index, previous.fencing_generation + 1)
    return _records(
        decision_id=request.decision_id, request_digest=request.digest_ref, actor=request.operator_ref,
        previous=previous, replacement_id=replacement_id, at=at,
    )


def _records(
    *, decision_id: str, request_digest: str, actor: str, previous: OutwardModelAdmission, replacement_id: str, at: str,
) -> tuple[RecoveryDecisionRecord, OperatorActionRecord]:
    decision = RecoveryDecisionRecord(
        decision_id=decision_id, run_id=previous.run_id, failed_attempt_id=previous.attempt_id,
        failure_classification_basis="model_response_unretained_before_governed_proposal",
        # This boundary is the governed connector, not a claim about provider invocation or billing.
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="outward_model_attempt_recovery.v1",
        authorized_next_action=RecoveryActionClass.START_NEW_ATTEMPT, new_attempt_id=replacement_id,
        operator_requirement=OperatorCommandClass.APPROVE_CONTINUE,
        required_precondition_refs=[request_digest, f"inputs:sha256:{previous.inputs_digest}",
                                    "governed_proposal:absent", "provider_execution_and_cost:unknown",
                                    f"owner:{previous.owner_id}:fence:{previous.fencing_generation}"],
        blocked_actions=["reuse_previous_owner", "rewrite_previous_evidence", "claim_provider_not_called", "dispatch_connector"],
        rationale_ref=replacement_id,
    )
    action = OperatorActionRecord(
        action_id=decision_id, actor_ref=actor, input_class=OperatorInputClass.COMMAND,
        command_class=OperatorCommandClass.APPROVE_CONTINUE, target_ref=previous.attempt_id,
        timestamp=at, precondition_basis_ref=request_digest, result="new_model_attempt_admitted",
        affected_transition_refs=[previous.attempt_id, replacement_id], receipt_refs=[replacement_id],
    )
    return decision, action


def model_recovery_commitment(records: tuple[RecoveryDecisionRecord, OperatorActionRecord]) -> str:
    decision, action = records
    return admission_digest(canonical_json({"decision": decision.model_dump(mode="json"), "action": action.model_dump(mode="json")}))


async def validate_model_attempt_history(transaction: OutwardStoreTransaction, attempts: list[OutwardModelAdmission]) -> None:
    for index, attempt in enumerate(attempts):
        if attempt.fencing_generation != index + 1:
            raise RuntimeError("E_OUTWARD_MODEL_ATTEMPT_HISTORY_GAP")
        if index == 0:
            continue
        previous = attempts[index - 1]
        if previous.state != "claimed" or previous.inputs_json != attempt.inputs_json:
            raise RuntimeError("E_OUTWARD_MODEL_ATTEMPT_HISTORY_CONFLICT")
        records = await transaction.recovery.get(attempt.recovery_decision_id)
        if records is None:
            raise RuntimeError("E_OUTWARD_MODEL_RECOVERY_RECORD_MISSING")
        if model_recovery_commitment(records) != attempt.recovery_records_digest:
            raise RuntimeError("E_OUTWARD_MODEL_RECOVERY_RECORD_MISMATCH")
        decision, action = records
        expected = _records(decision_id=attempt.recovery_decision_id, request_digest=action.precondition_basis_ref,
                            actor=action.actor_ref, previous=previous, replacement_id=attempt.attempt_id, at=attempt.created_at)
        if records != expected or not decision.required_precondition_refs:
            raise RuntimeError("E_OUTWARD_MODEL_RECOVERY_RECORD_MISMATCH")
