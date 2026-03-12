# Layer: integration

from __future__ import annotations

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.sandbox_lifecycle_view_service import SandboxLifecycleViewService
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleEventRecord, SandboxLifecycleRecord


def _record(sandbox_id: str, *, cleanup_due_at: str | None, last_heartbeat_at: str | None, requires_reconciliation: bool = False) -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id=sandbox_id,
        compose_project=f"orket-sandbox-{sandbox_id}",
        workspace_path=f"workspace/{sandbox_id}",
        run_id=f"run-{sandbox_id}",
        owner_instance_id="runner-a",
        lease_epoch=1,
        lease_expires_at="2026-03-11T00:05:00+00:00",
        state=SandboxState.TERMINAL,
        cleanup_state=CleanupState.SCHEDULED,
        record_version=1,
        created_at="2026-03-11T00:00:00+00:00",
        last_heartbeat_at=last_heartbeat_at,
        terminal_reason=TerminalReason.FAILED,
        cleanup_due_at=cleanup_due_at,
        cleanup_attempts=0,
        managed_resource_inventory=ManagedResourceInventory(),
        requires_reconciliation=requires_reconciliation,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


@pytest.mark.asyncio
async def test_view_service_projects_operator_fields_and_heartbeat_age(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            "sb-1",
            cleanup_due_at="2026-03-11T00:15:00+00:00",
            last_heartbeat_at="2026-03-11T00:01:00+00:00",
        )
    )
    service = SandboxLifecycleViewService(repo)

    views = await service.list_views(observed_at="2026-03-11T00:05:00+00:00")

    assert len(views) == 1
    assert views[0].sandbox_id == "sb-1"
    assert views[0].heartbeat_age_seconds == 240
    assert views[0].cleanup_eligible is True
    assert views[0].terminal_reason == "failed"


@pytest.mark.asyncio
async def test_view_service_marks_reconciliation_blocked_records_not_cleanup_eligible(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            "sb-1",
            cleanup_due_at="2026-03-11T00:15:00+00:00",
            last_heartbeat_at=None,
            requires_reconciliation=True,
        )
    )
    service = SandboxLifecycleViewService(repo)

    views = await service.list_views(observed_at="2026-03-11T00:05:00+00:00")

    assert views[0].heartbeat_age_seconds is None
    assert views[0].cleanup_eligible is False
    assert views[0].requires_reconciliation is True


@pytest.mark.asyncio
async def test_view_service_projects_latest_restart_diagnostics_from_events(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            "sb-2",
            cleanup_due_at="2026-03-11T00:15:00+00:00",
            last_heartbeat_at="2026-03-11T00:01:00+00:00",
        )
    )
    await repo.append_event(
        SandboxLifecycleEventRecord(
            event_id="evt-1",
            sandbox_id="sb-2",
            event_kind="lifecycle",
            event_type="sandbox.restart_loop_classified",
            created_at="2026-03-11T00:05:00+00:00",
            payload={
                "restart_summary": {"triggered_services": ["api"]},
                "health_summary": {"services": [{"service": "api", "continuous_unhealthy_seconds": 12}]},
                "terminal_reason": "restart_loop",
            },
        )
    )
    service = SandboxLifecycleViewService(repo)

    views = await service.list_views(observed_at="2026-03-11T00:06:00+00:00")

    assert views[0].restart_summary["terminal_reason"] == "restart_loop"
    assert views[0].restart_summary["restart_summary"]["triggered_services"] == ["api"]
