"""Read and validate a retained terminal projection inside its owner's transaction."""
from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import AttemptRecord, EffectJournalEntryRecord, FinalTruthRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import ResidualUncertaintyClassification
from orket.core.domain.control_plane_final_truth import (
    ControlPlaneFinalTruthError,
    validate_terminal_record_consistency,
)


async def read_terminal_truth(
    execution: ControlPlaneExecutionRepository, publication: ControlPlanePublicationService, run: RunRecord,
) -> tuple[AttemptRecord, FinalTruthRecord | None]:
    attempt = await execution.get_attempt_record(attempt_id=run.current_attempt_id)
    if attempt is None or attempt.run_id != run.run_id or attempt.attempt_id != run.current_attempt_id:
        raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:attempt_identity")
    truth = await publication.repository.get_final_truth(run_id=run.run_id)
    validate_terminal_record_consistency(run, attempt, truth)
    return attempt, truth


async def require_closeout_evidence(
    execution: ControlPlaneExecutionRepository, publication: ControlPlanePublicationService, *,
    run: RunRecord, expected_step: StepRecord, truth: FinalTruthRecord, expected_truth: FinalTruthRecord,
    journal_entry_id: str, effect_id: str, target_ref: str,
) -> tuple[StepRecord, EffectJournalEntryRecord]:
    step = await execution.get_step_record(step_id=expected_step.step_id)
    entries = await publication.repository.list_effect_journal_entries(run_id=run.run_id)
    publication.authority.validate_effect_journal_history(entries)
    matches = [entry for entry in entries if entry.step_id == expected_step.step_id
               or entry.effect_id == effect_id or entry.journal_entry_id == journal_entry_id]
    if (truth != expected_truth or step is None
            or step.model_dump(exclude={"state_revision"}) != expected_step.model_dump(exclude={"state_revision"})
            or len(matches) != 1):
        raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:closeout_evidence")
    effect = matches[0]
    if (effect.journal_entry_id != journal_entry_id or effect.effect_id != effect_id
            or effect.run_id != run.run_id or effect.attempt_id != step.attempt_id
            or effect.step_id != step.step_id or effect.intended_target_ref != target_ref
            or effect.observed_result_ref != step.output_ref or effect.integrity_verification_ref != step.output_ref
            or effect.authorization_basis_ref != run.admission_decision_receipt_ref
            or effect.uncertainty_classification is not ResidualUncertaintyClassification.NONE):
        raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:closeout_effect")
    return step, effect
