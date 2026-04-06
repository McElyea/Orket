from __future__ import annotations

from pydantic import Field, model_validator

from orket.core.contracts.control_plane_models import (
    CONTROL_PLANE_CONTRACT_VERSION_V1,
    NonEmptyStr,
    _ControlPlaneBaseModel,
)
from orket.core.domain.control_plane_enums import (
    CheckpointAcceptanceOutcome,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ResidualUncertaintyClassification,
)


class EffectJournalEntryRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    journal_entry_id: NonEmptyStr
    effect_id: NonEmptyStr
    run_id: NonEmptyStr
    attempt_id: NonEmptyStr
    step_id: NonEmptyStr
    authorization_basis_ref: NonEmptyStr
    publication_sequence: int = Field(ge=1)
    publication_timestamp: NonEmptyStr
    intended_target_ref: NonEmptyStr
    observed_result_ref: NonEmptyStr | None = None
    uncertainty_classification: ResidualUncertaintyClassification
    integrity_verification_ref: NonEmptyStr
    prior_journal_entry_id: NonEmptyStr | None = None
    prior_entry_digest: NonEmptyStr | None = None
    contradictory_entry_refs: list[NonEmptyStr] = Field(default_factory=list)
    superseding_entry_refs: list[NonEmptyStr] = Field(default_factory=list)
    entry_digest: NonEmptyStr

    @model_validator(mode="after")
    def _validate_journal_shape(self) -> EffectJournalEntryRecord:
        if self.publication_sequence == 1 and (
            self.prior_journal_entry_id is not None or self.prior_entry_digest is not None
        ):
            raise ValueError("first journal entry cannot declare prior linkage")
        if self.publication_sequence > 1 and (
            self.prior_journal_entry_id is None or self.prior_entry_digest is None
        ):
            raise ValueError("non-initial journal entry requires prior linkage")
        if (
            self.uncertainty_classification is ResidualUncertaintyClassification.NONE
            and self.observed_result_ref is None
        ):
            raise ValueError("journal entry without residual uncertainty requires observed_result_ref")
        if self.journal_entry_id in self.contradictory_entry_refs or self.journal_entry_id in self.superseding_entry_refs:
            raise ValueError("journal entry cannot reference itself")
        if set(self.contradictory_entry_refs).intersection(self.superseding_entry_refs):
            raise ValueError("journal entry refs cannot be both contradictory and superseding")
        return self


class CheckpointAcceptanceRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    acceptance_id: NonEmptyStr
    checkpoint_id: NonEmptyStr
    supervisor_authority_ref: NonEmptyStr
    decision_timestamp: NonEmptyStr
    outcome: CheckpointAcceptanceOutcome
    resumability_class: CheckpointResumabilityClass
    required_reobservation_class: CheckpointReobservationClass
    evaluated_policy_digest: NonEmptyStr
    integrity_verification_ref: NonEmptyStr
    dependent_effect_entry_refs: list[NonEmptyStr] = Field(default_factory=list)
    dependent_reservation_refs: list[NonEmptyStr] = Field(default_factory=list)
    dependent_lease_refs: list[NonEmptyStr] = Field(default_factory=list)
    rejection_reasons: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_acceptance_shape(self) -> CheckpointAcceptanceRecord:
        if self.outcome is CheckpointAcceptanceOutcome.ACCEPTED and self.rejection_reasons:
            raise ValueError("accepted checkpoint cannot carry rejection_reasons")
        if self.outcome is CheckpointAcceptanceOutcome.REJECTED:
            if not self.rejection_reasons:
                raise ValueError("rejected checkpoint requires rejection_reasons")
            if self.resumability_class is not CheckpointResumabilityClass.RESUME_FORBIDDEN:
                raise ValueError("rejected checkpoint must publish resume_forbidden")
        return self


__all__ = [
    "CheckpointAcceptanceRecord",
    "EffectJournalEntryRecord",
]
