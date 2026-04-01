# Layer: integration

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.interfaces.api import app
import orket.interfaces.api as api_module
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_engine_approvals import _FakePendingGates, _tool_approval_row

pytestmark = pytest.mark.integration


client = TestClient(app)


def test_get_approval_returns_409_for_unsupported_packet1_status(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)
    row = _tool_approval_row()
    row["status"] = "approved_with_edits"
    monkeypatch.setattr(api_module.engine, "pending_gates", _FakePendingGates(rows=[row]), raising=False)
    monkeypatch.setattr(
        api_module.engine,
        "control_plane_repository",
        InMemoryControlPlaneRecordRepository(),
        raising=False,
    )

    response = client.get("/v1/approvals/apr-1", headers={"X-API-Key": "test-key"})

    assert response.status_code == 409
    assert "unsupported Packet 1 status" in response.json()["detail"]


def test_list_approvals_rejects_unsupported_packet1_status_filter(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)
    monkeypatch.setattr(api_module.engine, "pending_gates", _FakePendingGates(rows=[_tool_approval_row()]), raising=False)

    response = client.get("/v1/approvals?status=EXPIRED", headers={"X-API-Key": "test-key"})

    assert response.status_code == 422
    assert response.json()["detail"] == "status must be one of PENDING, APPROVED, DENIED"


def test_get_approval_returns_409_for_target_projection_drift(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)
    row = _tool_approval_row()
    row["payload_json"] = {
        **dict(row["payload_json"]),
        "control_plane_target_ref": "turn-tool-run:sess-1:ISS-1:coder:9999",
    }
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = ToolApprovalControlPlaneReservationService(publication=publication)
    asyncio.run(
        service.publish_pending_tool_approval_hold(
            approval_id="apr-1",
            session_id="sess-1",
            issue_id="ISS-1",
            seat_name="coder",
            tool_name="write_file",
            turn_index=1,
            created_at="2026-03-03T12:00:00+00:00",
            control_plane_target_ref="turn-tool-run:sess-1:ISS-1:coder:0001",
        )
    )
    monkeypatch.setattr(api_module.engine, "pending_gates", _FakePendingGates(rows=[row]), raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", repository, raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", publication, raising=False)

    response = client.get("/v1/approvals/apr-1", headers={"X-API-Key": "test-key"})

    assert response.status_code == 409
    assert "target projection drift" in response.json()["detail"]
