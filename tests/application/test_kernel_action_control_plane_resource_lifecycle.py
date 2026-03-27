# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    lease_id_for_run,
    reservation_id_for_run,
    resource_id_for_run,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.core.domain import LeaseStatus, OrphanClassification, ReservationKind, ReservationStatus, RunState
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
async def test_kernel_action_admission_publishes_active_concurrency_reservation() -> None:
    service, _, record_repo = _service()

    run, _ = await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-resource-1",
            "trace_id": "trace-kernel-resource-1",
            "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "echo"}},
        },
        response={
            "proposal_digest": "a" * 64,
            "decision_digest": "b" * 64,
            "event_digest": "c" * 64,
        },
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-25T12:00:00+00:00",
                "event_digest": "c" * 64,
            }
        ],
    )

    reservation = await record_repo.get_latest_reservation_record(reservation_id=reservation_id_for_run(run_id=run.run_id))
    assert reservation is not None
    assert reservation.reservation_kind is ReservationKind.CONCURRENCY
    assert reservation.status is ReservationStatus.ACTIVE
    assert reservation.holder_ref == f"kernel-action-run:{run.run_id}"
    assert reservation.target_scope_ref == f"kernel-action-scope:{run.namespace_scope}"


@pytest.mark.asyncio
async def test_kernel_action_commit_promotes_reservation_and_releases_lease_on_terminal_closeout() -> None:
    service, _, record_repo = _service()

    run, _, _, _ = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-resource-2",
            "trace_id": "trace-kernel-resource-2",
            "proposal_digest": "d" * 64,
            "admission_decision_digest": "e" * 64,
            "execution_result_digest": "f" * 64,
        },
        response={"status": "COMMITTED", "commit_event_digest": "g" * 64},
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-25T12:10:00+00:00",
                "event_digest": "h" * 64,
            },
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-25T12:10:02+00:00",
                "event_digest": "g" * 64,
            },
        ],
    )

    assert run.lifecycle_state is RunState.COMPLETED
    reservation_id = reservation_id_for_run(run_id=run.run_id)
    lease_id = lease_id_for_run(run_id=run.run_id)
    reservation = await record_repo.get_latest_reservation_record(reservation_id=reservation_id)
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id)
    lease_history = await record_repo.list_lease_records(lease_id=lease_id)
    resource_history = await record_repo.list_resource_records(resource_id=resource_id_for_run(run=run))
    latest_resource = await record_repo.get_latest_resource_record(resource_id=resource_id_for_run(run=run))

    assert reservation is not None
    assert reservation.status is ReservationStatus.PROMOTED_TO_LEASE
    assert lease is not None
    assert latest_resource is not None
    assert lease.status is LeaseStatus.RELEASED
    assert len(lease_history) == 2
    assert lease_history[0].status is LeaseStatus.ACTIVE
    assert lease_history[-1].status is LeaseStatus.RELEASED
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
    assert latest_resource.orphan_classification is OrphanClassification.NOT_ORPHANED


@pytest.mark.asyncio
async def test_kernel_action_session_end_releases_admission_reservation_when_run_never_executes() -> None:
    service, _, record_repo = _service()
    run, _ = await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-resource-3",
            "trace_id": "trace-kernel-resource-3",
            "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "echo"}},
        },
        response={
            "proposal_digest": "1" * 64,
            "decision_digest": "2" * 64,
            "event_digest": "3" * 64,
        },
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-25T12:20:00+00:00",
                "event_digest": "3" * 64,
            }
        ],
    )

    closed = await service.record_session_end(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-resource-3",
            "trace_id": "trace-kernel-resource-3",
        },
        response={"status": "ENDED", "event_digest": "4" * 64},
        ledger_items=[
            {
                "event_type": "session.ended",
                "created_at": "2026-03-25T12:20:05+00:00",
                "event_digest": "4" * 64,
            }
        ],
    )

    assert closed is not None
    reservation = await record_repo.get_latest_reservation_record(reservation_id=reservation_id_for_run(run_id=run.run_id))
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    assert reservation is not None
    assert reservation.status is ReservationStatus.RELEASED
    assert lease is None


@pytest.mark.asyncio
async def test_kernel_action_policy_reject_with_observed_execution_releases_terminal_lease() -> None:
    service, _, record_repo = _service()

    run, _, _, _ = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-resource-4",
            "trace_id": "trace-kernel-resource-4",
            "proposal_digest": "9" * 64,
            "admission_decision_digest": "8" * 64,
            "execution_result_payload": {"ok": True, "unsafe": True},
        },
        response={"status": "REJECTED_POLICY", "commit_event_digest": "7" * 64},
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-25T12:30:00+00:00",
                "event_digest": "6" * 64,
            },
            {
                "event_type": "action.executed",
                "created_at": "2026-03-25T12:30:01+00:00",
                "event_digest": "5" * 64,
            },
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-25T12:30:02+00:00",
                "event_digest": "7" * 64,
            },
        ],
    )

    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    reservation = await record_repo.get_latest_reservation_record(reservation_id=reservation_id_for_run(run_id=run.run_id))
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    resource = await record_repo.get_latest_resource_record(resource_id=resource_id_for_run(run=run))
    assert reservation is not None
    assert reservation.status is ReservationStatus.PROMOTED_TO_LEASE
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    assert resource is not None
    assert resource.current_observed_state.split(";")[0] == "lease_status:lease_released"


@pytest.mark.asyncio
async def test_kernel_action_policy_reject_without_observed_execution_releases_admission_reservation_without_lease() -> None:
    service, _, record_repo = _service()

    run, _, _, _ = await service.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-resource-5",
            "trace_id": "trace-kernel-resource-5",
            "proposal_digest": "1a" * 32,
            "admission_decision_digest": "2a" * 32,
        },
        response={"status": "REJECTED_POLICY", "commit_event_digest": "3a" * 32},
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-25T12:40:00+00:00",
                "event_digest": "4a" * 32,
            },
            {
                "event_type": "commit.recorded",
                "created_at": "2026-03-25T12:40:02+00:00",
                "event_digest": "3a" * 32,
            },
        ],
    )

    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    reservation = await record_repo.get_latest_reservation_record(reservation_id=reservation_id_for_run(run_id=run.run_id))
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    assert reservation is not None
    assert reservation.status is ReservationStatus.RELEASED
    assert lease is None


@pytest.mark.asyncio
async def test_kernel_action_execution_activation_fail_closes_reservation_and_lease_on_promotion_error() -> None:
    service, execution_repo, record_repo = _service()
    await service.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": "sess-kernel-resource-6",
            "trace_id": "trace-kernel-resource-6",
            "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "echo"}},
        },
        response={
            "proposal_digest": "8b" * 32,
            "decision_digest": "9b" * 32,
            "event_digest": "ab" * 32,
        },
        ledger_items=[
            {
                "event_type": "admission.decided",
                "created_at": "2026-03-26T12:00:00+00:00",
                "event_digest": "ab" * 32,
            }
        ],
    )

    async def _raise_promote_failure(**_kwargs) -> None:
        raise RuntimeError("promote failed")

    service.publication.promote_reservation_to_lease = _raise_promote_failure  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="promote failed"):
        await service.record_commit(
            request={
                "contract_version": "kernel_api/v1",
                "session_id": "sess-kernel-resource-6",
                "trace_id": "trace-kernel-resource-6",
                "proposal_digest": "8b" * 32,
                "admission_decision_digest": "9b" * 32,
                "execution_result_digest": "cb" * 32,
            },
            response={"status": "COMMITTED", "commit_event_digest": "db" * 32},
            ledger_items=[
                {
                    "event_type": "admission.decided",
                    "created_at": "2026-03-26T12:00:00+00:00",
                    "event_digest": "ab" * 32,
                },
                {
                    "event_type": "commit.recorded",
                    "created_at": "2026-03-26T12:00:05+00:00",
                    "event_digest": "db" * 32,
                },
            ],
        )

    run_id = service.run_id_for(session_id="sess-kernel-resource-6", trace_id="trace-kernel-resource-6")
    run = await execution_repo.get_run_record(run_id=run_id)
    reservation = await record_repo.get_latest_reservation_record(reservation_id=reservation_id_for_run(run_id=run_id))
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    resource_history = await record_repo.list_resource_records(
        resource_id=resource_id_for_run(run=run) if run is not None else f"kernel-action-scope:{run_id}"
    )

    assert run is not None
    assert run.lifecycle_state is RunState.EXECUTING
    assert reservation is not None
    assert reservation.status is ReservationStatus.INVALIDATED
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
