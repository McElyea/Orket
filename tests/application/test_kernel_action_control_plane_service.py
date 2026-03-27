# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_support import KernelActionControlPlaneSupportError
from orket.core.domain import (
    AttemptState,
    ClosureBasisClassification,
    CompletionClassification,
    EvidenceSufficiencyClassification,
    ExecutionFailureClass,
    FailurePlane,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
    TruthFailureClass,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_kernel_action_control_plane_service_records_committed_trace_with_validated_effect() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    request = {
        "contract_version": "kernel_api/v1",
        "session_id": "sess-kernel-cp-1",
        "trace_id": "trace-kernel-cp-1",
        "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "write_file"}},
    }
    response = {
        "proposal_digest": "a" * 64,
        "decision_digest": "b" * 64,
        "event_digest": "c" * 64,
        "admission_decision": {"decision": "ACCEPT_TO_UNIFY"},
    }
    ledger_items = [
        {
            "event_type": "admission.decided",
            "created_at": "2026-03-24T10:00:00+00:00",
            "event_digest": "c" * 64,
        }
    ]
    await service.record_admission(request=request, response=response, ledger_items=ledger_items)
    policy_snapshot = await record_repo.get_resolved_policy_snapshot(
        snapshot_id=KernelActionControlPlaneService.policy_snapshot_id_for(
            session_id="sess-kernel-cp-1",
            trace_id="trace-kernel-cp-1",
        )
    )
    configuration_snapshot = await record_repo.get_resolved_configuration_snapshot(
        snapshot_id=KernelActionControlPlaneService.configuration_snapshot_id_for(
            session_id="sess-kernel-cp-1",
            trace_id="trace-kernel-cp-1",
        )
    )

    commit_request = {
        "contract_version": "kernel_api/v1",
        "session_id": "sess-kernel-cp-1",
        "trace_id": "trace-kernel-cp-1",
        "proposal_digest": "a" * 64,
        "admission_decision_digest": "b" * 64,
        "execution_result_digest": "d" * 64,
        "execution_result_payload": {"ok": True, "path": "workspace/file.txt"},
    }
    commit_response = {
        "status": "COMMITTED",
        "commit_event_digest": "e" * 64,
    }
    commit_items = [
        *ledger_items,
        {
            "event_type": "action.executed",
            "created_at": "2026-03-24T10:01:00+00:00",
            "event_digest": "f" * 64,
        },
        {
            "event_type": "action.result_validated",
            "created_at": "2026-03-24T10:01:01+00:00",
            "event_digest": "g" * 64,
        },
        {
            "event_type": "commit.recorded",
            "created_at": "2026-03-24T10:01:02+00:00",
            "event_digest": "e" * 64,
        },
    ]

    run, attempt, final_truth, effect = await service.record_commit(
        request=commit_request,
        response=commit_response,
        ledger_items=commit_items,
    )
    step = await execution_repo.get_step_record(
        step_id=KernelActionControlPlaneService.step_id_for(run_id=run.run_id)
    )

    assert run.lifecycle_state is RunState.COMPLETED
    assert run.namespace_scope == "session:sess-kernel-cp-1"
    assert attempt.attempt_state is AttemptState.COMPLETED
    assert final_truth.result_class is ResultClass.SUCCESS
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == "b" * 64
    assert configuration_snapshot.snapshot_digest == "a" * 64
    assert final_truth.completion_classification is CompletionClassification.SATISFIED
    assert final_truth.evidence_sufficiency_classification is EvidenceSufficiencyClassification.SUFFICIENT
    assert step is not None
    assert step.observed_result_classification == "kernel_action_validated"
    assert step.closure_classification == "step_completed"
    assert effect is not None
    assert effect.step_id == step.step_id
    assert step.namespace_scope == "session:sess-kernel-cp-1"
    assert effect.uncertainty_classification is ResidualUncertaintyClassification.NONE
    assert effect.observed_result_ref == "kernel-execution-result:" + ("d" * 64)


@pytest.mark.asyncio
async def test_kernel_action_control_plane_service_rejects_namespace_scope_escalation() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    with pytest.raises(KernelActionControlPlaneSupportError, match="namespace scope escalation"):
        await service.record_admission(
            request={
                "contract_version": "kernel_api/v1",
                "session_id": "sess-kernel-cp-scope-1",
                "trace_id": "trace-kernel-cp-scope-1",
                "proposal": {
                    "proposal_type": "action.tool_call",
                    "payload": {"tool_name": "write_file", "namespace_scope": "issue:ISSUE-1"},
                },
            },
            response={
                "proposal_digest": "f1" * 32,
                "decision_digest": "f2" * 32,
                "event_digest": "f3" * 32,
            },
            ledger_items=[
                {
                    "event_type": "admission.decided",
                    "created_at": "2026-03-26T15:00:00+00:00",
                    "event_digest": "f3" * 32,
                }
            ],
        )


@pytest.mark.asyncio
async def test_kernel_action_control_plane_service_marks_digest_only_commit_degraded() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-2",
            "trace_id": "trace-kernel-cp-2",
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "1" * 64,
            "decision_digest": "2" * 64,
            "event_digest": "3" * 64,
        },
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-24T10:10:00+00:00",
                "event_digest": "3" * 64,
            }
        ],
    )

    run, attempt, final_truth, effect = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-2",
            "trace_id": "trace-kernel-cp-2",
            "proposal_digest": "1" * 64,
            "admission_decision_digest": "2" * 64,
            "execution_result_digest": "4" * 64,
        },
        response={"status": "COMMITTED", "commit_event_digest": "5" * 64},
        ledger_items=[
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-24T10:10:05+00:00",
                "event_digest": "5" * 64,
            }
        ],
    )
    step = await execution_repo.get_step_record(
        step_id=KernelActionControlPlaneService.step_id_for(run_id=run.run_id)
    )

    assert run.lifecycle_state is RunState.COMPLETED
    assert attempt.attempt_state is AttemptState.COMPLETED
    assert final_truth.result_class is ResultClass.DEGRADED
    assert step is not None
    assert step.observed_result_classification == "kernel_action_claimed"
    assert final_truth.evidence_sufficiency_classification is EvidenceSufficiencyClassification.INSUFFICIENT
    assert final_truth.residual_uncertainty_classification is ResidualUncertaintyClassification.UNRESOLVED
    assert effect is not None
    assert effect.uncertainty_classification is ResidualUncertaintyClassification.UNRESOLVED
    assert effect.observed_result_ref is None


@pytest.mark.asyncio
async def test_kernel_action_control_plane_service_cancels_unfinished_trace_on_session_end() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-3",
            "trace_id": "trace-kernel-cp-3",
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "6" * 64,
            "decision_digest": "7" * 64,
            "event_digest": "8" * 64,
        },
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-24T10:20:00+00:00",
                "event_digest": "8" * 64,
            }
        ],
    )

    closed = await service.record_session_end(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-3",
            "trace_id": "trace-kernel-cp-3",
            "reason": "manual-close",
        },
        response={"status": "ENDED", "event_digest": "9" * 64},
        ledger_items=[
            {
                "event_type": "session.ended",
                "created_at": "2026-03-24T10:20:10+00:00",
                "event_digest": "9" * 64,
            }
        ],
    )

    assert closed is not None
    run, attempt, final_truth = closed
    assert run.lifecycle_state is RunState.CANCELLED
    assert attempt is not None
    assert attempt.attempt_state is AttemptState.ABANDONED
    assert final_truth.result_class is ResultClass.BLOCKED
    assert final_truth.closure_basis is ClosureBasisClassification.CANCELLED_BY_AUTHORITY


@pytest.mark.asyncio
async def test_kernel_action_control_plane_service_preserves_effect_truth_on_policy_rejected_observed_execution() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-4",
            "trace_id": "trace-kernel-cp-4",
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "a1" * 32,
            "decision_digest": "b1" * 32,
            "event_digest": "c1" * 32,
        },
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-24T10:30:00+00:00",
                "event_digest": "c1" * 32,
            }
        ],
    )

    run, attempt, final_truth, effect = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-4",
            "trace_id": "trace-kernel-cp-4",
            "proposal_digest": "a1" * 32,
            "admission_decision_digest": "b1" * 32,
            "execution_result_digest": "d1" * 32,
            "execution_result_payload": {"ok": True, "body": "unsafe"},
        },
        response={"status": "REJECTED_POLICY", "commit_event_digest": "e1" * 32},
        ledger_items=[
            {
                "event_type": "action.executed",
                "created_at": "2026-03-24T10:30:01+00:00",
                "event_digest": "f1" * 32,
            },
            {
                "event_type": "action.result_validated",
                "created_at": "2026-03-24T10:30:02+00:00",
                "event_digest": "g1" * 32,
            },
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-24T10:30:03+00:00",
                "event_digest": "e1" * 32,
            },
        ],
    )
    step = await execution_repo.get_step_record(
        step_id=KernelActionControlPlaneService.step_id_for(run_id=run.run_id)
    )
    decision = None if attempt.recovery_decision_id is None else await record_repo.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )

    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert attempt.failure_class == "kernel_action_policy_rejected"
    assert attempt.failure_plane is FailurePlane.TRUTH
    assert attempt.failure_classification is TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY
    assert final_truth.result_class is ResultClass.FAILED
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_plane is FailurePlane.TRUTH
    assert decision.failure_classification is TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY
    assert step is not None
    assert step.observed_result_classification == "kernel_action_observed_policy_reject"
    assert step.closure_classification == "step_failed"
    assert effect is not None
    assert effect.observed_result_ref == "kernel-execution-result:" + ("d1" * 32)


@pytest.mark.asyncio
async def test_kernel_action_control_plane_service_publishes_recovery_for_error_with_observed_execution() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-5",
            "trace_id": "trace-kernel-cp-5",
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "aa" * 32,
            "decision_digest": "bb" * 32,
            "event_digest": "cc" * 32,
        },
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-24T10:40:00+00:00",
                "event_digest": "cc" * 32,
            }
        ],
    )

    run, attempt, final_truth, effect = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-5",
            "trace_id": "trace-kernel-cp-5",
            "proposal_digest": "aa" * 32,
            "admission_decision_digest": "bb" * 32,
            "execution_result_payload": {"ok": False, "error": "boom"},
        },
        response={"status": "ERROR", "commit_event_digest": "dd" * 32},
        ledger_items=[
            {
                "event_type": "action.executed",
                "created_at": "2026-03-24T10:40:01+00:00",
                "event_digest": "ee" * 32,
            },
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-24T10:40:02+00:00",
                "event_digest": "dd" * 32,
            },
        ],
    )
    decision = None if attempt.recovery_decision_id is None else await record_repo.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )

    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert attempt.failure_class == "kernel_action_error"
    assert attempt.failure_plane is FailurePlane.EXECUTION
    assert attempt.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_plane is FailurePlane.EXECUTION
    assert decision.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert final_truth.result_class is ResultClass.FAILED
    assert final_truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP
    assert effect is None
