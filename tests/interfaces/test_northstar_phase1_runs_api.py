from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore


def _client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    db_path = tmp_path / "phase1-control-plane.sqlite3"
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(db_path))
    return TestClient(api_module.create_api_app(project_root=tmp_path)), str(db_path)


@pytest.mark.integration
def test_run_submit_status_list_and_idempotency(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies Phase 1 run API submission, status, list, and idempotency."""
    client, _db_path = _client(tmp_path, monkeypatch)
    try:
        payload = {
            "run_id": "run-api-phase1",
            "task": {"description": "Demo", "instruction": "Do the work"},
            "policy_overrides": {"max_turns": 7},
        }

        submit_response = client.post("/v1/runs", headers={"X-API-Key": "test-key"}, json=payload)
        repeat_response = client.post("/v1/runs", headers={"X-API-Key": "test-key"}, json=payload)
        status_response = client.get("/v1/runs/run-api-phase1", headers={"X-API-Key": "test-key"})
        list_response = client.get("/v1/runs?status=queued", headers={"X-API-Key": "test-key"})

        assert submit_response.status_code == 200
        assert repeat_response.json() == submit_response.json()
        assert submit_response.headers["X-Orket-Version"] == api_module.__version__
        assert submit_response.json()["run_id"] == "run-api-phase1"
        assert submit_response.json()["status"] == "queued"
        assert submit_response.json()["namespace"] == "issue:run-api-phase1"
        assert submit_response.json()["max_turns"] == 7

        assert status_response.status_code == 200
        assert status_response.json() == submit_response.json()

        assert list_response.status_code == 200
        assert list_response.json()["items"] == [submit_response.json()]
    finally:
        client.close()


@pytest.mark.integration
def test_run_submit_missing_instruction_rejected(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies invalid work submission fails before execution."""
    client, _db_path = _client(tmp_path, monkeypatch)
    try:
        response = client.post(
            "/v1/runs",
            headers={"X-API-Key": "test-key"},
            json={"task": {"description": "Demo"}},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "task.instruction is required"
    finally:
        client.close()


@pytest.mark.integration
def test_run_api_payloads_traverse_outbound_policy_gate(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies submit, status, and list responses call the outbound gate before serialization."""
    calls: list[str] = []

    def _fake_gate(payload: Any, config: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        calls.append(str((config or {}).get("surface") or ""))
        return payload, {"applied": True}

    monkeypatch.setattr(api_module, "apply_outbound_policy_gate", _fake_gate)
    client, _db_path = _client(tmp_path, monkeypatch)
    try:
        payload = {
            "run_id": "run-gated-phase1",
            "task": {"description": "Demo", "instruction": "Do the work"},
        }

        assert client.post("/v1/runs", headers={"X-API-Key": "test-key"}, json=payload).status_code == 200
        assert client.get("/v1/runs/run-gated-phase1", headers={"X-API-Key": "test-key"}).status_code == 200
        assert client.get("/v1/runs?status=queued", headers={"X-API-Key": "test-key"}).status_code == 200

        assert calls == ["api.runs.submit", "api.runs.status", "api.runs.list"]
    finally:
        client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_submit_creates_initial_run_event(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies API submission creates the expected initial run_events row."""
    client, db_path = _client(tmp_path, monkeypatch)
    try:
        response = client.post(
            "/v1/runs",
            headers={"X-API-Key": "test-key"},
            json={"run_id": "run-event-phase1", "task": {"description": "Demo", "instruction": "Do the work"}},
        )
        assert response.status_code == 200
    finally:
        client.close()

    events = await OutwardRunEventStore(db_path).list_for_run("run-event-phase1")
    assert [event.event_type for event in events] == ["run_submitted"]
