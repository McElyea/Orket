# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.core.domain import AttemptState, ResultClass, RunState
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_kernel_action_session_end_abandons_executing_attempt_before_run_cancel() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run, attempt = await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-session-end-guard",
            "trace_id": "trace-kernel-cp-session-end-guard",
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
                "created_at": "2026-03-26T00:00:00+00:00",
                "event_digest": "8" * 64,
            }
        ],
    )
    run = run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
    attempt = attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING})
    await execution_repo.save_run_record(record=run)
    await execution_repo.save_attempt_record(record=attempt)

    closed = await service.record_session_end(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-cp-session-end-guard",
            "trace_id": "trace-kernel-cp-session-end-guard",
            "reason": "manual-close",
        },
        response={"status": "ENDED", "event_digest": "9" * 64},
        ledger_items=[
            {
                "event_type": "session.ended",
                "created_at": "2026-03-26T00:00:05+00:00",
                "event_digest": "9" * 64,
            }
        ],
    )

    assert closed is not None
    closed_run, closed_attempt, final_truth = closed
    assert closed_run.lifecycle_state is RunState.CANCELLED
    assert closed_attempt is not None
    assert closed_attempt.attempt_state is AttemptState.ABANDONED
    assert closed_attempt.end_timestamp == "2026-03-26T00:00:05+00:00"
    assert final_truth.result_class is ResultClass.BLOCKED

