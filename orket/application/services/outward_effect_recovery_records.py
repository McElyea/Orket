from __future__ import annotations

from orket.core.contracts.control_plane_models import OperatorActionRecord, RecoveryDecisionRecord
from orket.core.domain.control_plane_enums import (
    OperatorCommandClass,
    OperatorInputClass,
    RecoveryActionClass,
    SideEffectBoundaryClass,
)
from orket.core.domain.outward_authorization import OutwardAuthorization
from orket.core.domain.outward_effects import OutwardEffectRecord, OutwardEffectRecoveryRequest


def recovery_records(
    request: OutwardEffectRecoveryRequest, binding: OutwardAuthorization,
    previous: OutwardEffectRecord, replacement: OutwardEffectRecord, *, at: str,
) -> tuple[RecoveryDecisionRecord, OperatorActionRecord]:
    decision = RecoveryDecisionRecord(
        decision_id=request.decision_id, run_id=binding.run_id, failed_attempt_id=binding.attempt_id,
        failure_classification_basis="serialized_pre_intent_owner_replacement",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="outward_pre_intent_recovery.v1",
        authorized_next_action=RecoveryActionClass.RETRY_SAME_ATTEMPT_SCOPE,
        resumed_attempt_id=binding.attempt_id,
        required_precondition_refs=[request.digest_ref, previous.journal_entry_id, "dispatch_intent:absent",
                                    f"owner:{previous.owner_id}:fence:{previous.fencing_generation}"],
        blocked_actions=["reuse_previous_owner", "replace_dispatch_intent", "advance_unrelated_turn"],
        rationale_ref=replacement.journal_entry_id,
    )
    action = OperatorActionRecord(
        action_id=request.decision_id, actor_ref=request.operator_ref, input_class=OperatorInputClass.COMMAND,
        command_class=OperatorCommandClass.FORCE_RECONCILE, target_ref=binding.effect_id,
        timestamp=at, precondition_basis_ref=request.digest_ref, result="pre_intent_owner_replaced",
        affected_transition_refs=[previous.journal_entry_id, replacement.journal_entry_id],
        receipt_refs=[f"owner:{replacement.owner_id}:fence:{replacement.fencing_generation}"],
    )
    return decision, action


def validate_recovery_retry(
    request: OutwardEffectRecoveryRequest, binding: OutwardAuthorization, effect: OutwardEffectRecord,
    records: tuple[RecoveryDecisionRecord, OperatorActionRecord],
) -> None:
    decision, action = records
    if (decision.decision_id != request.decision_id or request.digest_ref not in decision.required_precondition_refs
            or action.actor_ref != request.operator_ref or action.precondition_basis_ref != request.digest_ref
            or action.target_ref != binding.effect_id or decision.run_id != binding.run_id):
        raise RuntimeError("E_OUTWARD_RECOVERY_REQUEST_CONFLICT")
    if (effect.recovery_decision_id != request.decision_id or effect.fencing_generation != request.expected_fencing_generation + 1
            or action.receipt_refs != [f"owner:{effect.owner_id}:fence:{effect.fencing_generation}"]):
        raise RuntimeError("E_OUTWARD_RECOVERY_SUPERSEDED")


def validate_recovered_owner(
    binding: OutwardAuthorization, effect: OutwardEffectRecord,
    records: tuple[RecoveryDecisionRecord, OperatorActionRecord] | None, *, claim_entry_id: str,
) -> None:
    if records is None:
        raise RuntimeError("E_OUTWARD_RECOVERY_RECORD_MISSING")
    decision, action = records
    if (decision.decision_id != effect.recovery_decision_id or action.action_id != decision.decision_id
            or decision.run_id != binding.run_id or decision.resumed_attempt_id != binding.attempt_id
            or decision.rationale_ref != claim_entry_id or action.affected_transition_refs[-1:] != [claim_entry_id]
            or action.target_ref != effect.effect_id or action.precondition_basis_ref not in decision.required_precondition_refs
            or action.receipt_refs != [f"owner:{effect.owner_id}:fence:{effect.fencing_generation}"]
            or decision.side_effect_boundary_class is not SideEffectBoundaryClass.PRE_EFFECT_FAILURE
            or decision.authorized_next_action is not RecoveryActionClass.RETRY_SAME_ATTEMPT_SCOPE
            or decision.recovery_policy_ref != "outward_pre_intent_recovery.v1"
            or "dispatch_intent:absent" not in decision.required_precondition_refs
            or action.input_class is not OperatorInputClass.COMMAND
            or action.command_class is not OperatorCommandClass.FORCE_RECONCILE
            or action.result != "pre_intent_owner_replaced"):
        raise RuntimeError("E_OUTWARD_RECOVERY_RECORD_MISMATCH")
