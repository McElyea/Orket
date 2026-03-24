from __future__ import annotations

from typing import Any


def operator_action_summary(record: Any) -> dict[str, Any]:
    return {
        "action_id": record.action_id,
        "input_class": record.input_class.value,
        "command_class": None if record.command_class is None else record.command_class.value,
        "result": record.result,
        "actor_ref": record.actor_ref,
        "timestamp": record.timestamp,
        "receipt_refs": list(record.receipt_refs),
        "affected_transition_refs": list(record.affected_transition_refs),
        "affected_resource_refs": list(record.affected_resource_refs),
    }


def reservation_summary(record: Any) -> dict[str, Any]:
    return {
        "reservation_id": record.reservation_id,
        "reservation_kind": record.reservation_kind.value,
        "status": record.status.value,
        "holder_ref": record.holder_ref,
        "target_scope_ref": record.target_scope_ref,
        "expiry_or_invalidation_basis": record.expiry_or_invalidation_basis,
        "supervisor_authority_ref": record.supervisor_authority_ref,
        "promotion_rule": record.promotion_rule,
        "promoted_lease_id": record.promoted_lease_id,
    }


def final_truth_summary(record: Any) -> dict[str, Any]:
    return {
        "final_truth_record_id": record.final_truth_record_id,
        "result_class": record.result_class.value,
        "completion_classification": record.completion_classification.value,
        "evidence_sufficiency_classification": record.evidence_sufficiency_classification.value,
        "residual_uncertainty_classification": record.residual_uncertainty_classification.value,
        "degradation_classification": record.degradation_classification.value,
        "closure_basis": record.closure_basis.value,
        "terminality_basis": record.terminality_basis.value,
        "authoritative_result_ref": record.authoritative_result_ref,
        "authority_sources": [source.value for source in record.authority_sources],
    }


async def target_run_summary(*, execution_repository: Any, run_id: str) -> dict[str, Any] | None:
    run = await execution_repository.get_run_record(run_id=run_id)
    if run is None:
        return None
    attempts = await execution_repository.list_attempt_records(run_id=run_id)
    attempt = None
    if run.current_attempt_id is not None:
        attempt = await execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    if attempt is None:
        if attempts:
            attempt = attempts[-1]
    return {
        "run_id": run.run_id,
        "run_state": run.lifecycle_state.value,
        "current_attempt_id": run.current_attempt_id,
        "current_attempt_state": None if attempt is None else attempt.attempt_state.value,
        "final_truth_record_id": run.final_truth_record_id,
        "namespace_scope": run.namespace_scope,
        "admission_decision_receipt_ref": run.admission_decision_receipt_ref,
        "policy_snapshot_id": run.policy_snapshot_id,
        "configuration_snapshot_id": run.configuration_snapshot_id,
        "creation_timestamp": run.creation_timestamp,
        "attempt_count": len(attempts),
    }


async def target_checkpoint_summary(*, repository: Any, attempt_id: str | None) -> dict[str, Any] | None:
    if not attempt_id:
        return None
    checkpoints = await repository.list_checkpoints(parent_ref=attempt_id)
    if not checkpoints:
        return None
    checkpoint = checkpoints[-1]
    acceptance = await repository.get_checkpoint_acceptance(checkpoint_id=checkpoint.checkpoint_id)
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "creation_timestamp": checkpoint.creation_timestamp,
        "state_snapshot_ref": checkpoint.state_snapshot_ref,
        "resumability_class": checkpoint.resumability_class.value,
        "invalidation_conditions": list(checkpoint.invalidation_conditions),
        "dependent_resource_ids": list(checkpoint.dependent_resource_ids),
        "dependent_effect_refs": list(checkpoint.dependent_effect_refs),
        "policy_digest": checkpoint.policy_digest,
        "integrity_verification_ref": checkpoint.integrity_verification_ref,
        "acceptance_outcome": None if acceptance is None else acceptance.outcome.value,
        "acceptance_decision_timestamp": None if acceptance is None else acceptance.decision_timestamp,
        "acceptance_supervisor_authority_ref": None if acceptance is None else acceptance.supervisor_authority_ref,
        "acceptance_evaluated_policy_digest": None if acceptance is None else acceptance.evaluated_policy_digest,
        "required_reobservation_class": None
        if acceptance is None
        else acceptance.required_reobservation_class.value,
        "acceptance_integrity_verification_ref": None
        if acceptance is None
        else acceptance.integrity_verification_ref,
        "acceptance_dependent_effect_entry_refs": None
        if acceptance is None
        else list(acceptance.dependent_effect_entry_refs),
        "acceptance_dependent_reservation_refs": None
        if acceptance is None
        else list(acceptance.dependent_reservation_refs),
        "acceptance_dependent_lease_refs": None
        if acceptance is None
        else list(acceptance.dependent_lease_refs),
        "acceptance_rejection_reasons": None if acceptance is None else list(acceptance.rejection_reasons),
    }


async def target_step_summary(*, execution_repository: Any, attempt_id: str | None) -> dict[str, Any] | None:
    if not attempt_id:
        return None
    steps = await execution_repository.list_step_records(attempt_id=attempt_id)
    if not steps:
        return None
    latest_step = steps[-1]
    return {
        "step_count": len(steps),
        "latest_step_id": latest_step.step_id,
        "latest_step_kind": latest_step.step_kind,
        "latest_namespace_scope": latest_step.namespace_scope,
        "latest_capability_used": None if latest_step.capability_used is None else latest_step.capability_used.value,
        "latest_observed_result_classification": latest_step.observed_result_classification,
        "latest_closure_classification": latest_step.closure_classification,
        "latest_output_ref": latest_step.output_ref,
        "latest_resources_touched": list(latest_step.resources_touched),
        "latest_receipt_refs": list(latest_step.receipt_refs),
    }


async def target_effect_journal_summary(*, repository: Any, run_id: str) -> dict[str, Any] | None:
    entries = await repository.list_effect_journal_entries(run_id=run_id)
    if not entries:
        return None
    latest_entry = entries[-1]
    return {
        "effect_entry_count": len(entries),
        "latest_effect_journal_entry_id": latest_entry.journal_entry_id,
        "latest_effect_id": latest_entry.effect_id,
        "latest_step_id": latest_entry.step_id,
        "latest_publication_sequence": latest_entry.publication_sequence,
        "latest_intended_target_ref": latest_entry.intended_target_ref,
        "latest_observed_result_ref": latest_entry.observed_result_ref,
        "latest_authorization_basis_ref": latest_entry.authorization_basis_ref,
        "latest_publication_timestamp": latest_entry.publication_timestamp,
        "latest_integrity_verification_ref": latest_entry.integrity_verification_ref,
        "latest_prior_journal_entry_id": latest_entry.prior_journal_entry_id,
        "latest_prior_entry_digest": latest_entry.prior_entry_digest,
        "latest_contradictory_entry_refs": list(latest_entry.contradictory_entry_refs),
        "latest_superseding_entry_refs": list(latest_entry.superseding_entry_refs),
        "latest_entry_digest": latest_entry.entry_digest,
        "latest_uncertainty_classification": latest_entry.uncertainty_classification.value,
    }


__all__ = [
    "final_truth_summary",
    "operator_action_summary",
    "reservation_summary",
    "target_checkpoint_summary",
    "target_effect_journal_summary",
    "target_run_summary",
    "target_step_summary",
]
