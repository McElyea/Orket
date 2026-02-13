from pathlib import Path

from orket.domain.sandbox import PortAllocation, Sandbox, SandboxRegistry, TechStack
from orket.adapters.storage.command_runner import CommandResult
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class FakeRunner:
    def __init__(self):
        self.sync_calls = []

    async def run_async(self, *cmd: str) -> CommandResult:
        return CommandResult(returncode=0, stdout="", stderr="")

    def run_sync(self, *cmd: str, timeout=None) -> CommandResult:
        self.sync_calls.append((cmd, timeout))
        return CommandResult(returncode=0, stdout="logs-from-fake-runner", stderr="")


def test_sandbox_orchestrator_get_logs_uses_command_runner(tmp_path):
    registry = SandboxRegistry()
    runner = FakeRunner()
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=registry,
        command_runner=runner,
    )

    sandbox = Sandbox(
        id="sandbox-test",
        rock_id="rock-1",
        project_name="Test",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        ports=PortAllocation(api=8001, frontend=3001, database=5433, admin_tool=8081),
        compose_project="orket-sandbox-test",
        workspace_path=str(tmp_path),
        api_url="http://localhost:8001",
        frontend_url="http://localhost:3001",
        database_url="postgresql://postgres:pw@localhost:5433/appdb",
        admin_url="http://localhost:8081",
    )
    registry.register(sandbox)

    logs = orchestrator.get_logs("sandbox-test")

    assert logs == "logs-from-fake-runner"
    assert runner.sync_calls, "Expected command runner to receive docker-compose logs call"


