# Layer: unit

from __future__ import annotations

from typing import Any

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_operator_service import (
    KernelActionControlPlaneOperatorService,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import (
    KernelActionControlPlaneViewService,
)
from orket.orchestration.engine import OrchestrationEngine
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.unit


class _FakeKernelGatewayFacade:
    def __init__(
        self,
        *,
        admit_response: dict[str, Any] | None = None,
        commit_response: dict[str, Any] | None = None,
        end_response: dict[str, Any] | None = None,
        ledger_by_limit: dict[int, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._admit_response = dict(admit_response or {})
        self._commit_response = dict(commit_response or {})
        self._end_response = dict(end_response or {})
        self._ledger_by_limit = {
            int(limit): [dict(item) for item in items]
            for limit, items in dict(ledger_by_limit or {}).items()
        }

    def admit_proposal(self, _request: dict[str, Any]) -> dict[str, Any]:
        return dict(self._admit_response)

    def commit_proposal(self, _request: dict[str, Any]) -> dict[str, Any]:
        return dict(self._commit_response)

    def end_session(self, _request: dict[str, Any]) -> dict[str, Any]:
        return dict(self._end_response)

    def list_ledger_events(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"items": list(self._ledger_by_limit.get(int(request.get("limit") or 0), []))}


def _make_engine(*, facade: _FakeKernelGatewayFacade) -> OrchestrationEngine:
    engine = object.__new__(OrchestrationEngine)
    record_repo = InMemoryControlPlaneRecordRepository()
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    engine.control_plane_repository = record_repo
    engine.control_plane_execution_repository = execution_repo
    engine.control_plane_publication = publication
    engine.kernel_action_control_plane = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=publication,
    )
    engine.kernel_action_control_plane_operator = KernelActionControlPlaneOperatorService(
        publication=publication,
    )
    engine.kernel_action_control_plane_view = KernelActionControlPlaneViewService(
        record_repository=record_repo,
        execution_repository=execution_repo,
    )
    engine.kernel_gateway_facade = facade
    return engine


@pytest.mark.asyncio
async def test_orchestration_engine_kernel_admit_async_publishes_pending_hold_and_augments_response() -> None:
    engine = _make_engine(
        facade=_FakeKernelGatewayFacade(
            admit_response={
                "proposal_digest": "a" * 64,
                "decision_digest": "b" * 64,
                "approval_id": "apr-engine-kernel-1",
                "admission_decision": {"decision": "NEEDS_APPROVAL"},
            },
            ledger_by_limit={
                200: [
                    {
                        "event_type": "admission.decided",
                        "created_at": "2026-03-27T14:00:00+00:00",
                        "event_digest": "c" * 64,
                    }
                ]
            },
        )
    )

    async def _fake_get_approval(_approval_id: str) -> dict[str, Any]:
        return {"approval_id": "apr-engine-kernel-1", "created_at": "2026-03-27T14:00:01+00:00"}

    engine.get_approval = _fake_get_approval

    response = await engine.kernel_admit_proposal_async(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-engine-kernel-1",
            "trace_id": "trace-engine-kernel-1",
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"tool_name": "write_file"},
            },
        }
    )

    assert response["control_plane_run_id"] == (
        "kernel-action-run:sess-engine-kernel-1:trace-engine-kernel-1"
    )
    assert response["control_plane_attempt_id"] == (
        "kernel-action-attempt:sess-engine-kernel-1:trace-engine-kernel-1:0001"
    )
    assert response["control_plane_attempt_state"] == "attempt_created"
    assert response["control_plane_reservation_id"] == "approval-reservation:apr-engine-kernel-1"
    reservation = await engine.control_plane_repository.get_latest_reservation_record(
        reservation_id="approval-reservation:apr-engine-kernel-1"
    )
    assert reservation is not None
    assert reservation.reservation_kind.value == "operator_hold_reservation"
    assert reservation.holder_ref == "kernel-action-run:sess-engine-kernel-1:trace-engine-kernel-1"


@pytest.mark.asyncio
async def test_orchestration_engine_kernel_commit_async_returns_resource_and_final_truth_refs() -> None:
    engine = _make_engine(
        facade=_FakeKernelGatewayFacade(
            admit_response={
                "proposal_digest": "d" * 64,
                "decision_digest": "e" * 64,
                "admission_decision": {"decision": "ACCEPT_TO_UNIFY"},
            },
            commit_response={
                "status": "COMMITTED",
                "commit_event_digest": "f" * 64,
            },
            ledger_by_limit={
                200: [
                    {
                        "event_type": "admission.decided",
                        "created_at": "2026-03-27T14:10:00+00:00",
                        "event_digest": "1" * 64,
                    }
                ],
                400: [
                    {
                        "event_type": "admission.decided",
                        "created_at": "2026-03-27T14:10:00+00:00",
                        "event_digest": "1" * 64,
                    },
                    {
                        "event_type": "action.executed",
                        "created_at": "2026-03-27T14:10:01+00:00",
                        "event_digest": "2" * 64,
                    },
                    {
                        "event_type": "action.result_validated",
                        "created_at": "2026-03-27T14:10:02+00:00",
                        "event_digest": "3" * 64,
                    },
                    {
                        "event_type": "commit.recorded",
                        "created_at": "2026-03-27T14:10:03+00:00",
                        "event_digest": "f" * 64,
                    },
                ],
            },
        )
    )
    engine.get_approval = _no_approval

    admitted = await engine.kernel_admit_proposal_async(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-engine-kernel-2",
            "trace_id": "trace-engine-kernel-2",
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )
    committed = await engine.kernel_commit_proposal_async(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-engine-kernel-2",
            "trace_id": "trace-engine-kernel-2",
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "execution_result_digest": "9" * 64,
            "execution_result_payload": {"ok": True, "path": "workspace/out.txt"},
            "execution_result_schema_valid": True,
        }
    )

    assert committed["control_plane_run_id"] == (
        "kernel-action-run:sess-engine-kernel-2:trace-engine-kernel-2"
    )
    assert committed["control_plane_attempt_state"] == "attempt_completed"
    assert committed["control_plane_reservation_id"] == (
        "kernel-action-reservation:kernel-action-run:sess-engine-kernel-2:trace-engine-kernel-2"
    )
    assert committed["control_plane_lease_id"] == (
        "kernel-action-lease:kernel-action-run:sess-engine-kernel-2:trace-engine-kernel-2"
    )
    assert committed["control_plane_resource_id"] == "kernel-action-scope:session:sess-engine-kernel-2"
    assert committed["control_plane_step_id"].startswith("kernel-action-step:")
    assert committed["control_plane_final_truth_record_id"] == (
        "kernel-action-final-truth:kernel-action-run:sess-engine-kernel-2:trace-engine-kernel-2"
    )


@pytest.mark.asyncio
async def test_orchestration_engine_kernel_end_session_async_returns_final_truth_and_operator_refs() -> None:
    engine = _make_engine(
        facade=_FakeKernelGatewayFacade(
            admit_response={
                "proposal_digest": "7" * 64,
                "decision_digest": "8" * 64,
                "admission_decision": {"decision": "ACCEPT_TO_UNIFY"},
            },
            end_response={
                "status": "ENDED",
                "event_digest": "a" * 64,
            },
            ledger_by_limit={
                200: [
                    {
                        "event_type": "admission.decided",
                        "created_at": "2026-03-27T14:20:00+00:00",
                        "event_digest": "b" * 64,
                    },
                    {
                        "event_type": "session.ended",
                        "created_at": "2026-03-27T14:20:05+00:00",
                        "event_digest": "a" * 64,
                    },
                ]
            },
        )
    )
    engine.get_approval = _no_approval

    await engine.kernel_admit_proposal_async(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-engine-kernel-3",
            "trace_id": "trace-engine-kernel-3",
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )
    ended = await engine.kernel_end_session_async(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-engine-kernel-3",
            "trace_id": "trace-engine-kernel-3",
            "reason": "manual-close",
            "operator_actor_ref": "api_key_fingerprint:sha256:test",
            "attestation_scope": "run_scope",
            "attestation_payload": {"operator_note": "confirmed"},
        }
    )

    assert ended["control_plane_run_id"] == "kernel-action-run:sess-engine-kernel-3:trace-engine-kernel-3"
    assert ended["control_plane_attempt_state"] == "attempt_abandoned"
    assert ended["control_plane_final_truth_record_id"] == (
        "kernel-action-final-truth:kernel-action-run:sess-engine-kernel-3:trace-engine-kernel-3"
    )
    assert ended["control_plane_operator_action_id"].startswith("kernel-action-operator:")


async def _no_approval(_approval_id: str) -> None:
    return None
