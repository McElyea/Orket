from __future__ import annotations

from fastapi.testclient import TestClient

from orket.interfaces.api import app
import orket.interfaces.api as api_module
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests


client = TestClient(app)


def test_list_approvals_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_list_approvals(*, status=None, session_id=None, request_id=None, limit=100):
        captured["status"] = status
        captured["session_id"] = session_id
        captured["request_id"] = request_id
        captured["limit"] = limit
        return [{"approval_id": "abc123", "status": "PENDING"}]

    monkeypatch.setattr(api_module.engine, "list_approvals", fake_list_approvals)

    response = client.get(
        "/v1/approvals?status=PENDING&session_id=sess-1&request_id=req-1&limit=20",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["approval_id"] == "abc123"
    assert captured == {
        "status": "PENDING",
        "session_id": "sess-1",
        "request_id": "req-1",
        "limit": 20,
    }


def test_get_approval_returns_404_when_missing(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_approval(_approval_id: str):
        return None

    monkeypatch.setattr(api_module.engine, "get_approval", fake_get_approval)
    response = client.get("/v1/approvals/missing", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_decide_approval_returns_409_on_conflict(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_decide_approval(*, approval_id: str, decision: str, edited_proposal=None, notes=None):
        _ = approval_id, decision, edited_proposal, notes
        raise RuntimeError("approval already resolved with a conflicting decision")

    monkeypatch.setattr(api_module.engine, "decide_approval", fake_decide_approval)
    response = client.post(
        "/v1/approvals/abc123/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve"},
    )
    assert response.status_code == 409


def test_decide_approval_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_decide_approval(*, approval_id: str, decision: str, edited_proposal=None, notes=None):
        captured["approval_id"] = approval_id
        captured["decision"] = decision
        captured["edited_proposal"] = edited_proposal
        captured["notes"] = notes
        return {"status": "resolved", "approval": {"approval_id": approval_id, "status": "APPROVED"}}

    monkeypatch.setattr(api_module.engine, "decide_approval", fake_decide_approval)
    response = client.post(
        "/v1/approvals/abc123/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve", "notes": "safe", "edited_proposal": {"path": "a.txt"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert captured == {
        "approval_id": "abc123",
        "decision": "approve",
        "edited_proposal": {"path": "a.txt"},
        "notes": "safe",
    }


def test_approvals_endpoints_real_nervous_system_flow(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    reset_runtime_state_for_tests()

    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-api-approvals-real-1",
            "trace_id": "trace-api-approvals-real-1",
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        },
    )
    assert admitted.status_code == 200
    approval_id = admitted.json()["approval_id"]

    listed = client.get(
        "/v1/approvals?status=PENDING&session_id=sess-api-approvals-real-1",
        headers={"X-API-Key": "test-key"},
    )
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1
    assert any(item["approval_id"] == approval_id for item in listed.json()["items"])

    decided = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve", "notes": "api-approved"},
    )
    assert decided.status_code == 200
    assert decided.json()["approval"]["status"] == "APPROVED"
