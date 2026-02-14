import pytest

from orket.adapters.storage.async_repositories import AsyncPendingGateRepository


@pytest.mark.asyncio
async def test_pending_gate_request_create_list_and_resolve(db_path):
    repo = AsyncPendingGateRepository(db_path)

    request_id = await repo.create_request(
        session_id="run-1",
        issue_id="ISSUE-1",
        seat_name="integrity_guard",
        gate_mode="review_required",
        request_type="guard_rejection_payload",
        reason="missing_rationale",
        payload={"rationale": "", "remediation_actions": []},
    )

    assert request_id

    pending = await repo.list_requests(session_id="run-1", status="pending")
    assert len(pending) == 1
    assert pending[0]["request_id"] == request_id
    assert pending[0]["reason"] == "missing_rationale"
    assert pending[0]["status"] == "pending"

    await repo.resolve_request(
        request_id=request_id,
        status="resolved",
        resolution={"approved_by": "tester"},
    )

    resolved = await repo.list_requests(session_id="run-1", status="resolved")
    assert len(resolved) == 1
    assert resolved[0]["request_id"] == request_id
    assert resolved[0]["resolution_json"]["approved_by"] == "tester"
