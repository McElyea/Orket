# Layer: end-to-end

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orket.interfaces.api import create_api_app
from orket_extension_sdk.agent_fixtures import prefixed_digest
from orket_extension_sdk.agent_testing import ticket_report_fixture
from tests.e2e.test_governed_agent_supervisor_ollama import (
    _configure_api,
    _headers,
    _receipts,
    _wait_for_terminal_wake,
    _wake_payload,
    _write_catalog,
)


@pytest.mark.end_to_end
@pytest.mark.skipif(
    os.getenv("ORKET_RUN_LIVE_AGENT_OLLAMA") != "1",
    reason="set ORKET_RUN_LIVE_AGENT_OLLAMA=1 for live Ollama proof",
)
@pytest.mark.parametrize("decision", ["approved", "denied"])
def test_live_effect_resolution_survives_restart_and_replay(tmp_path, monkeypatch, decision):
    """Layer: end-to-end. Real models, child, effects and durable API restarts; no provider mocks."""
    planner = os.getenv("ORKET_GOVERNED_AGENT_PLANNER_MODEL", "qwen2.5:7b")
    actor = os.getenv("ORKET_GOVERNED_AGENT_ACTOR_MODEL", "qwen2.5-coder:7b")
    critic = os.getenv("ORKET_GOVERNED_AGENT_CRITIC_MODEL", planner)
    _configure_api(
        monkeypatch,
        db_path=tmp_path / "agent.sqlite3",
        catalog_path=_write_catalog(tmp_path),
        planner=planner,
        actor=actor,
        critic=critic,
    )
    source = tmp_path / "inputs" / "tickets.json"
    source.parent.mkdir()
    source.write_text(json.dumps(ticket_report_fixture()["batches"]), encoding="utf-8")
    payload = _effect_payload()
    report = tmp_path / "reports" / "ticket-report.json"
    blocked = _pause_for_approval(tmp_path, payload, report)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", "0")
    resolution = _resolve_after_restart(tmp_path, blocked, payload, decision)
    if decision == "approved":
        assert json.loads(report.read_text(encoding="utf-8")) == ticket_report_fixture()["expected_report"]
        monkeypatch.setenv("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", "1")
    final_app = create_api_app(project_root=tmp_path)
    with TestClient(final_app) as client:
        if decision == "approved":
            wake = _wait_for_terminal_wake(client, resolution["wake"]["wake_id"])
            assert wake["state"] == "completed", wake
        final = _inspect(client)
        _assert_terminal(final, decision, report)
        replay = client.get("/v1/agent-runs/run-1/replay", headers=_headers())
        assert replay.status_code == 200 and replay.json()["status"] == "matched", replay.json()
        assert _inspect(client) == final
        receipts = _receipts(final)
        assert {r["role"]: r["model"] for r in receipts} == {
            "planner": planner,
            "actor": actor,
            "critic": critic,
        }
        assert len({r["model"] for r in receipts}) >= 2
        assert all(r["usage_posture"] == "measured" and r["status"] == "returned" for r in receipts)
    assert final_app.state.api_runtime_context.active_background_task_count == 0
    _print_evidence(decision, final, receipts)


def _print_evidence(decision: str, final: dict, receipts: list[dict]) -> None:
    print(
        json.dumps(
            {
                "decision": decision,
                "run_id": "run-1",
                "path": "primary",
                "result": "success",
                "state": final["run"]["lifecycle_state"],
                "receipts": receipts,
                "replay": "matched and non-mutating",
                "background_tasks": 0,
            }
        )
    )


def _pause_for_approval(tmp_path: Path, payload: dict, report: Path) -> dict:
    app = create_api_app(project_root=tmp_path)
    with TestClient(app) as client:
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=payload)
        assert admitted.status_code == 202, admitted.json()
        wake = _wait_for_terminal_wake(client, admitted.json()["wake"]["wake_id"])
        assert wake["state"] == "completed", wake
        blocked = _inspect(client)
        assert blocked["run"]["lifecycle_state"] == "operator_blocked", blocked
        assert len(blocked["effects"]) == 1
        assert blocked["approvals"][0]["status"] == "pending"
        assert not report.exists()
    assert app.state.api_runtime_context.active_background_task_count == 0
    return blocked


def _resolve_after_restart(tmp_path: Path, blocked: dict, payload: dict, decision: str) -> dict:
    deadline = datetime.fromisoformat(payload["dispatch"]["request"]["deadline_utc"])
    resolution = {
        "decision": decision,
        "actor_ref": "operator:live-effect-proof",
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    if decision == "approved":
        resolution.update(
            {
                "next_lease_expires_at_utc": (deadline - timedelta(seconds=1)).isoformat(),
                "decision_timestamps_utc": [(deadline - timedelta(seconds=2)).isoformat()],
                "next_lease_expiries_utc": [],
            }
        )
    app = create_api_app(project_root=tmp_path)
    route = f"/v1/agent-runs/run-1/effects/{blocked['approvals'][0]['request_id']}/resolve"
    with TestClient(app) as client:
        assert _inspect(client) == blocked
        assert client.post(route, json=resolution).status_code == 403
        response = client.post(route, headers=_headers(), json=resolution)
        assert response.status_code == 200, response.json()
        body = response.json()
        if decision == "approved":
            assert body["status"] == "resume_queued" and body["wake_status"] == "enqueued"
            repeated = client.post(route, headers=_headers(), json=resolution)
            assert repeated.status_code == 200, repeated.json()
            assert repeated.json()["wake_status"] == "idempotent"
            assert repeated.json()["wake"]["wake_id"] == body["wake"]["wake_id"]
            assert _inspect(client)["run"]["lifecycle_state"] == "operator_blocked"
        else:
            assert body["status"] == "denied" and body["wake"] is None
    assert app.state.api_runtime_context.active_background_task_count == 0
    return body


def _assert_terminal(inspection: dict, decision: str, report: Path) -> None:
    if decision == "approved":
        assert inspection["run"]["lifecycle_state"] == "completed", inspection
        assert inspection["final_truth"] is not None
        assert len(inspection["effects"]) == 2 and len(inspection["wakes"]) == 2
        assert any(
            item["checkpoint"]["checkpoint_id"].startswith("agent-post-effects-checkpoint:")
            and item["acceptance"]["outcome"] == "checkpoint_accepted"
            for item in inspection["checkpoints"]
        )
        assert any(item["result"] == "resume_authorized" for item in inspection["operator_actions"])
        assert json.loads(report.read_text(encoding="utf-8")) == ticket_report_fixture()["expected_report"]
    else:
        assert inspection["run"]["lifecycle_state"] == "failed_terminal", inspection
        assert len(inspection["effects"]) == 1 and len(inspection["wakes"]) == 1
        assert not report.exists()


def _inspect(client: TestClient) -> dict:
    response = client.get("/v1/agent-runs/run-1", headers=_headers())
    assert response.status_code == 200, response.json()
    return response.json()


def _effect_payload() -> dict:
    payload = _wake_payload()
    request = payload["dispatch"]["request"]
    request["namespace_scope"] = ["issue:issue-1"]
    request["admitted_capabilities"] = ["agent.iteration.v1", "read_file", "write_file"]
    request["extension_config"] = {
        "effect_demo": {
            "enabled": True,
            "proposal_iteration": 2,
            "namespace": "issue:issue-1",
            "read_path": "inputs/tickets.json",
            "write_path": "reports/ticket-report.json",
        }
    }
    deadline = datetime.fromisoformat(request["deadline_utc"])
    payload["dispatch"]["decision_timestamps_utc"].append((deadline - timedelta(seconds=3)).isoformat())
    payload["dispatch"]["next_lease_expiries_utc"].append((deadline - timedelta(seconds=1)).isoformat())
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        budget = request[scope]
        if scope == "remaining_run_budget":
            budget["iterations"] = 3
            for field in ("model_calls", "input_tokens", "output_tokens", "repair_attempts"):
                budget[field] = budget[field] * 3 // 2
            for counter in budget["per_role_model_calls"]:
                counter["count"] = counter["count"] * 3 // 2
        budget["per_capability_effects"] = [
            {"capability": "read_file", "count": 1},
            {"capability": "write_file", "count": 1},
        ]
        budget["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in budget.items() if key != "snapshot_digest"}
        )
    return payload
