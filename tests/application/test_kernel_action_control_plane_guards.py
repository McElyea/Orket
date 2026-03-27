# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import (
    KernelActionControlPlaneError,
    KernelActionControlPlaneService,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_kernel_action_commit_rejects_unsupported_status() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    with pytest.raises(
        KernelActionControlPlaneError,
        match="unsupported governed action commit status for control-plane publication",
    ):
        await service.record_commit(
            request={
                "contract_version": "kernel_api/v1",
                "session_id": "sess-kernel-guard-1",
                "trace_id": "trace-kernel-guard-1",
                "proposal_digest": "1" * 64,
                "admission_decision_digest": "2" * 64,
            },
            response={"status": "DENIED_OPERATOR", "commit_event_digest": "3" * 64},
            ledger_items=[
                {
                    "event_type": "admission.decided",
                    "created_at": "2026-03-25T18:00:00+00:00",
                    "event_digest": "4" * 64,
                },
                {
                    "event_type": "commit.recorded",
                    "created_at": "2026-03-25T18:00:01+00:00",
                    "event_digest": "3" * 64,
                },
            ],
        )
