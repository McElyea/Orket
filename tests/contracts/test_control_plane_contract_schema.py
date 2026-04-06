# Layer: contract

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.contracts import (
    CONTROL_PLANE_SNAPSHOT_VERSION_V1,
    AttemptRecord,
    FinalTruthRecord,
    LeaseRecord,
    OperatorActionRecord,
    RecoveryDecisionRecord,
    ReservationRecord,
    ResolvedConfigurationSnapshot,
    ResolvedPolicySnapshot,
    RunRecord,
)
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ExecutionFailureClass,
    FailurePlane,
    OperatorCommandClass,
    OperatorInputClass,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    TerminalityBasisClassification,
)

pytestmark = pytest.mark.contract


def test_run_record_schema_exposes_required_fields() -> None:
    required = set(RunRecord.model_json_schema().get("required", []))
    assert {
        "run_id",
        "workload_id",
        "workload_version",
        "policy_snapshot_id",
        "policy_digest",
        "configuration_snapshot_id",
        "configuration_digest",
        "creation_timestamp",
        "admission_decision_receipt_ref",
        "lifecycle_state",
    }.issubset(required)


def test_run_record_rejects_unsupported_contract_version() -> None:
    with pytest.raises(ValidationError, match="unsupported control-plane contract_version"):
        RunRecord(
            contract_version="control_plane.contract.v0",
            run_id="run-unsupported-version",
            workload_id="workload-1",
            workload_version="2026-03-25",
            policy_snapshot_id="policy-unsupported-version",
            policy_digest="sha256:policy-unsupported-version",
            configuration_snapshot_id="config-unsupported-version",
            configuration_digest="sha256:config-unsupported-version",
            creation_timestamp="2026-03-25T00:00:00+00:00",
            admission_decision_receipt_ref="admission-unsupported-version",
            lifecycle_state=RunState.CREATED,
        )


def test_reservation_record_rejects_unsupported_contract_version() -> None:
    with pytest.raises(ValidationError, match="unsupported control-plane contract_version"):
        ReservationRecord(
            contract_version="control_plane.contract.v0",
            reservation_id="reservation-unsupported-version",
            holder_ref="holder-unsupported-version",
            reservation_kind="concurrency_reservation",
            target_scope_ref="resource:unsupported-version",
            creation_timestamp="2026-03-25T00:00:00+00:00",
            expiry_or_invalidation_basis="unsupported-version-test",
            status="reservation_active",
            supervisor_authority_ref="supervisor:unsupported-version",
        )


def test_final_truth_record_rejects_unsupported_contract_version() -> None:
    with pytest.raises(ValidationError, match="unsupported control-plane contract_version"):
        FinalTruthRecord(
            contract_version="control_plane.contract.v0",
            final_truth_record_id="truth-unsupported-version",
            run_id="run-unsupported-version",
            result_class=ResultClass.BLOCKED,
            completion_classification=CompletionClassification.UNSATISFIED,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=ClosureBasisClassification.POLICY_TERMINAL_STOP,
            terminality_basis=TerminalityBasisClassification.POLICY_TERMINAL,
            authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        )


def test_resolved_policy_snapshot_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError, match="unsupported policy snapshot schema_version"):
        ResolvedPolicySnapshot(
            schema_version="control_plane.snapshot.v0",
            snapshot_id="policy-1",
            snapshot_digest="sha256:policy",
            created_at="2026-03-23T00:00:00+00:00",
            source_refs=["docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md"],
            policy_payload={"mode": "strict"},
        )


def test_resolved_policy_snapshot_accepts_current_schema_version() -> None:
    snapshot = ResolvedPolicySnapshot(
        schema_version=CONTROL_PLANE_SNAPSHOT_VERSION_V1,
        snapshot_id="policy-2",
        snapshot_digest="sha256:policy-2",
        created_at="2026-03-23T00:00:00+00:00",
        source_refs=["docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md"],
        policy_payload={"mode": "strict"},
    )

    assert snapshot.schema_version == CONTROL_PLANE_SNAPSHOT_VERSION_V1


def test_resolved_configuration_snapshot_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError, match="unsupported configuration snapshot schema_version"):
        ResolvedConfigurationSnapshot(
            schema_version="control_plane.snapshot.v0",
            snapshot_id="config-1",
            snapshot_digest="sha256:config",
            created_at="2026-03-25T00:00:00+00:00",
            source_refs=["kernel-admission-decision:test"],
            configuration_payload={"session_id": "sess-1"},
        )


def test_operator_command_requires_command_class() -> None:
    with pytest.raises(ValidationError, match="operator command input requires command_class"):
        OperatorActionRecord(
            action_id="op-1",
            actor_ref="jon",
            input_class=OperatorInputClass.COMMAND,
            target_ref="run-1",
            timestamp="2026-03-23T00:00:00+00:00",
            precondition_basis_ref="receipt-1",
            result="accepted",
        )


def test_operator_risk_acceptance_rejects_command_class() -> None:
    with pytest.raises(ValidationError, match="operator risk acceptance must not carry command_class"):
        OperatorActionRecord(
            action_id="op-2",
            actor_ref="jon",
            input_class=OperatorInputClass.RISK_ACCEPTANCE,
            target_ref="run-1",
            timestamp="2026-03-23T00:00:00+00:00",
            precondition_basis_ref="receipt-1",
            result="accepted",
            command_class=OperatorCommandClass.APPROVE_CONTINUE,
            risk_acceptance_scope="bounded uncertainty",
        )


def test_operator_attestation_requires_scope() -> None:
    with pytest.raises(ValidationError, match="operator attestation requires attestation_scope"):
        OperatorActionRecord(
            action_id="op-3",
            actor_ref="jon",
            input_class=OperatorInputClass.ATTESTATION,
            target_ref="run-1",
            timestamp="2026-03-23T00:00:00+00:00",
            precondition_basis_ref="receipt-1",
            result="recorded",
        )


def test_recovery_decision_rejects_multiple_execution_targets() -> None:
    with pytest.raises(ValidationError, match="cannot both resume an attempt and start a new attempt"):
        RecoveryDecisionRecord(
            decision_id="rd-1",
            run_id="run-1",
            failed_attempt_id="attempt-1",
            failure_classification_basis="tool_timeout",
            side_effect_boundary_class="pre_effect_failure",
            recovery_policy_ref="policy-1",
            authorized_next_action=RecoveryActionClass.START_NEW_ATTEMPT,
            resumed_attempt_id="attempt-1",
            new_attempt_id="attempt-2",
            rationale_ref="recovery-receipt-1",
        )


def test_recovery_decision_rejects_partial_failure_taxonomy() -> None:
    with pytest.raises(ValidationError, match="failure_plane and failure_classification must be set together"):
        RecoveryDecisionRecord(
            decision_id="rd-partial-failure-taxonomy",
            run_id="run-1",
            failed_attempt_id="attempt-1",
            failure_classification_basis="tool_timeout",
            failure_plane=FailurePlane.EXECUTION,
            side_effect_boundary_class="pre_effect_failure",
            recovery_policy_ref="policy-1",
            authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
            rationale_ref="recovery-receipt-partial-failure-taxonomy",
        )


def test_final_truth_record_rejects_success_without_sufficient_evidence() -> None:
    with pytest.raises(ValidationError, match="success result_class requires evidence_sufficient"):
        FinalTruthRecord(
            final_truth_record_id="truth-1",
            run_id="run-1",
            result_class=ResultClass.SUCCESS,
            completion_classification=CompletionClassification.SATISFIED,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.INSUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
            terminality_basis=TerminalityBasisClassification.COMPLETED_TERMINAL,
            authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        )


def test_final_truth_record_accepts_attested_degraded_closure() -> None:
    record = FinalTruthRecord(
        final_truth_record_id="truth-2",
        run_id="run-2",
        result_class=ResultClass.DEGRADED,
        completion_classification=CompletionClassification.PARTIAL,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.ATTESTED,
        residual_uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
        degradation_classification=DegradationClassification.OPERATOR_APPROVED,
        closure_basis=ClosureBasisClassification.OPERATOR_TERMINAL_STOP,
        terminality_basis=TerminalityBasisClassification.OPERATOR_TERMINAL,
        authority_sources=[
            AuthoritySourceClass.OPERATOR_ATTESTATION,
            AuthoritySourceClass.RECONCILIATION_RECORD,
        ],
    )

    assert record.result_class is ResultClass.DEGRADED


def test_run_record_accepts_lifecycle_state_enum() -> None:
    record = RunRecord(
        run_id="run-3",
        workload_id="workload-1",
        workload_version="2026-03-23",
        policy_snapshot_id="policy-3",
        policy_digest="sha256:policy-3",
        configuration_snapshot_id="config-3",
        configuration_digest="sha256:config-3",
        creation_timestamp="2026-03-23T00:00:00+00:00",
        admission_decision_receipt_ref="admission-3",
        lifecycle_state=RunState.EXECUTING,
        current_attempt_id="attempt-3",
    )

    assert record.lifecycle_state is RunState.EXECUTING


def test_attempt_record_requires_end_timestamp_for_terminal_states() -> None:
    with pytest.raises(ValidationError, match="terminal attempt state requires end_timestamp"):
        AttemptRecord(
            attempt_id="attempt-1",
            run_id="run-1",
            attempt_ordinal=1,
            attempt_state=AttemptState.FAILED,
            starting_state_snapshot_ref="snapshot-1",
            start_timestamp="2026-03-23T00:00:00+00:00",
            failure_class="tool_timeout",
        )


def test_attempt_record_rejects_end_timestamp_on_non_terminal_state() -> None:
    with pytest.raises(ValidationError, match="non-terminal attempt state cannot carry end_timestamp"):
        AttemptRecord(
            attempt_id="attempt-2",
            run_id="run-2",
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="snapshot-2",
            start_timestamp="2026-03-23T00:00:00+00:00",
            end_timestamp="2026-03-23T00:01:00+00:00",
        )


def test_attempt_record_rejects_side_effect_boundary_on_non_failed_attempt() -> None:
    with pytest.raises(ValidationError, match="side_effect_boundary_class is only valid"):
        AttemptRecord(
            attempt_id="attempt-3",
            run_id="run-3",
            attempt_ordinal=1,
            attempt_state=AttemptState.COMPLETED,
            starting_state_snapshot_ref="snapshot-3",
            start_timestamp="2026-03-23T00:00:00+00:00",
            end_timestamp="2026-03-23T00:01:00+00:00",
            side_effect_boundary_class="pre_effect_failure",
        )


def test_attempt_record_accepts_failed_attempt_with_recovery_link() -> None:
    record = AttemptRecord(
        attempt_id="attempt-4",
        run_id="run-4",
        attempt_ordinal=2,
        attempt_state=AttemptState.INTERRUPTED,
        starting_state_snapshot_ref="snapshot-4",
        start_timestamp="2026-03-23T00:00:00+00:00",
        end_timestamp="2026-03-23T00:01:00+00:00",
        side_effect_boundary_class="effect_boundary_uncertain",
        failure_plane=FailurePlane.EXECUTION,
        failure_classification=ExecutionFailureClass.TOOL_TIMEOUT,
        recovery_decision_id="recovery-4",
    )

    assert record.recovery_decision_id == "recovery-4"


def test_lease_record_schema_exposes_publication_timestamp() -> None:
    required = set(LeaseRecord.model_json_schema().get("required", []))
    assert "publication_timestamp" in required
