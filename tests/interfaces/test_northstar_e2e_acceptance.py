from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.core.domain.outward_ledger import verify_ledger_export
from tests.helpers.outward_model import patch_outward_model_client


class _FrozenRuntimeInputs:
    def __init__(self, now: str) -> None:
        self.now = _parse(now)

    def create_session_id(self) -> str:
        return "generated"

    def utc_now(self) -> datetime:
        return self.now

    def utc_now_iso(self) -> str:
        return self.utc_now().isoformat()

    def set(self, now: str) -> None:
        self.now = _parse(now)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    clock: _FrozenRuntimeInputs | None = None,
    model_args: dict[str, object] | None = None,
) -> TestClient:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(tmp_path / "northstar-e2e.sqlite3"))
    monkeypatch.delenv("ORKET_OUTBOUND_POLICY_CONFIG_PATH", raising=False)
    monkeypatch.delenv("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS", raising=False)
    monkeypatch.delenv("ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS", raising=False)
    monkeypatch.delenv("ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS", raising=False)
    if clock is not None:
        monkeypatch.setattr(
            api_module,
            "_build_api_runtime_host",
            lambda root: ApiRuntimeHostService(Path(root), runtime_inputs=clock),  # type: ignore[arg-type]
        )
    patch_outward_model_client(monkeypatch, args=model_args)
    return TestClient(api_module.create_api_app(project_root=tmp_path))


def _submit_write_run(
    client: TestClient,
    *,
    run_id: str,
    path: str,
    content: str,
    approval_timeout_seconds: int | None = None,
) -> None:
    policy_overrides: dict[str, object] = {"approval_required_tools": ["write_file"]}
    if approval_timeout_seconds is not None:
        policy_overrides["approval_timeout_seconds"] = approval_timeout_seconds
    response = client.post(
        "/v1/runs",
        headers={"X-API-Key": "test-key"},
        json={
            "run_id": run_id,
            "task": {
                "description": f"Write {path}",
                "instruction": "Call write_file",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": path, "content": content},
                    }
                },
            },
            "policy_overrides": policy_overrides,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approval_required"


def _pending_proposal_id(client: TestClient) -> str:
    response = client.get("/v1/approvals", headers={"X-API-Key": "test-key"}, params={"status": "pending"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    return str(items[0]["proposal_id"])


def _offline_verified_ledger(client: TestClient, run_id: str) -> dict:
    response = client.get(f"/v1/runs/{run_id}/ledger", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    ledger = response.json()
    verified = verify_ledger_export(ledger)
    assert verified["result"] == "valid"
    return ledger


@pytest.mark.end_to_end
def test_northstar_e2e_acceptance_approval_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: end-to-end. Verifies submit -> approve -> effect -> inspect -> export -> offline verify."""
    client = _client(tmp_path, monkeypatch, model_args={"path": "approved.txt", "content": "approved"})
    target = tmp_path / "approved.txt"
    try:
        _submit_write_run(client, run_id="e2e-approval", path="approved.txt", content="approved")
        proposal_id = _pending_proposal_id(client)

        assert target.exists() is False
        approved = client.post(
            f"/v1/approvals/{proposal_id}/approve",
            headers={"X-API-Key": "test-key"},
            json={"note": "operator-reviewed"},
        )
        status = client.get("/v1/runs/e2e-approval", headers={"X-API-Key": "test-key"})
        events = client.get("/v1/runs/e2e-approval/events", headers={"X-API-Key": "test-key"})
        ledger = _offline_verified_ledger(client, "e2e-approval")

        assert approved.status_code == 200
        assert approved.json()["approval"]["status"] == "approved"
        assert status.json()["status"] == "completed"
        assert target.read_text(encoding="utf-8") == "approved"
        assert events.json()["count"] == ledger["summary"]["event_count"]
        assert "tool_invoked" in [event["event_type"] for event in ledger["events"]]
    finally:
        client.close()


@pytest.mark.end_to_end
def test_northstar_e2e_acceptance_denial_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: end-to-end. Verifies submit -> deny -> no effect -> completed run -> ledger offline verify."""
    client = _client(tmp_path, monkeypatch, model_args={"path": "denied.txt", "content": "denied"})
    target = tmp_path / "denied.txt"
    try:
        _submit_write_run(client, run_id="e2e-denial", path="denied.txt", content="denied")
        proposal_id = _pending_proposal_id(client)

        denied = client.post(
            f"/v1/approvals/{proposal_id}/deny",
            headers={"X-API-Key": "test-key"},
            json={"reason": "operator rejected"},
        )
        status = client.get("/v1/runs/e2e-denial", headers={"X-API-Key": "test-key"})
        ledger = _offline_verified_ledger(client, "e2e-denial")

        assert denied.status_code == 200
        assert denied.json()["approval"]["status"] == "denied"
        assert target.exists() is False
        assert status.json()["status"] == "completed"
        assert status.json()["stop_reason"] == "operator rejected"
        decision_events = [event for event in ledger["events"] if event["event_type"] == "proposal_denied"]
        assert decision_events
        assert decision_events[0]["payload"]["reason"] == "operator rejected"
    finally:
        client.close()


@pytest.mark.end_to_end
def test_northstar_e2e_acceptance_timeout_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: end-to-end. Verifies submit -> no operator action -> timeout deny -> ledger offline verify."""
    clock = _FrozenRuntimeInputs("2026-04-25T12:00:00+00:00")
    client = _client(tmp_path, monkeypatch, clock=clock, model_args={"path": "timeout.txt", "content": "timeout"})
    target = tmp_path / "timeout.txt"
    try:
        _submit_write_run(
            client,
            run_id="e2e-timeout",
            path="timeout.txt",
            content="timeout",
            approval_timeout_seconds=10,
        )
        assert _pending_proposal_id(client)
        assert target.exists() is False

        clock.set("2026-04-25T12:00:11+00:00")
        expired_queue = client.get("/v1/approvals", headers={"X-API-Key": "test-key"}, params={"status": "expired"})
        status = client.get("/v1/runs/e2e-timeout", headers={"X-API-Key": "test-key"})
        ledger = _offline_verified_ledger(client, "e2e-timeout")

        assert expired_queue.status_code == 200
        assert expired_queue.json()["items"][0]["status"] == "expired"
        assert target.exists() is False
        assert status.json()["status"] == "failed"
        assert status.json()["stop_reason"] == "timeout_exceeded"
        timeout_events = [event for event in ledger["events"] if event["event_type"] == "proposal_expired"]
        assert timeout_events
        assert timeout_events[0]["payload"]["operator_ref"] == "system:timeout"
        assert timeout_events[0]["payload"]["reason"] == "timeout_exceeded"
    finally:
        client.close()
