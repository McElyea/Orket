# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_operator_service import (
    KernelActionControlPlaneOperatorService,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_kernel_action_operator_service_publishes_cancel_command() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    record = await service.publish_cancel_run_command(
        actor_ref="api_key_fingerprint:sha256:test",
        session_id="sess-kernel-op-1",
        trace_id="trace-kernel-op-1",
        timestamp="2026-03-24T12:00:00+00:00",
        receipt_ref="kernel-ledger-event:abc",
        reason="manual-close",
    )

    assert record.command_class.value == "cancel_run"
    assert record.result == "accepted_cancel"
    assert record.affected_resource_refs == ["kernel-action-scope:session:sess-kernel-op-1"]
    assert record.receipt_refs == ["kernel-ledger-event:abc"]


@pytest.mark.asyncio
async def test_kernel_action_operator_service_publishes_attestation() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = KernelActionControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    record = await service.publish_run_attestation(
        actor_ref="api_key_fingerprint:sha256:test",
        session_id="sess-kernel-op-2",
        trace_id="trace-kernel-op-2",
        timestamp="2026-03-26T12:00:00+00:00",
        receipt_ref="kernel-ledger-event:def",
        attestation_scope="run_scope",
        attestation_payload={"observation": "manual_verification"},
        request_id="req-attest-1",
        precondition_basis_ref="kernel-session-end:manual-close",
    )

    assert record.input_class.value == "operator_attestation"
    assert record.command_class is None
    assert record.attestation_scope == "run_scope"
    assert record.attestation_payload == {"observation": "manual_verification"}
    assert record.result == "recorded_attestation"
    assert record.affected_resource_refs == ["kernel-action-scope:session:sess-kernel-op-2"]
