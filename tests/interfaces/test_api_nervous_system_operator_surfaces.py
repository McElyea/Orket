from __future__ import annotations

from fastapi.testclient import TestClient

from orket.interfaces.api import app
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests


client = TestClient(app)


def test_kernel_operator_surfaces_cover_one_action_lifecycle(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_USE_TOOL_PROFILE_RESOLVER", "true")
    monkeypatch.delenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", raising=False)
    reset_runtime_state_for_tests()

    headers = {"X-API-Key": "test-key"}
    session_id = "sess-api-operator-surfaces"
    trace_id = "trace-api-operator-surfaces"

    projection = client.post(
        "/v1/kernel/projection-pack",
        headers=headers,
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "purpose": "action_path",
            "tool_context_summary": {"tool": "fs.write_patch"},
            "policy_context": {"mode": "strict"},
        },
    )
    assert projection.status_code == 200

    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers=headers,
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {
                    "tool_name": "fs.write_patch",
                    "args": {"path": "./workspace/notes.md", "patch": "ADD LINE hello"},
                },
            },
        },
    )
    assert admitted.status_code == 200
    admitted_payload = admitted.json()
    assert admitted_payload["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    assert admitted_payload["admission_decision"]["reason_codes"] == ["APPROVAL_REQUIRED_DESTRUCTIVE"]
    approval_id = admitted_payload["approval_id"]

    decided = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers=headers,
        json={"decision": "approve", "notes": "api-approved"},
    )
    assert decided.status_code == 200
    assert decided.json()["approval"]["status"] == "APPROVED"

    committed = client.post(
        "/v1/kernel/commit-proposal",
        headers=headers,
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": admitted_payload["proposal_digest"],
            "admission_decision_digest": admitted_payload["decision_digest"],
            "approval_id": approval_id,
            "execution_result_digest": "2" * 64,
        },
    )
    assert committed.status_code == 200
    assert committed.json()["status"] == "COMMITTED"

    approvals = client.get("/v1/approvals", headers=headers, params={"session_id": session_id, "limit": 20})
    ledger = client.get(
        "/v1/kernel/ledger-events",
        headers=headers,
        params={"session_id": session_id, "trace_id": trace_id, "limit": 200},
    )
    rebuild = client.post("/v1/kernel/approvals/rebuild", headers=headers, json={"session_id": session_id})
    replay = client.get(
        "/v1/kernel/action-lifecycle/replay",
        headers=headers,
        params={"session_id": session_id, "trace_id": trace_id},
    )
    audit = client.get(
        "/v1/kernel/action-lifecycle/audit",
        headers=headers,
        params={"session_id": session_id, "trace_id": trace_id},
    )

    assert approvals.status_code == 200
    assert ledger.status_code == 200
    assert rebuild.status_code == 200
    assert replay.status_code == 200
    assert audit.status_code == 200

    approval_rows = [
        row
        for row in list(approvals.json().get("items") or [])
        if row.get("approval_id") == approval_id
    ]
    assert approval_rows
    assert approval_rows[0]["status"] == "APPROVED"

    event_types = {str(row.get("event_type") or "") for row in list(ledger.json().get("items") or [])}
    assert {
        "projection.issued",
        "proposal.received",
        "admission.decided",
        "approval.requested",
        "approval.decided",
        "commit.recorded",
    }.issubset(event_types)
    assert "action.executed" not in event_types
    assert "action.result_validated" not in event_types

    assert rebuild.json()["count"] == 0

    replay_payload = replay.json()
    assert replay_payload["decision_summary"]["admission_decision"] == "NEEDS_APPROVAL"
    assert replay_payload["decision_summary"]["approval_status"] == "APPROVED"
    assert replay_payload["decision_summary"]["commit_status"] == "COMMITTED"
    assert replay_payload["execution_summary"]["execution_claimed"] is True
    assert replay_payload["execution_summary"]["executed"] is False
    assert replay_payload["execution_summary"]["validated"] is False
    assert replay_payload["execution_summary"]["evidence_status"] == "claimed_only"

    audit_payload = audit.json()
    checks = {str(row.get("check") or ""): bool(row.get("ok")) for row in list(audit_payload.get("checks") or [])}
    assert audit_payload["ok"] is True
    assert checks["approval_path_complete"] is True
    assert checks["execution_path_consistent"] is True
    assert checks["approval_queue_rebuild_consistent"] is True
