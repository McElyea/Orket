from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from tests.helpers.outward_model import patch_outward_model_client


def _client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    db_path = tmp_path / "phase4-control-plane.sqlite3"
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(db_path))
    patch_outward_model_client(monkeypatch, args={"path": "phase4.txt", "content": "phase4"})
    return TestClient(api_module.create_api_app(project_root=tmp_path)), str(db_path)


def _submit_and_approve(client: TestClient) -> str:
    submitted = client.post(
        "/v1/runs",
        headers={"X-API-Key": "test-key"},
        json={
            "run_id": "run-phase4-api",
            "task": {
                "description": "Write file",
                "instruction": "Call write_file",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "phase4.txt", "content": "phase4"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        },
    )
    assert submitted.status_code == 200
    proposal = client.get("/v1/approvals", headers={"X-API-Key": "test-key"}, params={"status": "pending"})
    proposal_id = proposal.json()["items"][0]["proposal_id"]
    approved = client.post(f"/v1/approvals/{proposal_id}/approve", headers={"X-API-Key": "test-key"}, json={})
    assert approved.status_code == 200
    return "run-phase4-api"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_phase4_ledger_export_verify_filter_audit_and_gate(tmp_path, monkeypatch) -> None:
    """Layer: integration. Verifies Phase 4 ledger API export, verification, partial views, audit, and gate traversal."""
    calls: list[str] = []

    def _fake_gate(payload: Any, config: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        calls.append(str((config or {}).get("surface") or ""))
        return payload, {"applied": True}

    monkeypatch.setattr(api_module, "apply_outbound_policy_gate", _fake_gate)
    client, db_path = _client(tmp_path, monkeypatch)
    try:
        run_id = _submit_and_approve(client)
        calls.clear()

        exported = client.get(f"/v1/runs/{run_id}/ledger", headers={"X-API-Key": "test-key"})
        verified = client.get(f"/v1/runs/{run_id}/ledger/verify", headers={"X-API-Key": "test-key"})
        filtered = client.get(
            f"/v1/runs/{run_id}/ledger",
            headers={"X-API-Key": "test-key"},
            params={"types": "proposals,decisions"},
        )
        include_pii = client.get(
            f"/v1/runs/{run_id}/ledger",
            headers={"X-API-Key": "test-key"},
            params={"include_pii": True},
        )

        assert exported.status_code == 200
        assert exported.json()["schema_version"] == "ledger_export.v1"
        assert exported.json()["export_scope"] == "all"
        assert exported.json()["verification"]["result"] == "valid"
        assert verified.status_code == 200
        assert verified.json()["result"] == "valid"
        assert filtered.status_code == 200
        assert filtered.json()["export_scope"] == "partial_view"
        assert filtered.json()["verification"]["result"] == "partial_valid"
        assert include_pii.status_code == 200
        audit = [event for event in include_pii.json()["events"] if event["event_type"] == "ledger_export_requested"]
        assert audit
        assert audit[0]["event_group"] == "audit"
        assert "api.runs.ledger" in calls
        assert "api.runs.ledger.verify" in calls
    finally:
        client.close()

    events = await OutwardRunEventStore(db_path).list_for_run("run-phase4-api")
    assert events[-1].event_type == "ledger_export_requested"
