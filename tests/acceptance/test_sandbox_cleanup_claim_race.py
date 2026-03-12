# Layer: end-to-end

from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.command_runner import CommandResult
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class RaceCommandRunner:
    def __init__(self, *, compose_project: str, sandbox_id: str, run_id: str):
        self.compose_project = compose_project
        self.sandbox_id = sandbox_id
        self.run_id = run_id
        self.resources_present = True
        self.down_calls = 0

    async def run_async(self, *cmd: str) -> CommandResult:
        if cmd[:2] == ("docker-compose", "-f") and "up" in cmd:
            return CommandResult(returncode=0, stdout="", stderr="")
        if cmd[:2] == ("docker-compose", "-f") and "ps" in cmd and "-q" in cmd:
            return CommandResult(returncode=0, stdout="cid-1\n", stderr="")
        if cmd[:2] == ("docker-compose", "-f") and "down" in cmd:
            self.down_calls += 1
            await asyncio.sleep(0.05)
            self.resources_present = False
            return CommandResult(returncode=0, stdout="", stderr="")
        if cmd[:3] == ("docker", "ps", "-a"):
            return CommandResult(returncode=0, stdout=self._container_rows(), stderr="")
        if cmd[:3] == ("docker", "network", "ls"):
            return CommandResult(returncode=0, stdout=self._network_rows(), stderr="")
        if cmd[:3] == ("docker", "volume", "ls"):
            return CommandResult(returncode=0, stdout=self._volume_rows(), stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    def run_sync(self, *cmd: str, timeout=None) -> CommandResult:
        return CommandResult(returncode=0, stdout="", stderr="")

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


@pytest.mark.asyncio
async def test_cleanup_claim_race_allows_only_one_cleanup_execution(tmp_path) -> None:
    sandbox_id = "sandbox-race-1"
    compose_project = "orket-sandbox-race-1"
    runner = RaceCommandRunner(compose_project=compose_project, sandbox_id=sandbox_id, run_id="race-1")
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        command_runner=runner,
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )

    sandbox = await orchestrator.create_sandbox(
        rock_id="race-1",
        project_name="Cleanup Race",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )
    record = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
    assert record is not None
    await orchestrator.lifecycle_service.repository.save_record(
        record.model_copy(
            update={
                "state": SandboxState.TERMINAL,
                "cleanup_state": CleanupState.SCHEDULED,
                "record_version": record.record_version + 1,
                "terminal_reason": TerminalReason.SUCCESS,
                "terminal_at": record.created_at,
                "cleanup_due_at": record.created_at,
            }
        )
    )

    first, second = await asyncio.gather(
        orchestrator.sweep_due_cleanups(max_records=1),
        orchestrator.sweep_due_cleanups(max_records=1),
    )
    stored = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)

    assert sorted([len(first), len(second)]) == [0, 1]
    assert runner.down_calls == 1
    assert stored is not None
    assert stored.state is SandboxState.CLEANED
    assert stored.cleanup_state is CleanupState.COMPLETED
