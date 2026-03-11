# Layer: contract

from __future__ import annotations

from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.interfaces.api import app


client = TestClient(app)


def test_sandbox_operator_list_exposes_required_lifecycle_fields(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_sandboxes():
        return [
            {
                "sandbox_id": "sb-1",
                "compose_project": "orket-sandbox-sb-1",
                "state": "active",
                "cleanup_state": "none",
                "terminal_reason": None,
                "owner_instance_id": "runner-a",
                "cleanup_owner_instance_id": None,
                "lease_expires_at": "2026-03-11T00:05:00+00:00",
                "heartbeat_age_seconds": 12,
                "restart_summary": {},
                "cleanup_eligible": False,
                "cleanup_due_at": None,
                "requires_reconciliation": False,
            }
        ]

    monkeypatch.setattr(api_module.engine, "get_sandboxes", fake_get_sandboxes)

    response = client.get("/v1/sandboxes", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200
    body = response.json()
    assert body[0]["sandbox_id"] == "sb-1"
    assert sorted(body[0].keys()) == sorted(
        [
            "sandbox_id",
            "compose_project",
            "state",
            "cleanup_state",
            "terminal_reason",
            "owner_instance_id",
            "cleanup_owner_instance_id",
            "lease_expires_at",
            "heartbeat_age_seconds",
            "restart_summary",
            "cleanup_eligible",
            "cleanup_due_at",
            "requires_reconciliation",
        ]
    )


def test_sandbox_operator_stop_returns_conflict_when_reconciliation_blocked(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_stop_sandbox(_sandbox_id):
        raise ValueError("Sandbox sb-2 is blocked by requires_reconciliation=true")

    monkeypatch.setattr(api_module.engine, "stop_sandbox", fake_stop_sandbox)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandbox_stop_invocation",
        lambda sandbox_id: {"method_name": "stop_sandbox", "args": [sandbox_id]},
    )

    response = client.post("/v1/sandboxes/sb-2/stop", headers={"X-API-Key": "test-key"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Sandbox sb-2 is blocked by requires_reconciliation=true"
