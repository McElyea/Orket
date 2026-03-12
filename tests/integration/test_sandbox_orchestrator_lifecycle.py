# Layer: integration

from __future__ import annotations

from pathlib import Path

import aiofiles
import pytest

from orket.adapters.storage.command_runner import CommandResult
from orket.application.services.sandbox_terminal_evidence_service import SandboxTerminalEvidenceService
from orket.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class FakeLifecycleRunner:
    def __init__(self, *, compose_project: str, sandbox_id: str, run_id: str, down_returncode: int = 0):
        self.compose_project = compose_project
        self.sandbox_id = sandbox_id
        self.run_id = run_id
        self.down_returncode = down_returncode
        self.resources_present = True
        self.async_calls: list[tuple[str, ...]] = []

    async def run_async(self, *cmd: str) -> CommandResult:
        self.async_calls.append(cmd)
        if cmd[:2] == ("docker-compose", "-f") and "up" in cmd:
            return CommandResult(returncode=0, stdout="", stderr="")
        if cmd[:2] == ("docker-compose", "-f") and "down" in cmd:
            self.resources_present = False
            return CommandResult(returncode=self.down_returncode, stdout="", stderr="compose-down-warning")
        if cmd[:2] == ("docker-compose", "-f") and "ps" in cmd and "-q" in cmd:
            return CommandResult(returncode=0, stdout="cid-1\n", stderr="")
        if cmd[:2] == ("docker-compose", "-f") and "ps" in cmd and "--format" in cmd:
            return CommandResult(
                returncode=0,
                stdout='{"Service":"api","State":"running","Name":"%s-api-1"}\n' % self.compose_project,
                stderr="",
            )
        if cmd[:3] == ("docker", "ps", "-a"):
            return CommandResult(returncode=0, stdout=self._container_rows(), stderr="")
        if cmd[:3] == ("docker", "network", "ls"):
            return CommandResult(returncode=0, stdout=self._network_rows(), stderr="")
        if cmd[:3] == ("docker", "volume", "ls"):
            return CommandResult(returncode=0, stdout=self._volume_rows(), stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    def run_sync(self, *cmd: str, timeout=None) -> CommandResult:
        return CommandResult(returncode=0, stdout="logs", stderr="")

    def _container_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Names":"%s-api-1","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s"}\n'
            % (self.compose_project, self.sandbox_id, self.run_id)
        )

    def _network_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Name":"%s_default","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s"}\n'
            % (self.compose_project, self.sandbox_id, self.run_id)
        )

    def _volume_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Name":"%s_db-data","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s"}\n'
            % (self.compose_project, self.sandbox_id, self.run_id)
        )


def _orchestrator(tmp_path: Path, runner: FakeLifecycleRunner) -> SandboxOrchestrator:
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        command_runner=runner,
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    return orchestrator


@pytest.mark.asyncio
async def test_create_sandbox_persists_active_lifecycle_and_operator_view(tmp_path) -> None:
    sandbox_id = "sandbox-rock-1"
    compose_project = "orket-sandbox-rock-1"
    runner = FakeLifecycleRunner(compose_project=compose_project, sandbox_id=sandbox_id, run_id="rock-1")
    orchestrator = _orchestrator(tmp_path, runner)

    sandbox = await orchestrator.create_sandbox(
        rock_id="rock-1",
        project_name="Integration Sandbox",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )

    record = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
    views = await orchestrator.list_sandboxes()

    assert sandbox.status.value == "running"
    assert record is not None
    assert record.state.value == "active"
    assert record.managed_resource_inventory.containers == [f"{compose_project}-api-1"]
    assert record.managed_resource_inventory.networks == [f"{compose_project}_default"]
    assert record.managed_resource_inventory.managed_volumes == [f"{compose_project}_db-data"]
    assert views[0]["sandbox_id"] == sandbox_id
    assert views[0]["compose_project"] == compose_project
    assert views[0]["state"] == "active"
    assert views[0]["requires_reconciliation"] is False


@pytest.mark.asyncio
async def test_delete_sandbox_marks_cleaned_after_live_absence_even_if_down_warns(tmp_path) -> None:
    sandbox_id = "sandbox-rock-2"
    compose_project = "orket-sandbox-rock-2"
    runner = FakeLifecycleRunner(
        compose_project=compose_project,
        sandbox_id=sandbox_id,
        run_id="rock-2",
        down_returncode=1,
    )
    orchestrator = _orchestrator(tmp_path, runner)
    orchestrator.lifecycle_service.terminal_evidence = SandboxTerminalEvidenceService(
        evidence_root=tmp_path / "terminal_evidence"
    )

    await orchestrator.create_sandbox(
        rock_id="rock-2",
        project_name="Cleanup Sandbox",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )
    await orchestrator.delete_sandbox(sandbox_id)

    record = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
    events = await orchestrator.lifecycle_service.repository.list_events(sandbox_id)

    assert record is not None
    assert record.state.value == "cleaned"
    assert record.cleanup_state.value == "completed"
    assert record.cleanup_attempts == 1
    assert record.required_evidence_ref is not None
    async with aiofiles.open(record.required_evidence_ref, "r", encoding="utf-8") as handle:
        evidence = await handle.read()
    assert "sandbox_cancellation_receipt" in evidence
    assert any(event.event_type == "sandbox.workflow_terminal_outcome" for event in events)


@pytest.mark.asyncio
async def test_create_sandbox_fails_closed_before_docker_when_lifecycle_store_is_unavailable(tmp_path, monkeypatch) -> None:
    sandbox_id = "sandbox-rock-3"
    compose_project = "orket-sandbox-rock-3"
    runner = FakeLifecycleRunner(compose_project=compose_project, sandbox_id=sandbox_id, run_id="rock-3")
    orchestrator = _orchestrator(tmp_path, runner)

    async def _raise_store_unavailable(**_kwargs):
        raise OSError("sandbox lifecycle store unavailable")

    monkeypatch.setattr(orchestrator.lifecycle_service, "create_record", _raise_store_unavailable)

    with pytest.raises(OSError, match="store unavailable"):
        await orchestrator.create_sandbox(
            rock_id="rock-3",
            project_name="Store Outage",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )

    assert runner.async_calls == []
    assert orchestrator.registry.get(sandbox_id) is None
    assert sandbox_id not in orchestrator.registry.port_allocator.allocated_ports
