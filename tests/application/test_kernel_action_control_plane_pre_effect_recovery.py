# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.core.domain import (
    AttemptState,
    ClosureBasisClassification,
    ExecutionFailureClass,
    FailurePlane,
    RecoveryActionClass,
    RunState,
    SideEffectBoundaryClass,
    TruthFailureClass,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


pytestmark = pytest.mark.unit


def _service() -> tuple[
    KernelActionControlPlaneService,
    InMemoryControlPlaneExecutionRepository,
    InMemoryControlPlaneRecordRepository,
]:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    return service, execution_repo, record_repo


@pytest.mark.asyncio
async def test_kernel_action_pre_effect_rejected_policy_publishes_terminal_recovery_decision() -> None:
    service, _, record_repo = _service()

    run, attempt, final_truth, effect = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-pre-effect-1",
            "trace_id": "trace-kernel-pre-effect-1",
            "proposal_digest": "a1" * 32,
            "admission_decision_digest": "b1" * 32,
        },
        response={"status": "REJECTED_POLICY", "commit_event_digest": "c1" * 32},
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-25T16:00:00+00:00",
                "event_digest": "d1" * 32,
            },
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-25T16:00:01+00:00",
                "event_digest": "c1" * 32,
            },
        ],
    )

    decision = None if attempt.recovery_decision_id is None else await record_repo.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.ABANDONED
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert attempt.failure_class == "kernel_action_policy_rejected"
    assert attempt.failure_plane is FailurePlane.TRUTH
    assert attempt.failure_classification is TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert final_truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP
    assert effect is None


@pytest.mark.asyncio
async def test_kernel_action_pre_effect_error_publishes_terminal_recovery_decision() -> None:
    service, _, record_repo = _service()

    run, attempt, final_truth, effect = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-pre-effect-2",
            "trace_id": "trace-kernel-pre-effect-2",
            "proposal_digest": "e1" * 32,
            "admission_decision_digest": "f1" * 32,
        },
        response={"status": "ERROR", "commit_event_digest": "g1" * 32},
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-25T16:10:00+00:00",
                "event_digest": "h1" * 32,
            },
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-25T16:10:01+00:00",
                "event_digest": "g1" * 32,
            },
        ],
    )

    decision = None if attempt.recovery_decision_id is None else await record_repo.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.ABANDONED
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert attempt.failure_class == "kernel_action_error"
    assert attempt.failure_plane is FailurePlane.EXECUTION
    assert attempt.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert final_truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP
    assert effect is None
