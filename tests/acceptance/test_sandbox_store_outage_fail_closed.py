# Layer: end-to-end

from __future__ import annotations

import pytest

from orket.adapters.storage.command_runner import CommandResult
from orket.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class FakeCommandRunner:
    def __init__(self) -> None:
        self.async_calls: list[tuple[str, ...]] = []

    async def run_async(self, *cmd: str) -> CommandResult:
        self.async_calls.append(cmd)
        return CommandResult(returncode=0, stdout="", stderr="")

    def run_sync(self, *cmd: str, timeout=None) -> CommandResult:
        return CommandResult(returncode=0, stdout="", stderr="")


@pytest.mark.asyncio
async def test_create_sandbox_fails_closed_when_lifecycle_store_is_unavailable(tmp_path, monkeypatch) -> None:
    runner = FakeCommandRunner()
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        command_runner=runner,
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )

    async def _raise_store_unavailable(**_kwargs):
        raise OSError("sandbox lifecycle store unavailable")

    monkeypatch.setattr(orchestrator.lifecycle_service, "create_record", _raise_store_unavailable)

    with pytest.raises(OSError, match="store unavailable"):
        await orchestrator.create_sandbox(
            rock_id="store-outage-acceptance-1",
            project_name="Store Outage Acceptance",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )

    sandbox_id = orchestrator.sandbox_policy_node.build_sandbox_id("store-outage-acceptance-1")
    assert runner.async_calls == []
    assert orchestrator.registry.get(sandbox_id) is None
    assert sandbox_id not in orchestrator.registry.port_allocator.allocated_ports
