from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orket.core.domain.control_plane_enums import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    ControlPlaneFailureClass,
    CheckpointResumabilityClass,
    CleanupAuthorityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    DivergenceClass,
    EffectClass,
    EvidenceSufficiencyClassification,
    ExecutionFailureClass,
    FailurePlane,
    IdempotencyClass,
    LeaseStatus,
    OperatorCommandClass,
    OperatorInputClass,
    OrphanClassification,
    OwnershipClass,
    ProtocolFailureClass,
    ReservationKind,
    ReservationStatus,
    RecoveryActionClass,
    ResourceFailureClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SafeContinuationClass,
    SideEffectBoundaryClass,
    TerminalityBasisClassification,
    TruthFailureClass,
)
from orket.core.domain.control_plane_final_truth import terminality_basis_for_closure
from orket.core.domain.control_plane_lifecycle import is_terminal_attempt_state


CONTROL_PLANE_CONTRACT_VERSION_V1 = "control_plane.contract.v1"
CONTROL_PLANE_SNAPSHOT_VERSION_V1 = "control_plane.snapshot.v1"
NonEmptyStr = Annotated[str, Field(min_length=1)]
FailureClassification = (
    ExecutionFailureClass
    | ProtocolFailureClass
    | TruthFailureClass
    | ResourceFailureClass
    | ControlPlaneFailureClass
)


class _ControlPlaneBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_contract_version(self) -> "_ControlPlaneBaseModel":
        if hasattr(self, "contract_version"):
            contract_version = str(getattr(self, "contract_version") or "").strip()
            if contract_version != CONTROL_PLANE_CONTRACT_VERSION_V1:
                raise ValueError(
                    f"unsupported control-plane contract_version={contract_version!r}; "
                    f"expected {CONTROL_PLANE_CONTRACT_VERSION_V1!r}"
                )
        return self


class ResolvedPolicySnapshot(_ControlPlaneBaseModel):
    schema_version: str = CONTROL_PLANE_SNAPSHOT_VERSION_V1
    snapshot_id: NonEmptyStr
    snapshot_digest: NonEmptyStr
    created_at: NonEmptyStr
    source_refs: list[NonEmptyStr] = Field(min_length=1)
    policy_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_schema_version(self) -> "ResolvedPolicySnapshot":
        if self.schema_version != CONTROL_PLANE_SNAPSHOT_VERSION_V1:
            raise ValueError(
                f"unsupported policy snapshot schema_version={self.schema_version!r}; "
                f"expected {CONTROL_PLANE_SNAPSHOT_VERSION_V1!r}"
            )
        return self


class ResolvedConfigurationSnapshot(_ControlPlaneBaseModel):
    schema_version: str = CONTROL_PLANE_SNAPSHOT_VERSION_V1
    snapshot_id: NonEmptyStr
    snapshot_digest: NonEmptyStr
    created_at: NonEmptyStr
    source_refs: list[NonEmptyStr] = Field(min_length=1)
    configuration_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_schema_version(self) -> "ResolvedConfigurationSnapshot":
        if self.schema_version != CONTROL_PLANE_SNAPSHOT_VERSION_V1:
            raise ValueError(
                f"unsupported configuration snapshot schema_version={self.schema_version!r}; "
                f"expected {CONTROL_PLANE_SNAPSHOT_VERSION_V1!r}"
            )
        return self


class WorkloadRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    workload_id: NonEmptyStr
    workload_version: NonEmptyStr
    workload_digest: NonEmptyStr
    declared_capabilities: list[CapabilityClass] = Field(default_factory=list)
    declared_namespace_scopes: list[NonEmptyStr] = Field(default_factory=list)
    declared_resource_classes: list[NonEmptyStr] = Field(default_factory=list)
    declared_degraded_modes: list[NonEmptyStr] = Field(default_factory=list)
    input_contract_ref: NonEmptyStr
    output_contract_ref: NonEmptyStr
    recovery_policy_refs: list[NonEmptyStr] = Field(default_factory=list)
    reconciliation_requirements: list[NonEmptyStr] = Field(default_factory=list)


class RunRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    run_id: NonEmptyStr
    workload_id: NonEmptyStr
    workload_version: NonEmptyStr
    policy_snapshot_id: NonEmptyStr
    policy_digest: NonEmptyStr
    configuration_snapshot_id: NonEmptyStr
    configuration_digest: NonEmptyStr
    creation_timestamp: NonEmptyStr
    admission_decision_receipt_ref: NonEmptyStr
    namespace_scope: NonEmptyStr | None = None
    lifecycle_state: RunState
    current_attempt_id: NonEmptyStr | None = None
    final_truth_record_id: NonEmptyStr | None = None


class AttemptRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    attempt_id: NonEmptyStr
    run_id: NonEmptyStr
    attempt_ordinal: int = Field(ge=1)
    attempt_state: AttemptState
    starting_state_snapshot_ref: NonEmptyStr
    start_timestamp: NonEmptyStr
    end_timestamp: NonEmptyStr | None = None
    side_effect_boundary_class: SideEffectBoundaryClass | None = None
    failure_plane: FailurePlane | None = None
    failure_classification: FailureClassification | None = None
    failure_class: NonEmptyStr | None = None
    recovery_decision_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _validate_attempt_closure(self) -> "AttemptRecord":
        terminal = is_terminal_attempt_state(self.attempt_state)
        if terminal and self.end_timestamp is None:
            raise ValueError("terminal attempt state requires end_timestamp")
        if not terminal and self.end_timestamp is not None:
            raise ValueError("non-terminal attempt state cannot carry end_timestamp")
        if self.side_effect_boundary_class is not None and self.attempt_state not in {
            AttemptState.FAILED,
            AttemptState.INTERRUPTED,
        }:
            raise ValueError("side_effect_boundary_class is only valid for failed or interrupted attempts")
        if self.recovery_decision_id is not None and self.attempt_state not in {
            AttemptState.FAILED,
            AttemptState.INTERRUPTED,
        }:
            raise ValueError("recovery_decision_id is only valid for failed or interrupted attempts")
        if (self.failure_plane is None) != (self.failure_classification is None):
            raise ValueError("failure_plane and failure_classification must be set together")
        if self.failure_classification is not None and self.attempt_state not in {
            AttemptState.FAILED,
            AttemptState.INTERRUPTED,
        }:
            raise ValueError("failure_classification is only valid for failed or interrupted attempts")
        return self


class StepRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    step_id: NonEmptyStr
    attempt_id: NonEmptyStr
    step_kind: NonEmptyStr
    namespace_scope: NonEmptyStr | None = None
    input_ref: NonEmptyStr
    output_ref: NonEmptyStr | None = None
    capability_used: CapabilityClass | None = None
    resources_touched: list[NonEmptyStr] = Field(default_factory=list)
    observed_result_classification: NonEmptyStr
    receipt_refs: list[NonEmptyStr] = Field(default_factory=list)
    closure_classification: NonEmptyStr


class EffectRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    effect_id: NonEmptyStr
    step_id: NonEmptyStr
    effect_class: EffectClass
    capability_class: CapabilityClass
    intended_target_ref: NonEmptyStr
    idempotency_class: IdempotencyClass
    preconditions_ref: NonEmptyStr
    authorization_basis_ref: NonEmptyStr
    observed_result_ref: NonEmptyStr | None = None
    uncertainty_classification: NonEmptyStr


class ResourceRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    resource_id: NonEmptyStr
    resource_kind: NonEmptyStr
    namespace_scope: NonEmptyStr
    ownership_class: OwnershipClass
    current_observed_state: NonEmptyStr
    last_observed_timestamp: NonEmptyStr
    cleanup_authority_class: CleanupAuthorityClass
    provenance_ref: NonEmptyStr
    reconciliation_status: NonEmptyStr
    orphan_classification: OrphanClassification = OrphanClassification.NOT_ORPHANED


class ReservationRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    reservation_id: NonEmptyStr
    holder_ref: NonEmptyStr
    reservation_kind: ReservationKind
    target_scope_ref: NonEmptyStr
    creation_timestamp: NonEmptyStr
    expiry_or_invalidation_basis: NonEmptyStr
    status: ReservationStatus
    promotion_rule: NonEmptyStr | None = None
    promoted_lease_id: NonEmptyStr | None = None
    supervisor_authority_ref: NonEmptyStr
    history_refs: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_promotion_fields(self) -> "ReservationRecord":
        if self.status is ReservationStatus.PROMOTED_TO_LEASE and self.promoted_lease_id is None:
            raise ValueError("promoted reservation requires promoted_lease_id")
        if self.status is not ReservationStatus.PROMOTED_TO_LEASE and self.promoted_lease_id is not None:
            raise ValueError("promoted_lease_id is only valid for promoted reservations")
        return self


class LeaseRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    lease_id: NonEmptyStr
    resource_id: NonEmptyStr
    holder_ref: NonEmptyStr
    lease_epoch: int = Field(ge=0)
    granted_timestamp: NonEmptyStr
    publication_timestamp: NonEmptyStr
    expiry_basis: NonEmptyStr
    status: LeaseStatus
    last_confirmed_observation: NonEmptyStr | None = None
    source_reservation_id: NonEmptyStr | None = None
    cleanup_eligibility_rule: NonEmptyStr
    history_refs: list[NonEmptyStr] = Field(default_factory=list)


class CheckpointRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    checkpoint_id: NonEmptyStr
    parent_ref: NonEmptyStr
    creation_timestamp: NonEmptyStr
    state_snapshot_ref: NonEmptyStr
    resumability_class: CheckpointResumabilityClass
    invalidation_conditions: list[NonEmptyStr] = Field(default_factory=list)
    dependent_resource_ids: list[NonEmptyStr] = Field(default_factory=list)
    dependent_effect_refs: list[NonEmptyStr] = Field(default_factory=list)
    policy_digest: NonEmptyStr
    integrity_verification_ref: NonEmptyStr


class RecoveryDecisionRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    decision_id: NonEmptyStr
    run_id: NonEmptyStr
    failed_attempt_id: NonEmptyStr
    failure_classification_basis: NonEmptyStr
    failure_plane: FailurePlane | None = None
    failure_classification: FailureClassification | None = None
    side_effect_boundary_class: SideEffectBoundaryClass
    recovery_policy_ref: NonEmptyStr
    authorized_next_action: RecoveryActionClass
    resumed_attempt_id: NonEmptyStr | None = None
    new_attempt_id: NonEmptyStr | None = None
    target_checkpoint_id: NonEmptyStr | None = None
    required_precondition_refs: list[NonEmptyStr] = Field(default_factory=list)
    blocked_actions: list[NonEmptyStr] = Field(default_factory=list)
    operator_requirement: OperatorCommandClass | None = None
    rationale_ref: NonEmptyStr

    @model_validator(mode="after")
    def _validate_execution_target(self) -> "RecoveryDecisionRecord":
        if self.resumed_attempt_id and self.new_attempt_id:
            raise ValueError("recovery decision cannot both resume an attempt and start a new attempt")
        if (self.failure_plane is None) != (self.failure_classification is None):
            raise ValueError("failure_plane and failure_classification must be set together")
        return self


class ReconciliationRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    reconciliation_id: NonEmptyStr
    target_ref: NonEmptyStr
    comparison_scope: NonEmptyStr
    observed_refs: list[NonEmptyStr] = Field(default_factory=list)
    intended_refs: list[NonEmptyStr] = Field(default_factory=list)
    divergence_class: DivergenceClass
    residual_uncertainty_classification: ResidualUncertaintyClassification
    publication_timestamp: NonEmptyStr
    safe_continuation_class: SafeContinuationClass
    operator_requirement: OperatorCommandClass | None = None


class OperatorActionRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    action_id: NonEmptyStr
    actor_ref: NonEmptyStr
    input_class: OperatorInputClass
    target_ref: NonEmptyStr
    timestamp: NonEmptyStr
    precondition_basis_ref: NonEmptyStr
    result: NonEmptyStr
    command_class: OperatorCommandClass | None = None
    risk_acceptance_scope: NonEmptyStr | None = None
    attestation_scope: NonEmptyStr | None = None
    attestation_payload: dict[str, Any] = Field(default_factory=dict)
    affected_transition_refs: list[NonEmptyStr] = Field(default_factory=list)
    affected_resource_refs: list[NonEmptyStr] = Field(default_factory=list)
    receipt_refs: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_input_shape(self) -> "OperatorActionRecord":
        if self.input_class is OperatorInputClass.COMMAND:
            if self.command_class is None:
                raise ValueError("operator command input requires command_class")
            if self.risk_acceptance_scope is not None or self.attestation_scope is not None:
                raise ValueError("operator command input cannot carry risk acceptance or attestation scope")
        if self.input_class is OperatorInputClass.RISK_ACCEPTANCE:
            if self.command_class is not None:
                raise ValueError("operator risk acceptance must not carry command_class")
            if self.risk_acceptance_scope is None:
                raise ValueError("operator risk acceptance requires risk_acceptance_scope")
        if self.input_class is OperatorInputClass.ATTESTATION:
            if self.command_class is not None:
                raise ValueError("operator attestation must not carry command_class")
            if self.attestation_scope is None:
                raise ValueError("operator attestation requires attestation_scope")
        return self


class FinalTruthRecord(_ControlPlaneBaseModel):
    contract_version: str = CONTROL_PLANE_CONTRACT_VERSION_V1
    final_truth_record_id: NonEmptyStr
    run_id: NonEmptyStr
    result_class: ResultClass
    completion_classification: CompletionClassification
    evidence_sufficiency_classification: EvidenceSufficiencyClassification
    residual_uncertainty_classification: ResidualUncertaintyClassification
    degradation_classification: DegradationClassification
    closure_basis: ClosureBasisClassification
    terminality_basis: TerminalityBasisClassification
    authority_sources: list[AuthoritySourceClass] = Field(min_length=1)
    authoritative_result_ref: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _validate_truth_constraints(self) -> "FinalTruthRecord":
        if self.result_class is ResultClass.SUCCESS and (
            self.evidence_sufficiency_classification is not EvidenceSufficiencyClassification.SUFFICIENT
        ):
            raise ValueError("success result_class requires evidence_sufficient")
        expected_terminality = terminality_basis_for_closure(self.closure_basis)
        if self.terminality_basis is not expected_terminality:
            raise ValueError("terminality_basis must match closure_basis")
        if (
            self.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
            and AuthoritySourceClass.RECONCILIATION_RECORD not in self.authority_sources
        ):
            raise ValueError("reconciliation_closed requires reconciliation_record authority source")
        if self.evidence_sufficiency_classification is EvidenceSufficiencyClassification.ATTESTED:
            if AuthoritySourceClass.OPERATOR_ATTESTATION not in self.authority_sources:
                raise ValueError("evidence_attested requires operator_attestation authority source")
            if self.result_class is ResultClass.SUCCESS:
                raise ValueError("attested evidence cannot publish success result_class")
        return self


__all__ = [
    "CONTROL_PLANE_CONTRACT_VERSION_V1",
    "CONTROL_PLANE_SNAPSHOT_VERSION_V1",
    "AttemptRecord",
    "CheckpointRecord",
    "EffectRecord",
    "FinalTruthRecord",
    "LeaseRecord",
    "OperatorActionRecord",
    "ReconciliationRecord",
    "RecoveryDecisionRecord",
    "ReservationRecord",
    "ResolvedConfigurationSnapshot",
    "ResolvedPolicySnapshot",
    "ResourceRecord",
    "RunRecord",
    "StepRecord",
    "WorkloadRecord",
]
