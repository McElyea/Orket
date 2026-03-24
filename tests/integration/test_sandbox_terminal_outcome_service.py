# Layer: integration

from __future__ import annotations

import json
from pathlib import Path

import aiofiles
import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.adapters.storage.command_runner import CommandResult
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_terminal_evidence_service import SandboxTerminalEvidenceService
from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService
from orket.core.domain import ClosureBasisClassification, ResultClass
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


class _Runner:
    async def run_async(self, *cmd: str) -> CommandResult:
        raise AssertionError(f"Unexpected command: {cmd}")


def _record(**overrides) -> SandboxLifecycleRecord:
    payload = {
        "sandbox_id": "sb-1",
        "compose_project": "orket-sandbox-sb-1",
        "workspace_path": "workspace/sb-1",
        "run_id": "run-1",
        "owner_instance_id": "runner-a",
        "lease_epoch": 1,
        "lease_expires_at": "2026-03-11T00:05:00+00:00",
        "state": SandboxState.ACTIVE,
        "cleanup_state": CleanupState.NONE,
        "record_version": 3,
        "created_at": "2026-03-11T00:00:00+00:00",
        "last_heartbeat_at": "2026-03-11T00:00:30+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


@pytest.mark.asyncio
async def test_terminal_outcome_exports_required_evidence_and_records_event(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    await repo.save_record(_record())
    lifecycle = SandboxRuntimeLifecycleService(
        repository=repo,
        command_runner=_Runner(),
        instance_id="runner-a",
        docker_context="desktop-linux",
        docker_host_id="host-a",
        control_plane_publication=ControlPlanePublicationService(repository=control_plane_repo),
    )
    lifecycle.terminal_evidence = SandboxTerminalEvidenceService(
        evidence_root=tmp_path / "terminal_evidence"
    )

    record = await lifecycle.terminal_outcomes.record_workflow_terminal_outcome(
        sandbox_id="sb-1",
        terminal_reason=TerminalReason.SUCCESS,
        evidence_payload={"kind": "integration_report", "status": "ok"},
        operation_id_prefix="workflow-finish",
        expected_owner_instance_id="runner-a",
        expected_lease_epoch=1,
        terminal_at="2026-03-11T00:10:00+00:00",
    )
    events = await repo.list_events("sb-1")
    final_truth = await control_plane_repo.get_final_truth(run_id="run-1")

    assert record.state is SandboxState.TERMINAL
    assert record.terminal_reason is TerminalReason.SUCCESS
    assert record.required_evidence_ref is not None
    async with aiofiles.open(Path(record.required_evidence_ref), "r", encoding="utf-8") as handle:
        evidence = json.loads(await handle.read())
    assert evidence["payload"]["kind"] == "integration_report"
    assert final_truth is not None
    assert final_truth.authoritative_result_ref == record.required_evidence_ref
    assert final_truth.result_class is ResultClass.SUCCESS
    assert final_truth.closure_basis is ClosureBasisClassification.NORMAL_EXECUTION
    assert any(event.event_type == "sandbox.workflow_terminal_outcome" for event in events)
