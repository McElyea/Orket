# Layer: contract

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.contracts import CheckpointAcceptanceRecord, CheckpointRecord, EffectJournalEntryRecord
from orket.core.domain import (
    CheckpointAcceptanceOutcome,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ControlPlaneCheckpointError,
    ControlPlaneEffectJournalError,
    ResidualUncertaintyClassification,
    compute_effect_journal_entry_digest,
    create_effect_journal_entry,
    validate_checkpoint_acceptance,
    validate_effect_journal_append,
    validate_effect_journal_chain,
)

pytestmark = pytest.mark.contract


def test_effect_journal_entry_requires_prior_linkage_after_first_entry() -> None:
    with pytest.raises(ValidationError, match="non-initial journal entry requires prior linkage"):
        EffectJournalEntryRecord(
            journal_entry_id="journal-2",
            effect_id="effect-2",
            run_id="run-2",
            attempt_id="attempt-2",
            step_id="step-2",
            authorization_basis_ref="auth-2",
            publication_sequence=2,
            publication_timestamp="2026-03-23T00:02:00+00:00",
            intended_target_ref="resource:sb-2",
            uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
            integrity_verification_ref="integrity-2",
            entry_digest="f" * 64,
        )


def test_create_effect_journal_entry_assigns_digest_checked_sequence_chain() -> None:
    first = create_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        authorization_basis_ref="auth-1",
        publication_timestamp="2026-03-23T00:01:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )
    second = create_effect_journal_entry(
        journal_entry_id="journal-2",
        effect_id="effect-2",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-2",
        authorization_basis_ref="auth-2",
        publication_timestamp="2026-03-23T00:02:00+00:00",
        intended_target_ref="resource:sb-2",
        observed_result_ref=None,
        uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        integrity_verification_ref="integrity-2",
        previous_entry=first,
    )

    assert validate_effect_journal_append(previous_entry=None, entry=first) is True
    ordered = validate_effect_journal_chain([second, first])
    assert [entry.publication_sequence for entry in ordered] == [1, 2]
    assert second.prior_entry_digest == first.entry_digest


def test_validate_effect_journal_append_rejects_tampered_digest() -> None:
    entry = create_effect_journal_entry(
        journal_entry_id="journal-3",
        effect_id="effect-3",
        run_id="run-3",
        attempt_id="attempt-3",
        step_id="step-3",
        authorization_basis_ref="auth-3",
        publication_timestamp="2026-03-23T00:03:00+00:00",
        intended_target_ref="resource:sb-3",
        observed_result_ref="receipt-3",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-3",
    )
    tampered = entry.model_copy(update={"entry_digest": "0" * 64})

    with pytest.raises(ControlPlaneEffectJournalError, match="journal entry digest mismatch"):
        validate_effect_journal_append(previous_entry=None, entry=tampered)


def test_compute_effect_journal_entry_digest_is_stable() -> None:
    entry = create_effect_journal_entry(
        journal_entry_id="journal-4",
        effect_id="effect-4",
        run_id="run-4",
        attempt_id="attempt-4",
        step_id="step-4",
        authorization_basis_ref="auth-4",
        publication_timestamp="2026-03-23T00:04:00+00:00",
        intended_target_ref="resource:sb-4",
        observed_result_ref="receipt-4",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-4",
    )

    assert compute_effect_journal_entry_digest(entry) == entry.entry_digest


def _checkpoint(*, dependent_effect_refs: list[str]) -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id="checkpoint-1",
        parent_ref="attempt-1",
        creation_timestamp="2026-03-23T00:05:00+00:00",
        state_snapshot_ref="snapshot-1",
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        invalidation_conditions=["policy_digest_mismatch"],
        dependent_resource_ids=["resource:sb-1"],
        dependent_effect_refs=dependent_effect_refs,
        policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-checkpoint-1",
    )


def test_checkpoint_acceptance_record_rejects_missing_rejection_reason() -> None:
    with pytest.raises(ValidationError, match="rejected checkpoint requires rejection_reasons"):
        CheckpointAcceptanceRecord(
            acceptance_id="accept-1",
            checkpoint_id="checkpoint-1",
            supervisor_authority_ref="supervisor-1",
            decision_timestamp="2026-03-23T00:06:00+00:00",
            outcome=CheckpointAcceptanceOutcome.REJECTED,
            resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
            required_reobservation_class=CheckpointReobservationClass.FULL,
            evaluated_policy_digest="sha256:policy-1",
            integrity_verification_ref="integrity-checkpoint-1",
        )


def test_validate_checkpoint_acceptance_rejects_policy_digest_mismatch() -> None:
    checkpoint = _checkpoint(dependent_effect_refs=["effect-1"])
    journal_entry = create_effect_journal_entry(
        journal_entry_id="journal-5",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-5",
        authorization_basis_ref="auth-5",
        publication_timestamp="2026-03-23T00:07:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-5",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-5",
    )
    acceptance = CheckpointAcceptanceRecord(
        acceptance_id="accept-2",
        checkpoint_id="checkpoint-1",
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T00:08:00+00:00",
        outcome=CheckpointAcceptanceOutcome.ACCEPTED,
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        evaluated_policy_digest="sha256:policy-mismatch",
        integrity_verification_ref="integrity-checkpoint-1",
        dependent_effect_entry_refs=[journal_entry.journal_entry_id],
        dependent_lease_refs=["lease-1"],
    )

    with pytest.raises(ControlPlaneCheckpointError, match="policy digest mismatch"):
        validate_checkpoint_acceptance(checkpoint, acceptance, journal_entries=[journal_entry], lease_ids={"lease-1"})


def test_validate_checkpoint_acceptance_rejects_missing_effect_journal_coverage() -> None:
    checkpoint = _checkpoint(dependent_effect_refs=["effect-1", "effect-2"])
    journal_entry = create_effect_journal_entry(
        journal_entry_id="journal-6",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-6",
        authorization_basis_ref="auth-6",
        publication_timestamp="2026-03-23T00:09:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-6",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-6",
    )
    acceptance = CheckpointAcceptanceRecord(
        acceptance_id="accept-3",
        checkpoint_id="checkpoint-1",
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T00:10:00+00:00",
        outcome=CheckpointAcceptanceOutcome.ACCEPTED,
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        required_reobservation_class=CheckpointReobservationClass.DEPENDENCY_SCOPE,
        evaluated_policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-checkpoint-1",
        dependent_effect_entry_refs=[journal_entry.journal_entry_id],
    )

    with pytest.raises(ControlPlaneCheckpointError, match="missing effect journal coverage"):
        validate_checkpoint_acceptance(checkpoint, acceptance, journal_entries=[journal_entry])


def test_validate_checkpoint_acceptance_accepts_aligned_dependencies() -> None:
    checkpoint = _checkpoint(dependent_effect_refs=["effect-1"])
    journal_entry = create_effect_journal_entry(
        journal_entry_id="journal-7",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-7",
        authorization_basis_ref="auth-7",
        publication_timestamp="2026-03-23T00:11:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-7",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-7",
    )
    acceptance = CheckpointAcceptanceRecord(
        acceptance_id="accept-4",
        checkpoint_id="checkpoint-1",
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T00:12:00+00:00",
        outcome=CheckpointAcceptanceOutcome.ACCEPTED,
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        evaluated_policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-checkpoint-1",
        dependent_effect_entry_refs=[journal_entry.journal_entry_id],
        dependent_lease_refs=["lease-1"],
    )

    assert (
        validate_checkpoint_acceptance(
            checkpoint,
            acceptance,
            journal_entries=[journal_entry],
            lease_ids={"lease-1"},
        )
        is True
    )
