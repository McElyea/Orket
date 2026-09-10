# Layer: integration; API, real child/broker, deterministic model provider, SQLite restart
from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from orket.application.services.governed_agent_fixture import DeterministicAgentModelProvider
from orket.interfaces.api import create_api_app
from tests.interfaces.test_governed_agent_api import (
    _configure_api,
    _headers,
    _wait_for_completed_wake,
    _wake_payload,
    _write_catalog,
)
from tests.runtime.governed_agent_test_support import ticket_continuation_inputs

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("command", ["pause", "stop"])
def test_operator_control_is_consumed_before_next_iteration(tmp_path, monkeypatch, command):
    """Layer: integration. Requested pause/stop survives the current call and remains durable across restart."""
    entered, release = threading.Event(), threading.Event()
    original = DeterministicAgentModelProvider.call

    async def controlled_call(self, *, request, profile):
        if request.identity.iteration_ordinal == 1 and request.role == "planner":
            entered.set()
            assert await asyncio.to_thread(release.wait, 10)
        return await original(self, request=request, profile=profile)

    monkeypatch.setattr(DeterministicAgentModelProvider, "call", controlled_call)
    _configure_api(monkeypatch, tmp_path / "agent.sqlite3", enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(_write_catalog(tmp_path)))
    payload = _wake_payload()
    request = payload["dispatch"]["request"]
    request["authoritative_context_refs"] = ["artifact:ticket-batch-a"]
    request["materialized_inputs"] = [item for item in request["materialized_inputs"]
                                      if item["reference"] != "artifact:ticket-batch-b"]
    payload["dispatch"]["continuation_inputs"] = ticket_continuation_inputs()
    action = {"action_id": f"operator:{command}", "actor_ref": "operator:test",
              "timestamp_utc": datetime.now(UTC).isoformat(), "invocation_id": "invocation-1", "command": command}
    app = create_api_app(project_root=tmp_path)
    with TestClient(app) as client:
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=payload)
        try:
            assert admitted.status_code == 202 and entered.wait(8)
            assert client.post("/v1/agent-runs/run-1/controls", json=action).status_code == 403
            response = client.post("/v1/agent-runs/run-1/controls", headers=_headers(), json=action)
            assert response.status_code == 200 and response.json()["status"] == "requested"
            repeated = client.post("/v1/agent-runs/run-1/controls", headers=_headers(), json=action)
            assert repeated.json()["status"] == "idempotent"
        finally:
            release.set()
        _wait_for_completed_wake(client, admitted.json()["wake"]["wake_id"])
        inspected = client.get("/v1/agent-runs/run-1", headers=_headers()).json()
        assert len(inspected["iterations"]) == 1
        assert inspected["iterations"][0]["decision"]["rule"] == (
            "accepted_operator_pause" if command == "pause" else "accepted_terminal_stop")
        late = {**action, "action_id": "operator:late"}
        assert client.post("/v1/agent-runs/run-1/controls", headers=_headers(), json=late).status_code == 409
    assert app.state.api_runtime_context.active_background_task_count == 0
    if command == "pause":
        _resume_after_restart(tmp_path, request, monkeypatch)
    else:
        assert inspected["run"]["lifecycle_state"] == "failed_terminal"
        assert inspected["final_truth"]["closure_basis"] == "operator_terminal_stop"
        assert inspected["final_truth"]["result_class"] == "blocked"


def _resume_after_restart(tmp_path, request, monkeypatch):
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", "0")
    deadline = datetime.fromisoformat(request["deadline_utc"])
    payload = {"actor_ref": "operator:test", "timestamp_utc": datetime.now(UTC).isoformat(),
               "next_lease_expires_at_utc": (deadline - timedelta(seconds=1)).isoformat(),
               "decision_timestamps_utc": [(deadline - timedelta(seconds=2)).isoformat()],
               "next_lease_expiries_utc": []}
    app = create_api_app(project_root=tmp_path)
    with TestClient(app) as client:
        response = client.post("/v1/agent-runs/run-1/resume", headers=_headers(), json=payload)
        assert response.status_code == 200, response.json()
        wake = response.json()["wake"]["wake_id"]
        assert client.get("/v1/agent-runs/run-1", headers=_headers()).json()["run"]["lifecycle_state"] == "operator_blocked"
    assert app.state.api_runtime_context.active_background_task_count == 0
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", "1")
    app = create_api_app(project_root=tmp_path)
    with TestClient(app) as client:
        _wait_for_completed_wake(client, wake)
        inspected = client.get("/v1/agent-runs/run-1", headers=_headers()).json()
        assert inspected["run"]["lifecycle_state"] == "completed", inspected
        assert len(inspected["iterations"]) == 2
        assert client.get("/v1/agent-runs/run-1/replay", headers=_headers()).json()["status"] == "matched"
        assert client.get("/v1/agent-runs/run-1", headers=_headers()).json() == inspected
    assert app.state.api_runtime_context.active_background_task_count == 0
