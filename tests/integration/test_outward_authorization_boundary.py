"""BT-0 acceptance counterexamples. Failures are open defects, never expected passes."""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from tests.helpers.outward_authorization import (
    SequenceModelClient,
    approve,
    approve_in_new_process,
    hold_decision_writers,
    outward_api,
    submit_sequence,
)
from tests.helpers.outward_authorization import boundary as boundary


@pytest.mark.integration
@pytest.mark.parametrize("restart", ["same-app", "reopened-app", "new-process"])
@pytest.mark.parametrize("endpoint", ["approve", "decision"])
# Layer: integration
async def test_old_same_tool_approval_cannot_execute_pending_second_write(tmp_path, boundary, restart, endpoint):
    """Layer: integration. SR-01: authenticated retries cannot consume another turn's call."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, _context):
        first = await submit_sequence(client, calls)
        response = await approve(client, first, endpoint=endpoint)
        assert response.status_code == 200, response.text
        before = await OutwardRunStore(db_path).get("bt0-run")
        second = (await OutwardApprovalStore(db_path).list(status="pending"))[0]
        assert second.proposal_id != first and second.tool == calls[0]["tool"]
        assert before.status == "approval_required" and before.current_turn == 2
        assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == calls[0]["args"]["content"]
        assert not (tmp_path / "second.txt").exists()
        if restart == "same-app":
            repeated = await approve(client, first, endpoint=endpoint)
            repeated_status, repeated_payload = repeated.status_code, repeated.json()
    if restart == "reopened-app":
        async with outward_api(tmp_path, inputs) as (client, _context):
            repeated = await approve(client, first, endpoint=endpoint)
            repeated_status, repeated_payload = repeated.status_code, repeated.json()
    elif restart == "new-process":
        repeated_status, repeated_payload = await approve_in_new_process(tmp_path, first, endpoint)
    after = await OutwardRunStore(db_path).get("bt0-run")
    events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
    second_exists = (tmp_path / "second.txt").exists()
    observation = {
        "second_file_exists": second_exists,
        "second_content": await asyncio.to_thread((tmp_path / "second.txt").read_text) if second_exists else None,
        "first_content": await asyncio.to_thread((tmp_path / "first.txt").read_text),
        "run_status": after.status,
        "turn": after.current_turn,
        "pending_status": (await OutwardApprovalStore(db_path).get(second.proposal_id)).status,
        "tool_events": len([event for event in events if event.event_type == "tool_invoked"]),
    }
    assert repeated_status == 200 and repeated_payload == response.json()
    assert observation == {
        "second_file_exists": False, "run_status": "approval_required", "turn": 2,
        "pending_status": "pending", "tool_events": 1,
        "second_content": None, "first_content": calls[0]["args"]["content"],
    }, f"SR-01: old approval selected a different effect: {observation}"


@pytest.mark.integration
@pytest.mark.parametrize("offset", [-1, 0, 1], ids=["before", "at", "after"])
# Layer: integration
async def test_direct_approval_enforces_expiry_without_queue_reads(tmp_path, boundary, offset):
    """Layer: integration. SR-04: direct approval enforces now >= expires_at without a queue read."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls[:1], approval_seconds=10)
        inputs.now += timedelta(seconds=10 + offset)
        response = await approve(client, proposal_id)
        assert response.status_code == 200, response.text
    proposal = await OutwardApprovalStore(db_path).get(proposal_id)
    events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
    observation = {
        "status": proposal.status,
        "file_exists": (tmp_path / "first.txt").exists(),
        "tool_events": len([event for event in events if event.event_type == "tool_invoked"]),
    }
    allowed = offset < 0
    assert observation == {
        "status": "approved" if allowed else "expired",
        "file_exists": allowed, "tool_events": int(allowed),
    }, f"SR-04: expired authorization dispatched: {observation}"


@pytest.mark.integration
# Layer: integration
async def test_unauthenticated_approval_cannot_decide_or_dispatch(tmp_path, boundary):
    """Layer: integration. Healthy control: real API authentication denies mutation."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls[:1])
        before = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
        response = await client.post(
            f"/v1/approvals/{proposal_id}/approve", json={}, headers={"X-API-Key": "invalid-test-key"}
        )
        assert response.status_code in {401, 403}, response.text
    assert (await OutwardApprovalStore(db_path).get(proposal_id)).status == "pending"
    assert await OutwardRunEventStore(db_path).list_for_run("bt0-run") == before
    assert not (tmp_path / "first.txt").exists()


@pytest.mark.integration
# Layer: integration
async def test_approve_deny_race_has_one_durable_decision(tmp_path, boundary, monkeypatch):
    """Layer: integration. SR-03: concurrent HTTP decisions wait on a real SQLite writer lock."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls[:1])
        tasks = []
        try:
            async with hold_decision_writers(db_path, monkeypatch) as waiting:
                tasks = [asyncio.create_task(approve(client, proposal_id)), asyncio.create_task(
                    client.post(f"/v1/approvals/{proposal_id}/deny", json={"reason": "race denial"}),
                )]
                await asyncio.wait_for(waiting.wait(), timeout=4)
            approved, denied = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    row = await OutwardApprovalStore(db_path).get(proposal_id)
    run = await OutwardRunStore(db_path).get("bt0-run")
    events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
    decisions = [event.event_type for event in events if event.event_type in {"proposal_approved", "proposal_denied"}]
    responses = [approved, denied]
    acknowledgements = [response.json()["approval"]["status"] for response in responses if response.status_code == 200]
    observation = {"http": [response.status_code for response in responses], "acks": acknowledgements,
                   "stored": row.status, "events": decisions, "run": run.status}
    assert all(response.status_code in {200, 409} for response in responses), observation
    assert set(acknowledgements) == {row.status} and len(decisions) == 1, f"SR-03: contradictory decisions: {observation}"
    assert decisions == [f"proposal_{row.status}"], observation
    if row.status == "denied":
        assert not (tmp_path / "first.txt").exists(), observation


@pytest.mark.integration
# Layer: integration
async def test_concurrent_approved_retries_execute_at_most_one_command(tmp_path, boundary, monkeypatch):
    """Layer: integration. SR-02: overlapping authenticated retries have one actual append effect."""
    db_path, inputs, _calls = boundary
    script = "from pathlib import Path; p=Path('effects.txt'); f=p.open('a'); f.write('effect\\n'); f.close()"
    calls = [{"tool": "run_command", "args": {"command": [sys.executable, "-c", script]}}]
    import orket.application.services.outward_model_tool_call_service as model_module

    monkeypatch.setattr(model_module, "create_configured_model_client", lambda: SequenceModelClient(calls))
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls)
        await context.outward_approval_service.approve(proposal_id, operator_ref="operator:fixture")
        responses = await _overlap_retries(client, context, proposal_id, monkeypatch)
    effects = await asyncio.to_thread((tmp_path / "effects.txt").read_text)
    events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
    count = len([event for event in events if event.event_type == "tool_invoked"])
    observation = {"effects": effects.splitlines(), "tool_events": count,
                   "http": [response.status_code for response in responses]}
    assert observation["effects"] == ["effect"] and count == 1, f"SR-02: {observation}"
    assert all(response.status_code in {200, 409} for response in responses), observation


async def _overlap_retries(client, context, proposal_id, monkeypatch):
    """Hold the first real connector until the second request reads its live run."""
    entered, second_read, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    connector = context.outward_run_execution_service.connector_service
    invoke, get_run = connector.invoke_with_result, context.outward_run_store.get

    async def held_invoke(*args, **kwargs):
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=10)
        return await invoke(*args, **kwargs)

    async def observed_read(key, **kwargs):
        row = await get_run(key, **kwargs)
        if entered.is_set():
            second_read.set()
        return row

    monkeypatch.setattr(connector, "invoke_with_result", held_invoke)
    monkeypatch.setattr(context.outward_run_store, "get", observed_read)
    first = asyncio.create_task(approve(client, proposal_id))
    tasks = [first]
    try:
        await asyncio.wait_for(entered.wait(), timeout=10)
        second = asyncio.create_task(approve(client, proposal_id))
        tasks.append(second)
        read_wait = asyncio.create_task(second_read.wait())
        tasks.append(read_wait)
        done, _pending = await asyncio.wait([read_wait, second], timeout=10, return_when=asyncio.FIRST_COMPLETED)
        assert done, "Second request did not reach the overlapping decision boundary"
        release.set()
        return await asyncio.wait_for(asyncio.gather(first, second), timeout=15)
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
