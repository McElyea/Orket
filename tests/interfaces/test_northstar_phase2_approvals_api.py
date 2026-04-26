from __future__ import annotations

from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_run_service import OutwardRunService
from tests.helpers.outward_model import patch_outward_model_client


async def _seed_pending(db_path, *, run_id: str = "run-api-approval") -> str:
    await OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: run_id,
        utc_now=lambda: "2026-04-25T12:00:00+00:00",
    ).submit(
        {
            "run_id": run_id,
            "task": {"description": "Write file", "instruction": "Create the requested file"},
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        }
    )
    proposal = await OutwardApprovalService(
        approval_store=OutwardApprovalStore(db_path),
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=lambda: "2026-04-25T12:01:00+00:00",
    ).request_tool_approval(
        run_id=run_id,
        tool="write_file",
        args={"path": "out.txt", "content": "secret"},
        context_summary="operator review",
        timeout_seconds=9999999,
    )
    return proposal.proposal_id


def _client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    db_path = tmp_path / "phase2-control-plane.sqlite3"
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(db_path))
    patch_outward_model_client(monkeypatch, args={"path": "api-approved.txt", "content": "api approved"})
    return TestClient(api_module.create_api_app(project_root=tmp_path)), str(db_path)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_approval_list_review_approve_and_idempotency(tmp_path, monkeypatch) -> None:
    """Layer: integration. Verifies outward approval queue, review, approve, and idempotency API behavior."""
    client, db_path = _client(tmp_path, monkeypatch)
    proposal_id = await _seed_pending(db_path)
    try:
        listed = client.get("/v1/approvals?status=pending", headers={"X-API-Key": "test-key"})
        reviewed = client.get(f"/v1/approvals/{proposal_id}", headers={"X-API-Key": "test-key"})
        approved = client.post(
            f"/v1/approvals/{proposal_id}/approve",
            headers={"X-API-Key": "test-key"},
            json={"note": "safe"},
        )
        repeated = client.post(
            f"/v1/approvals/{proposal_id}/approve",
            headers={"X-API-Key": "test-key"},
            json={"note": "safe again"},
        )

        assert listed.status_code == 200
        assert listed.json()["items"][0]["proposal_id"] == proposal_id
        assert listed.json()["items"][0]["args_preview"]["content"] == "[REDACTED]"
        assert reviewed.status_code == 200
        assert reviewed.json()["proposal_id"] == proposal_id
        assert approved.status_code == 200
        assert approved.json()["approval"]["status"] == "approved"
        assert repeated.json() == approved.json()
    finally:
        client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_approval_deny_api_records_terminal_run(tmp_path, monkeypatch) -> None:
    """Layer: integration. Verifies outward denial endpoint fails the run and records a decision event."""
    client, db_path = _client(tmp_path, monkeypatch)
    proposal_id = await _seed_pending(db_path, run_id="run-deny-api")
    try:
        denied = client.post(
            f"/v1/approvals/{proposal_id}/deny",
            headers={"X-API-Key": "test-key"},
            json={"reason": "operator rejected"},
        )
        assert denied.status_code == 200
        assert denied.json()["approval"]["status"] == "denied"
    finally:
        client.close()

    run = await OutwardRunStore(db_path).get("run-deny-api")
    assert run is not None
    assert run.status == "failed"
    events = await OutwardRunEventStore(db_path).list_for_run("run-deny-api")
    assert events[-1].event_type == "proposal_denied"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_submit_pauses_before_api_approval_then_writes_file(tmp_path, monkeypatch) -> None:
    """Layer: integration. Verifies API submission reaches a gated write_file and resumes after approval."""
    client, db_path = _client(tmp_path, monkeypatch)
    target = tmp_path / "api-approved.txt"
    try:
        submitted = client.post(
            "/v1/runs",
            headers={"X-API-Key": "test-key"},
            json={
                "run_id": "run-api-exec",
                "task": {
                    "description": "Write a file",
                    "instruction": "Call write_file",
                    "acceptance_contract": {
                        "governed_tool_call": {
                            "tool": "write_file",
                            "args": {"path": "api-approved.txt", "content": "api approved"},
                        }
                    },
                },
                "policy_overrides": {"approval_required_tools": ["write_file"]},
            },
        )
        listed = client.get("/v1/approvals?status=pending", headers={"X-API-Key": "test-key"})
        proposal_id = listed.json()["items"][0]["proposal_id"]
        assert target.exists() is False
        approved = client.post(
            f"/v1/approvals/{proposal_id}/approve",
            headers={"X-API-Key": "test-key"},
            json={"note": "safe"},
        )
        status = client.get("/v1/runs/run-api-exec", headers={"X-API-Key": "test-key"})

        assert submitted.status_code == 200
        assert submitted.json()["status"] == "approval_required"
        assert approved.status_code == 200
        assert approved.json()["approval"]["status"] == "approved"
        assert status.json()["status"] == "completed"
        assert target.read_text(encoding="utf-8") == "api approved"
    finally:
        client.close()

    events = await OutwardRunEventStore(db_path).list_for_run("run-api-exec")
    assert "tool_invoked" in [event.event_type for event in events]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_approval_payloads_traverse_outbound_gate(tmp_path, monkeypatch) -> None:
    """Layer: contract. Verifies approval list, review, and decision payloads pass through the outbound gate."""
    calls: list[str] = []

    def _fake_gate(payload: Any, config: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        calls.append(str((config or {}).get("surface") or ""))
        return payload, {"applied": True}

    monkeypatch.setattr(api_module, "apply_outbound_policy_gate", _fake_gate)
    client, db_path = _client(tmp_path, monkeypatch)
    proposal_id = await _seed_pending(db_path, run_id="run-gate-api")
    try:
        client.get("/v1/approvals?status=pending", headers={"X-API-Key": "test-key"})
        client.get(f"/v1/approvals/{proposal_id}", headers={"X-API-Key": "test-key"})
        client.post(
            f"/v1/approvals/{proposal_id}/approve",
            headers={"X-API-Key": "test-key"},
            json={},
        )
    finally:
        client.close()

    assert calls == ["api.approvals.list", "api.approvals.review", "api.approvals.approve"]


@pytest.mark.contract
def test_no_approve_and_pause_surface_exists() -> None:
    """Layer: contract. Verifies Phase 2 does not introduce approve-and-pause semantics."""
    paths = {
        str(route.path)
        for route in api_module.app.routes
        if isinstance(route, APIRoute) and str(route.path).startswith("/v1/approvals")
    }

    assert not any("pause" in path for path in paths)
