from __future__ import annotations

import pytest

from orket.orchestration.engine import OrchestrationEngine
from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests


class _FakePendingGates:
    def __init__(self) -> None:
        self.rows = [
            {
                "request_id": "apr-1",
                "session_id": "sess-1",
                "issue_id": "ISS-1",
                "seat_name": "coder",
                "gate_mode": "approval_required",
                "request_type": "tool_approval",
                "reason": "approval_required_tool:write_file",
                "payload_json": {"tool": "write_file"},
                "status": "pending",
                "resolution_json": {},
                "created_at": "2026-03-03T12:00:00+00:00",
                "updated_at": "2026-03-03T12:00:00+00:00",
                "resolved_at": None,
            }
        ]

    async def list_requests(self, *, session_id=None, status=None, limit=100):
        rows = list(self.rows)
        if session_id:
            rows = [row for row in rows if row["session_id"] == session_id]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return rows[: max(1, int(limit))]

    async def resolve_request(self, *, request_id: str, status: str, resolution=None) -> None:
        for row in self.rows:
            if row["request_id"] == request_id:
                row["status"] = status
                row["resolution_json"] = dict(resolution or {})
                row["resolved_at"] = "2026-03-03T12:01:00+00:00"
                return
        raise RuntimeError("request not found")


def _make_engine() -> OrchestrationEngine:
    engine = object.__new__(OrchestrationEngine)
    engine.pending_gates = _FakePendingGates()
    return engine


@pytest.mark.asyncio
async def test_engine_list_approvals_normalizes_rows() -> None:
    engine = _make_engine()
    items = await engine.list_approvals(status="PENDING", session_id="sess-1", limit=10)
    assert len(items) == 1
    assert items[0]["approval_id"] == "apr-1"
    assert items[0]["status"] == "PENDING"


@pytest.mark.asyncio
async def test_engine_get_approval_returns_none_when_missing() -> None:
    engine = _make_engine()
    assert await engine.get_approval("missing") is None


@pytest.mark.asyncio
async def test_engine_decide_approval_resolves_pending_item() -> None:
    engine = _make_engine()
    result = await engine.decide_approval(approval_id="apr-1", decision="approve", notes="safe")
    assert result["status"] == "resolved"
    assert result["approval"]["status"] == "APPROVED"
    assert result["approval"]["resolution"]["decision"] == "approve"


@pytest.mark.asyncio
async def test_engine_decide_approval_conflict_after_resolution_raises() -> None:
    engine = _make_engine()
    await engine.decide_approval(approval_id="apr-1", decision="approve")
    with pytest.raises(RuntimeError):
        await engine.decide_approval(approval_id="apr-1", decision="deny")


@pytest.mark.asyncio
async def test_engine_approvals_use_nervous_system_runtime_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    reset_runtime_state_for_tests()
    admit_proposal_v1(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-ns-engine-1",
            "trace_id": "trace-ns-engine-1",
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        }
    )

    engine = object.__new__(OrchestrationEngine)
    items = await engine.list_approvals(status="PENDING", session_id="sess-ns-engine-1", limit=10)
    assert len(items) == 1
    approval_id = items[0]["approval_id"]

    resolved = await engine.decide_approval(approval_id=approval_id, decision="approve")
    assert resolved["approval"]["status"] == "APPROVED"
