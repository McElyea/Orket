from __future__ import annotations

from fastapi.testclient import TestClient

from orket.interfaces.api import app
import orket.interfaces.api as api_module


client = TestClient(app)


def test_kernel_lifecycle_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    def fake_kernel_run_lifecycle(*, workflow_id, execute_turn_requests, finish_outcome="PASS", start_request=None):
        captured["workflow_id"] = workflow_id
        captured["execute_turn_requests"] = execute_turn_requests
        captured["finish_outcome"] = finish_outcome
        captured["start_request"] = start_request
        return {"ok": True, "workflow_id": workflow_id}

    monkeypatch.setattr(api_module.engine, "kernel_run_lifecycle", fake_kernel_run_lifecycle)

    response = client.post(
        "/v1/kernel/lifecycle",
        headers={"X-API-Key": "test-key"},
        json={
            "workflow_id": "wf-api-kernel",
            "execute_turn_requests": [{"turn_id": "turn-0001", "turn_input": {}, "commit_intent": "stage_only"}],
            "finish_outcome": "PASS",
            "start_request": {"visibility_mode": "local_only"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "workflow_id": "wf-api-kernel"}
    assert captured["workflow_id"] == "wf-api-kernel"
    assert captured["execute_turn_requests"][0]["turn_id"] == "turn-0001"
