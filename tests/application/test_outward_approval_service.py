from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_run_service import OutwardRunService


class _Clock:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now


async def _seed_run(db_path: Path, *, run_id: str = "run-approval") -> None:
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: run_id,
        utc_now=lambda: "2026-04-25T12:00:00+00:00",
    )
    await run_service.submit(
        {
            "run_id": run_id,
            "task": {"description": "Write file", "instruction": "Create the requested file"},
            "policy_overrides": {"approval_required_tools": ["write_file"], "max_turns": 5},
        }
    )


def _approval_service(db_path: Path, clock: _Clock) -> OutwardApprovalService:
    return OutwardApprovalService(
        approval_store=OutwardApprovalStore(db_path),
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=clock,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_approval_request_pauses_before_effect_and_approve_continues(tmp_path) -> None:
    """Layer: integration. Verifies approval-required write_file records a hold before any file effect."""
    db_path = tmp_path / "phase2.sqlite3"
    target = tmp_path / "target.txt"
    await _seed_run(db_path)
    service = _approval_service(db_path, _Clock("2026-04-25T12:01:00+00:00"))

    proposal = await service.request_tool_approval(
        run_id="run-approval",
        tool="write_file",
        args={"path": str(target), "content": "secret output"},
        context_summary="write requested by queued run",
    )

    assert target.exists() is False
    assert proposal.status == "pending"
    assert proposal.risk_level == "write"
    assert proposal.args_preview["content"] == "[REDACTED]"
    run = await OutwardRunStore(db_path).get("run-approval")
    assert run is not None
    assert run.status == "approval_required"
    assert run.pending_proposals[0]["proposal_id"] == proposal.proposal_id

    first = await service.approve(proposal.proposal_id, operator_ref="operator:test", note="ok")
    second = await service.approve(proposal.proposal_id, operator_ref="operator:test", note="ok again")

    assert second == first
    assert first.status == "approved"
    run_after = await OutwardRunStore(db_path).get("run-approval")
    assert run_after is not None
    assert run_after.status == "running"
    assert run_after.pending_proposals == ()

    events = await OutwardRunEventStore(db_path).list_for_run("run-approval")
    assert [event.event_type for event in events] == [
        "run_submitted",
        "proposal_pending_approval",
        "proposal_approved",
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_approval_deny_is_terminal_and_records_reason(tmp_path) -> None:
    """Layer: integration. Verifies denial fails the outward run and records the reason."""
    db_path = tmp_path / "phase2-deny.sqlite3"
    await _seed_run(db_path, run_id="run-deny")
    service = _approval_service(db_path, _Clock("2026-04-25T12:01:00+00:00"))

    proposal = await service.request_tool_approval(
        run_id="run-deny",
        tool="write_file",
        args={"path": "out.txt", "content": "x"},
        context_summary="operator review",
    )
    denied = await service.deny(proposal.proposal_id, operator_ref="operator:test", reason="not safe")

    assert denied.status == "denied"
    assert denied.reason == "not safe"
    run = await OutwardRunStore(db_path).get("run-deny")
    assert run is not None
    assert run.status == "failed"
    assert run.stop_reason == "not safe"
    events = await OutwardRunEventStore(db_path).list_for_run("run-deny")
    assert events[-1].event_type == "proposal_denied"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_approval_timeout_auto_denies(tmp_path) -> None:
    """Layer: integration. Verifies pending proposals expire into system timeout denial."""
    db_path = tmp_path / "phase2-timeout.sqlite3"
    await _seed_run(db_path, run_id="run-timeout")
    clock = _Clock("2026-04-25T12:01:00+00:00")
    service = _approval_service(db_path, clock)
    proposal = await service.request_tool_approval(
        run_id="run-timeout",
        tool="write_file",
        args={"path": "out.txt", "content": "x"},
        context_summary="operator review",
        timeout_seconds=1,
    )

    clock.now = "2026-04-25T12:01:02+00:00"
    expired = await service.expire_due()

    assert [item.proposal_id for item in expired] == [proposal.proposal_id]
    assert expired[0].status == "expired"
    assert expired[0].operator_ref == "system:timeout"
    assert expired[0].reason == "timeout_exceeded"
    run = await OutwardRunStore(db_path).get("run-timeout")
    assert run is not None
    assert run.status == "failed"
    events = await OutwardRunEventStore(db_path).list_for_run("run-timeout")
    assert events[-1].event_type == "proposal_expired"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_approval_rejects_unregistered_or_not_required_tools(tmp_path) -> None:
    """Layer: integration. Verifies approval gating uses the Phase 0 connector registry."""
    db_path = tmp_path / "phase2-registry.sqlite3"
    await _seed_run(db_path, run_id="run-registry")
    service = _approval_service(db_path, _Clock("2026-04-25T12:01:00+00:00"))

    with pytest.raises(ValueError, match="not registered"):
        await service.request_tool_approval(
            run_id="run-registry",
            tool="unknown_tool",
            args={},
            context_summary="bad",
        )
    with pytest.raises(ValueError, match="not approval-required"):
        await service.request_tool_approval(
            run_id="run-registry",
            tool="delete_file",
            args={"path": "out.txt"},
            context_summary="not configured",
        )
