import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.streaming.contracts import CommitIntent, StreamEventType


client = TestClient(api_module.app)


def test_interaction_websocket_requires_api_key(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/interactions/no-session"):
            pass


def test_interaction_stream_flow_emits_commit_final(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_run_workload(*, workload_id, input_config, workspace, department, interaction_context=None):
        if interaction_context is not None:
            await interaction_context.emit_event(
                StreamEventType.TOKEN_DELTA,
                {"delta": "hello", "authoritative": False},
            )
            await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload_id))
        return None

    monkeypatch.setattr(api_module.extension_manager, "run_workload", fake_run_workload)

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    with client.websocket_connect(f"/ws/interactions/{session_id}?api_key=test-key") as ws:
        turn = client.post(
            f"/v1/interactions/{session_id}/turns",
            headers={"X-API-Key": "test-key"},
            json={"workload_id": "mystery_v1", "input_config": {"seed": 123}},
        )
        assert turn.status_code == 200
        events = [ws.receive_json() for _ in range(4)]
        event_types = [item["event_type"] for item in events]
        assert "turn_accepted" in event_types
        assert "turn_final" in event_types
        assert "commit_final" in event_types
