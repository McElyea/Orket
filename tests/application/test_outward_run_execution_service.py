from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_run_execution_service import OutwardRunExecutionService
from orket.application.services.outward_run_service import OutwardRunService


class _Clock:
    def __init__(self, now: str) -> None:
        self._now = datetime.fromisoformat(now)
        if self._now.tzinfo is None:
            self._now = self._now.replace(tzinfo=UTC)

    def __call__(self) -> str:
        value = self._now.isoformat()
        self._now += timedelta(seconds=1)
        return value

    def set(self, now: str) -> None:
        self._now = datetime.fromisoformat(now)
        if self._now.tzinfo is None:
            self._now = self._now.replace(tzinfo=UTC)


def _approval_service(db_path: Path, clock: _Clock) -> OutwardApprovalService:
    return OutwardApprovalService(
        approval_store=OutwardApprovalStore(db_path),
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=clock,
    )


def _execution_service(db_path: Path, workspace_root: Path, clock: _Clock) -> OutwardRunExecutionService:
    return OutwardRunExecutionService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        approval_service=_approval_service(db_path, clock),
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=workspace_root,
        utc_now=clock,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_pauses_before_write_and_continues_after_approval(tmp_path) -> None:
    """Layer: integration. Verifies explicit outward write_file execution pauses before effect and resumes."""
    db_path = tmp_path / "phase2-execution.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    target = tmp_path / "approved.txt"

    run = await run_service.submit(
        {
            "run_id": "run-exec",
            "task": {
                "description": "Write approved file",
                "instruction": "Call the governed write_file connector",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "approved.txt", "content": "approved content"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"], "approval_timeout_seconds": 30},
        }
    )

    paused = await _execution_service(db_path, tmp_path, clock).start_if_ready(run.run_id)

    assert paused.status == "approval_required"
    assert target.exists() is False
    proposals = await OutwardApprovalStore(db_path).list(status="pending")
    assert len(proposals) == 1
    assert proposals[0].args_preview["content"] == "[REDACTED]"

    clock.set("2026-04-25T12:01:00+00:00")
    approved = await _approval_service(db_path, clock).approve(proposals[0].proposal_id, operator_ref="operator:test")
    completed = await _execution_service(db_path, tmp_path, clock).continue_after_approval(approved.proposal_id)

    assert completed.status == "completed"
    assert target.read_text(encoding="utf-8") == "approved content"
    events = await OutwardRunEventStore(db_path).list_for_run("run-exec")
    assert [event.event_type for event in events] == [
        "run_submitted",
        "run_started",
        "turn_started",
        "proposal_made",
        "proposal_pending_approval",
        "proposal_approved",
        "tool_invoked",
        "commitment_recorded",
        "turn_completed",
        "run_completed",
    ]
    tool_event = next(event for event in events if event.event_type == "tool_invoked")
    assert tool_event.payload["args_hash"]
    assert "approved content" not in str(tool_event.payload)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_denial_keeps_effect_absent(tmp_path) -> None:
    """Layer: integration. Verifies denial leaves the planned write_file effect absent and fails the run."""
    db_path = tmp_path / "phase2-denied-execution.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    target = tmp_path / "denied.txt"
    run = await run_service.submit(
        {
            "run_id": "run-denied-exec",
            "task": {
                "description": "Write denied file",
                "instruction": "Call the governed write_file connector",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "denied.txt", "content": "denied content"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        }
    )

    await _execution_service(db_path, tmp_path, clock).start_if_ready(run.run_id)
    proposal = (await OutwardApprovalStore(db_path).list(status="pending"))[0]
    denied = await _approval_service(db_path, clock).deny(
        proposal.proposal_id,
        operator_ref="operator:test",
        reason="not allowed",
    )

    assert denied.status == "denied"
    assert target.exists() is False
    stored = await OutwardRunStore(db_path).get("run-denied-exec")
    assert stored is not None
    assert stored.status == "failed"
    assert stored.stop_reason == "not allowed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_delete_file_uses_hardened_connector_after_approval(tmp_path) -> None:
    """Layer: integration. Verifies Phase 5 delete_file execution is gated and recorded through connector service."""
    db_path = tmp_path / "phase5-delete-execution.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    target = tmp_path / "delete-me.txt"
    target.write_text("delete me", encoding="utf-8")
    run = await run_service.submit(
        {
            "run_id": "run-delete-exec",
            "task": {
                "description": "Delete approved file",
                "instruction": "Call delete_file",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "delete_file",
                        "args": {"path": "delete-me.txt"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["delete_file"]},
        }
    )

    paused = await _execution_service(db_path, tmp_path, clock).start_if_ready(run.run_id)
    assert paused.status == "approval_required"
    assert target.exists() is True

    proposal = (await OutwardApprovalStore(db_path).list(status="pending"))[0]
    approved = await _approval_service(db_path, clock).approve(proposal.proposal_id, operator_ref="operator:test")
    completed = await _execution_service(db_path, tmp_path, clock).continue_after_approval(approved.proposal_id)

    assert completed.status == "completed"
    assert target.exists() is False
    events = await OutwardRunEventStore(db_path).list_for_run("run-delete-exec")
    tool_event = next(event for event in events if event.event_type == "tool_invoked")
    assert set(tool_event.payload) == {"connector_name", "args_hash", "result_summary", "duration_ms", "outcome"}
    assert tool_event.payload["connector_name"] == "delete_file"
    assert tool_event.payload["outcome"] == "success"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_execution_rejects_invalid_connector_args_before_proposal(tmp_path) -> None:
    """Layer: integration. Verifies invalid connector args fail before approval proposal or side effect."""
    db_path = tmp_path / "phase5-invalid-args.sqlite3"
    clock = _Clock("2026-04-25T12:00:00+00:00")
    run_service = OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=clock,
    )
    run = await run_service.submit(
        {
            "run_id": "run-invalid-connector-args",
            "task": {
                "description": "Write missing content",
                "instruction": "Call write_file",
                "acceptance_contract": {
                    "governed_tool_call": {
                        "tool": "write_file",
                        "args": {"path": "missing-content.txt"},
                    }
                },
            },
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        }
    )

    failed = await _execution_service(db_path, tmp_path, clock).start_if_ready(run.run_id)

    assert failed.status == "failed"
    assert (tmp_path / "missing-content.txt").exists() is False
    assert await OutwardApprovalStore(db_path).list(status="pending") == []
    assert "invalid connector args" in str(failed.stop_reason)
