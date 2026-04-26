from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore


def _client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    db_path = tmp_path / "phase3-control-plane.sqlite3"
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(db_path))
    return TestClient(api_module.create_api_app(project_root=tmp_path)), str(db_path)


def _submit_and_approve(client: TestClient) -> str:
    submitted = client.post(
        "/v1/runs",
        headers={"X-API-Key": "test-key"},
        json={
            "run_id": "run-phase3-api",
            "task": {
                "description": "Write file",
                "instruction": "Call write_file",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "phase3.txt", "content": "phase3"},
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
    return "run-phase3-api"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_phase3_events_summary_stream_and_gate_are_read_only(tmp_path, monkeypatch) -> None:
    """Layer: integration. Verifies Phase 3 inspection APIs filter, summarize, stream, and stay read-only."""
    calls: list[str] = []

    def _fake_gate(payload: Any, config: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        calls.append(str((config or {}).get("surface") or ""))
        return payload, {"applied": True}

    monkeypatch.setattr(api_module, "apply_outbound_policy_gate", _fake_gate)
    client, db_path = _client(tmp_path, monkeypatch)
    try:
        run_id = _submit_and_approve(client)
        calls.clear()
        before_events = await OutwardRunEventStore(db_path).list_for_run(run_id)
        before_run = await OutwardRunStore(db_path).get(run_id)

        events = client.get(f"/v1/runs/{run_id}/events", headers={"X-API-Key": "test-key"})
        filtered = client.get(
            f"/v1/runs/{run_id}/events",
            headers={"X-API-Key": "test-key"},
            params={"types": "tool_invoked", "from_turn": 1},
        )
        summary = client.get(f"/v1/runs/{run_id}/summary", headers={"X-API-Key": "test-key"})
        stream = client.get(f"/v1/runs/{run_id}/events/stream", headers={"X-API-Key": "test-key"})

        assert events.status_code == 200
        assert events.json()["count"] == len(before_events)
        assert filtered.json()["count"] == 1
        assert filtered.json()["events"][0]["event_type"] == "tool_invoked"
        assert summary.status_code == 200
        assert summary.json()["event_count"] == len(before_events)
        assert summary.json()["event_counts"]["run_completed"] == 1
        assert stream.status_code == 200
        assert "event: run_event" in stream.text
        assert "run_completed" in stream.text
        assert "api.runs.events" in calls
        assert "api.runs.summary" in calls
        assert "api.runs.events.stream" in calls
    finally:
        client.close()

    after_events = await OutwardRunEventStore(db_path).list_for_run(run_id)
    after_run = await OutwardRunStore(db_path).get(run_id)
    assert len(after_events) == len(before_events)
    assert before_run is not None
    assert after_run is not None
    assert after_run.status == before_run.status
