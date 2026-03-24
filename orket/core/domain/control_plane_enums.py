from __future__ import annotations

from enum import Enum


class RunState(str, Enum):
    CREATED = "created"
    ADMISSION_PENDING = "admission_pending"
    ADMITTED = "admitted"
    EXECUTING = "executing"
    WAITING_ON_OBSERVATION = "waiting_on_observation"
    WAITING_ON_RESOURCE = "waiting_on_resource"
    RECOVERY_PENDING = "recovery_pending"
    RECONCILING = "reconciling"
    RECOVERING = "recovering"
    OPERATOR_BLOCKED = "operator_blocked"
    QUARANTINED = "quarantined"
    COMPLETED = "completed"
    FAILED_TERMINAL = "failed_terminal"
    CANCELLED = "cancelled"


class AttemptState(str, Enum):
    CREATED = "attempt_created"
    EXECUTING = "attempt_executing"
    WAITING = "attempt_waiting"
    FAILED = "attempt_failed"
    INTERRUPTED = "attempt_interrupted"
    COMPLETED = "attempt_completed"
    ABANDONED = "attempt_abandoned"


class FailurePlane(str, Enum):
    EXECUTION = "execution_failure"
    PROTOCOL = "protocol_failure"
    TRUTH = "truth_failure"
    RESOURCE = "resource_failure"
    CONTROL_PLANE = "control_plane_failure"


class ExecutionFailureClass(str, Enum):
    ADAPTER_EXECUTION_FAILURE = "adapter_execution_failure"
    TOOL_TIMEOUT = "tool_timeout"
    TRANSPORT_FAILURE = "transport_failure"
    DETERMINISTIC_TRANSFORM_FAILURE = "deterministic_transform_failure"
    CHECKPOINT_INVALID = "checkpoint_invalid"
    RESUME_FAILURE = "resume_failure"


class ProtocolFailureClass(str, Enum):
    INVALID_ENVELOPE = "invalid_envelope"
    INVALID_SCHEMA = "invalid_schema"
    TOOL_CARDINALITY_VIOLATION = "tool_cardinality_violation"
    FORBIDDEN_MIXED_SURFACE = "forbidden_mixed_surface"
    MISSING_REQUIRED_OBSERVATION = "missing_required_observation"
    UNDECLARED_CAPABILITY_REQUEST = "undeclared_capability_request"


class TruthFailureClass(str, Enum):
    UNSUPPORTED_CLAIM = "unsupported_claim"
    MISSING_REQUIRED_EVIDENCE = "missing_required_evidence"
    TOOL_RESULT_CONTRADICTION = "tool_result_contradiction"
    STATE_CONTRADICTION = "state_contradiction"
    CLAIM_EXCEEDS_AUTHORITY = "claim_exceeds_authority"
    FALSE_COMPLETION_CLAIM = "false_completion_claim"


class ResourceFailureClass(str, Enum):
    LEASE_CONFLICT = "lease_conflict"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    RESOURCE_STATE_UNCERTAIN = "resource_state_uncertain"
    ORPHAN_RESOURCE_DETECTED = "orphan_resource_detected"
    CLEANUP_AUTHORITY_BLOCKED = "cleanup_authority_blocked"
    RESERVATION_CONFLICT = "reservation_conflict"
    RESERVATION_EXPIRED_BEFORE_EXECUTION = "reservation_expired_before_execution"


class ControlPlaneFailureClass(str, Enum):
    ILLEGAL_STATE_TRANSITION = "illegal_state_transition"
    JOURNAL_INTEGRITY_FAILURE = "journal_integrity_failure"
    MISSING_REQUIRED_RECEIPT = "missing_required_receipt"
    SUPERVISORY_INVARIANT_VIOLATION = "supervisory_invariant_violation"
    RECONCILIATION_PUBLICATION_FAILURE = "reconciliation_publication_failure"
    FINAL_TRUTH_PUBLICATION_FAILURE = "final_truth_publication_failure"


class SideEffectBoundaryClass(str, Enum):
    PRE_EFFECT_FAILURE = "pre_effect_failure"
    EFFECT_BOUNDARY_UNCERTAIN = "effect_boundary_uncertain"
    POST_EFFECT_OBSERVED = "post_effect_observed"


class RecoveryActionClass(str, Enum):
    RETRY_SAME_ATTEMPT_SCOPE = "retry_same_attempt_scope"
    START_NEW_ATTEMPT = "start_new_attempt"
    RESUME_FROM_CHECKPOINT = "resume_from_checkpoint"
    REQUIRE_OBSERVATION_THEN_CONTINUE = "require_observation_then_continue"
    REQUIRE_RECONCILIATION_THEN_DECIDE = "require_reconciliation_then_decide"
    PERFORM_CONTROL_PLANE_RECOVERY_ACTION = "perform_control_plane_recovery_action"
    DOWNGRADE_TO_DEGRADED_MODE = "downgrade_to_degraded_mode"
    QUARANTINE_RUN = "quarantine_run"
    ESCALATE_TO_OPERATOR = "escalate_to_operator"
    TERMINATE_RUN = "terminate_run"


class CapabilityClass(str, Enum):
    OBSERVE = "observe"
    DETERMINISTIC_COMPUTE = "deterministic_compute"
    BOUNDED_LOCAL_MUTATION = "bounded_local_mutation"
    EXTERNAL_MUTATION = "external_mutation"
    DESTRUCTIVE_MUTATION = "destructive_mutation"
    OPERATOR_AUTHORIZED_ACTION = "operator_authorized_action"


class EffectClass(str, Enum):
    NO_EFFECT = "no_effect"
    LOCAL_STATE_EFFECT = "local_state_effect"
    ARTIFACT_EFFECT = "artifact_effect"
    RESOURCE_LIFECYCLE_EFFECT = "resource_lifecycle_effect"
    EXTERNAL_SERVICE_EFFECT = "external_service_effect"
    DESTRUCTIVE_EFFECT = "destructive_effect"


class IdempotencyClass(str, Enum):
    IDEMPOTENT = "idempotent"
    IDEMPOTENT_WITH_TOKEN = "idempotent_with_token"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN_IDEMPOTENCY = "unknown_idempotency"


class CompensationClass(str, Enum):
    NO_COMPENSATION_NEEDED = "no_compensation_needed"
    RUNTIME_COMPENSABLE = "runtime_compensable"
    ADAPTER_COMPENSABLE = "adapter_compensable"
    OPERATOR_COMPENSABLE = "operator_compensable"
    NON_COMPENSABLE = "non_compensable"
    UNKNOWN_COMPENSATION = "unknown_compensation"


class EvidenceContractClass(str, Enum):
    RECEIPT_ONLY = "receipt_only"
    RECEIPT_PLUS_OBSERVATION = "receipt_plus_observation"
    OBSERVATION_ONLY = "observation_only"
    ARTIFACT_MANIFEST_REQUIRED = "artifact_manifest_required"
    EXTERNAL_CONFIRMATION_REQUIRED = "external_confirmation_required"
    ATTESTATION_PERMITTED_BY_POLICY = "attestation_permitted_by_policy"


class ObservabilityClass(str, Enum):
    FULLY_OBSERVABLE = "fully_observable"
    EVENTUALLY_OBSERVABLE = "eventually_observable"
    PARTIALLY_OBSERVABLE = "partially_observable"
    OPAQUE_WITHOUT_EXTERNAL_CHECK = "opaque_without_external_check"


class ReservationKind(str, Enum):
    RESOURCE = "resource_reservation"
    CONCURRENCY = "concurrency_reservation"
    NAMESPACE = "namespace_reservation"
    OPERATOR_HOLD = "operator_hold_reservation"


class ReservationStatus(str, Enum):
    PENDING = "reservation_pending"
    ACTIVE = "reservation_active"
    PROMOTED_TO_LEASE = "reservation_promoted_to_lease"
    RELEASED = "reservation_released"
    EXPIRED = "reservation_expired"
    CANCELLED = "reservation_cancelled"
    INVALIDATED = "reservation_invalidated"
    UNCERTAIN = "reservation_uncertain"


class LeaseStatus(str, Enum):
    PENDING = "lease_pending"
    ACTIVE = "lease_active"
    EXPIRED = "lease_expired"
    RELEASED = "lease_released"
    REVOKED = "lease_revoked"
    UNCERTAIN = "lease_uncertain"


class CleanupAuthorityClass(str, Enum):
    RUNTIME_CLEANUP_ALLOWED = "runtime_cleanup_allowed"
    RUNTIME_CLEANUP_AFTER_RECONCILIATION = "runtime_cleanup_after_reconciliation"
    OPERATOR_CLEANUP_REQUIRED = "operator_cleanup_required"
    ADAPTER_CLEANUP_ONLY = "adapter_cleanup_only"
    CLEANUP_FORBIDDEN_WITHOUT_EXTERNAL_CONFIRMATION = "cleanup_forbidden_without_external_confirmation"


class OwnershipClass(str, Enum):
    RUN_OWNED = "run_owned"
    ATTEMPT_OWNED = "attempt_owned"
    SHARED_GOVERNED = "shared_governed"
    OPERATOR_OWNED = "operator_owned"
    EXTERNAL_UNOWNED_REFERENCE = "external_unowned_reference"


class OrphanClassification(str, Enum):
    NOT_ORPHANED = "not_orphaned"
    VERIFIED_ORPHAN = "verified_orphan"
    SUSPECTED_ORPHAN = "suspected_orphan"
    OWNERSHIP_CONFLICT = "ownership_conflict"


class DivergenceClass(str, Enum):
    NO_DIVERGENCE = "no_divergence"
    EXPECTED_EFFECT_OBSERVED = "expected_effect_observed"
    EFFECT_MISSING = "effect_missing"
    UNEXPECTED_EFFECT_OBSERVED = "unexpected_effect_observed"
    RESOURCE_STATE_DIVERGED = "resource_state_diverged"
    OWNERSHIP_DIVERGED = "ownership_diverged"
    INSUFFICIENT_OBSERVATION = "insufficient_observation"


class SafeContinuationClass(str, Enum):
    SAFE_TO_CONTINUE = "safe_to_continue"
    SAFE_TO_CONTINUE_IN_DEGRADED_MODE = "safe_to_continue_in_degraded_mode"
    OPERATOR_REQUIRED = "operator_required"
    UNSAFE_TO_CONTINUE = "unsafe_to_continue"
    TERMINAL_WITHOUT_CLEANUP = "terminal_without_cleanup"
    CLEANUP_BEFORE_CONTINUE = "cleanup_before_continue"


class OperatorInputClass(str, Enum):
    COMMAND = "operator_command"
    RISK_ACCEPTANCE = "operator_risk_acceptance"
    ATTESTATION = "operator_attestation"


class OperatorCommandClass(str, Enum):
    APPROVE_CONTINUE = "approve_continue"
    APPROVE_DEGRADED_CONTINUE = "approve_degraded_continue"
    FORCE_RECONCILE = "force_reconcile"
    QUARANTINE_RUN = "quarantine_run"
    CANCEL_RUN = "cancel_run"
    RELEASE_OR_REVOKE_LEASE = "release_or_revoke_lease"
    APPROVE_CLEANUP = "approve_cleanup"
    MARK_TERMINAL = "mark_terminal"


class CheckpointAcceptanceOutcome(str, Enum):
    ACCEPTED = "checkpoint_accepted"
    REJECTED = "checkpoint_rejected"


class CheckpointReobservationClass(str, Enum):
    NONE = "no_reobservation_required"
    TARGET_ONLY = "target_reobservation_required"
    DEPENDENCY_SCOPE = "dependency_reobservation_required"
    FULL = "full_reobservation_required"


class CheckpointResumabilityClass(str, Enum):
    RESUME_SAME_ATTEMPT = "resume_same_attempt"
    RESUME_NEW_ATTEMPT_FROM_CHECKPOINT = "resume_new_attempt_from_checkpoint"
    RESUME_FORBIDDEN = "resume_forbidden"


class ResultClass(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    ADVISORY = "advisory"


class CompletionClassification(str, Enum):
    SATISFIED = "completion_satisfied"
    PARTIAL = "completion_partial"
    UNSATISFIED = "completion_unsatisfied"


class EvidenceSufficiencyClassification(str, Enum):
    SUFFICIENT = "evidence_sufficient"
    ATTESTED = "evidence_attested"
    INSUFFICIENT = "evidence_insufficient"


class ResidualUncertaintyClassification(str, Enum):
    NONE = "no_residual_uncertainty"
    BOUNDED = "bounded_residual_uncertainty"
    UNRESOLVED = "unresolved_residual_uncertainty"


class DegradationClassification(str, Enum):
    NONE = "no_degradation"
    DECLARED = "declared_degradation"
    OPERATOR_APPROVED = "operator_approved_degradation"


class ClosureBasisClassification(str, Enum):
    NORMAL_EXECUTION = "normal_execution"
    RECONCILIATION_CLOSED = "reconciliation_closed"
    POLICY_TERMINAL_STOP = "policy_terminal_stop"
    OPERATOR_TERMINAL_STOP = "operator_terminal_stop"
    CANCELLED_BY_AUTHORITY = "cancelled_by_authority"


class TerminalityBasisClassification(str, Enum):
    COMPLETED_TERMINAL = "completed_terminal"
    POLICY_TERMINAL = "policy_terminal"
    OPERATOR_TERMINAL = "operator_terminal"
    CANCELLED_TERMINAL = "cancelled_terminal"


class AuthoritySourceClass(str, Enum):
    RECEIPT_EVIDENCE = "receipt_evidence"
    ADAPTER_OBSERVATION = "adapter_observation"
    RECONCILIATION_RECORD = "reconciliation_record"
    LEASE_RECORD = "lease_record"
    VALIDATED_ARTIFACT = "validated_artifact"
    OPERATOR_ATTESTATION = "operator_attestation"


__all__ = [
    "AttemptState",
    "AuthoritySourceClass",
    "CapabilityClass",
    "CheckpointAcceptanceOutcome",
    "CheckpointReobservationClass",
    "CheckpointResumabilityClass",
    "CleanupAuthorityClass",
    "ClosureBasisClassification",
    "CompensationClass",
    "CompletionClassification",
    "ControlPlaneFailureClass",
    "DegradationClassification",
    "DivergenceClass",
    "EffectClass",
    "EvidenceContractClass",
    "EvidenceSufficiencyClassification",
    "ExecutionFailureClass",
    "FailurePlane",
    "IdempotencyClass",
    "LeaseStatus",
    "ObservabilityClass",
    "OperatorCommandClass",
    "OperatorInputClass",
    "OrphanClassification",
    "OwnershipClass",
    "ProtocolFailureClass",
    "ReservationKind",
    "ReservationStatus",
    "RecoveryActionClass",
    "ResidualUncertaintyClassification",
    "ResultClass",
    "RunState",
    "SafeContinuationClass",
    "SideEffectBoundaryClass",
    "TerminalityBasisClassification",
    "TruthFailureClass",
    "ResourceFailureClass",
]
