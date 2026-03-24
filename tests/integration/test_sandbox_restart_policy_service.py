# Layer: integration

from __future__ import annotations

import json

import aiofiles
import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.adapters.storage.command_runner import CommandResult
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.application.services.sandbox_terminal_evidence_service import SandboxTerminalEvidenceService
from orket.application.services.sandbox_lifecycle_view_service import SandboxLifecycleViewService
from orket.application.services.sandbox_restart_policy_service import SandboxRestartPolicyService
from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService
from orket.core.domain import (
    AuthoritySourceClass,
    ClosureBasisClassification,
    ResultClass,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxLifecycleError, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


class FakeInspectRunner:
    def __init__(self, payloads: list[list[dict[str, object]]]) -> None:
        self.payloads = list(payloads)

    async def run_async(self, *cmd: str) -> CommandResult:
        if cmd[:2] != ("docker", "inspect"):
            raise AssertionError(f"Unexpected command: {cmd}")
        return CommandResult(returncode=0, stdout=json.dumps(self.payloads.pop(0)), stderr="")


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
        "last_heartbeat_at": "2026-03-11T00:00:00+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


def _inspect_payload(*, restart_count: int, health_status: str | None) -> list[dict[str, object]]:
    payload = {
        "Name": "/sb-1-api-1",
        "RestartCount": restart_count,
        "Config": {"Labels": {"com.docker.compose.service": "api"}},
        "State": {"Status": "running"},
    }
    if health_status is not None:
        payload["State"]["Health"] = {"Status": health_status}
    return [payload]


@pytest.mark.asyncio
async def test_restart_policy_terminalizes_active_record_and_projects_diagnostics(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    await repo.save_record(_record())
    policy = SandboxLifecyclePolicy(restart_threshold_count=5, restart_window_seconds=300, unhealthy_duration_seconds=1)
    lifecycle = SandboxRuntimeLifecycleService(
        repository=repo,
        command_runner=FakeInspectRunner(
            [
                _inspect_payload(restart_count=0, health_status="unhealthy"),
                _inspect_payload(restart_count=0, health_status="unhealthy"),
            ]
        ),
        instance_id="runner-a",
        docker_context="desktop-linux",
        docker_host_id="host-a",
        policy=policy,
        control_plane_publication=ControlPlanePublicationService(repository=control_plane_repo),
    )
    service = SandboxRestartPolicyService(lifecycle_service=lifecycle, policy=policy)
    lifecycle.terminal_evidence = SandboxTerminalEvidenceService(
        evidence_root=tmp_path / "terminal_evidence"
    )

    await service.observe_runtime_health(
        sandbox_id="sb-1",
        container_rows=[{"Name": "sb-1-api-1"}],
        observed_at="2026-03-11T00:00:00+00:00",
    )
    await service.observe_runtime_health(
        sandbox_id="sb-1",
        container_rows=[{"Name": "sb-1-api-1"}],
        observed_at="2026-03-11T00:00:02+00:00",
    )

    stored = await repo.get_record("sb-1")
    events = await repo.list_events("sb-1")
    views = await SandboxLifecycleViewService(repo).list_views(observed_at="2026-03-11T00:00:03+00:00")
    final_truth = await control_plane_repo.get_final_truth(run_id="run-1")

    assert stored is not None
    assert stored.state is SandboxState.TERMINAL
    assert stored.terminal_reason is TerminalReason.RESTART_LOOP
    assert stored.required_evidence_ref is not None
    async with aiofiles.open(stored.required_evidence_ref, "r", encoding="utf-8") as handle:
        evidence = json.loads(await handle.read())
    assert evidence["payload"]["terminal_reason"] == "restart_loop"
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.FAILED
    assert final_truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP
    assert AuthoritySourceClass.ADAPTER_OBSERVATION in final_truth.authority_sources
    assert any(event.event_type == "sandbox.restart_loop_classified" for event in events)
    assert any(event.event_type == "sandbox.workflow_terminal_outcome" for event in events)
    assert views[0].restart_summary["terminal_reason"] == "restart_loop"


@pytest.mark.asyncio
async def test_runtime_lifecycle_rejects_non_owner_heartbeat_renewal(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record(owner_instance_id="runner-b"))
    lifecycle = SandboxRuntimeLifecycleService(
        repository=repo,
        command_runner=FakeInspectRunner([]),
        instance_id="runner-a",
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )

    with pytest.raises(SandboxLifecycleError, match="non-owner"):
        await lifecycle.handle_healthy(sandbox_id="sb-1")

    stored = await repo.get_record("sb-1")
    assert stored is not None
    assert stored.owner_instance_id == "runner-b"
