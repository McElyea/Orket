from pathlib import Path

import pytest

from orket.adapters.storage.command_runner import CommandResult
from orket.core.domain.sandbox import PortAllocation, Sandbox, SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class FakeRunner:
    def __init__(self, *, async_result: CommandResult | None = None):
        self.sync_calls = []
        self.async_calls = []
        self.async_result = async_result or CommandResult(returncode=0, stdout="", stderr="")

    async def run_async(self, *cmd: str) -> CommandResult:
        self.async_calls.append(cmd)
        return self.async_result

    def run_sync(self, *cmd: str, timeout=None) -> CommandResult:
        self.sync_calls.append((cmd, timeout))
        return CommandResult(returncode=0, stdout="logs-from-fake-runner", stderr="")


def _sandbox(tmp_path: Path) -> Sandbox:
    return Sandbox(
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


def test_sandbox_orchestrator_get_logs_uses_command_runner(tmp_path):
    registry = SandboxRegistry()
    runner = FakeRunner()
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=registry,
        command_runner=runner,
    )

    registry.register(_sandbox(tmp_path))

    logs = orchestrator.get_logs("sandbox-test")

    assert logs == "logs-from-fake-runner"
    assert runner.sync_calls, "Expected command runner to receive docker-compose logs call"
    assert "agent_output\\deployment\\docker-compose.sandbox.yml" in runner.sync_calls[0][0][2]


def test_sandbox_orchestrator_get_logs_rejects_unknown_service(tmp_path):
    registry = SandboxRegistry()
    runner = FakeRunner()
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=registry,
        command_runner=runner,
    )

    registry.register(_sandbox(tmp_path))

    try:
        orchestrator.get_logs("sandbox-test", service="__invalid__")
    except ValueError as exc:
        assert "Unsupported sandbox service" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown sandbox service")

    assert runner.sync_calls == []


def test_sandbox_orchestrator_get_logs_uses_env_allowed_service_list(monkeypatch, tmp_path):
    """Layer: unit. Verifies log-service allowlists can be narrowed or extended through env configuration."""
    monkeypatch.setenv("ORKET_SANDBOX_ALLOWED_LOG_SERVICES", "api,frontend,custom")
    registry = SandboxRegistry()
    runner = FakeRunner()
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=registry,
        command_runner=runner,
    )

    registry.register(_sandbox(tmp_path))

    logs = orchestrator.get_logs("sandbox-test", service="custom")

    assert logs == "logs-from-fake-runner"
    assert runner.sync_calls[0][0][-1] == "custom"


@pytest.mark.asyncio
async def test_sandbox_orchestrator_health_check_parses_compose_ndjson(tmp_path):
    registry = SandboxRegistry()
    runner = FakeRunner(
        async_result=CommandResult(
            returncode=0,
            stdout=(
                '{"Names":"sandbox-test-api-1","State":"running","Labels":"com.docker.compose.service=api"}\n'
                '{"Names":"sandbox-test-frontend-1","State":"running","Labels":"com.docker.compose.service=frontend"}\n'
                '{"Names":"sandbox-test-db-1","State":"running","Labels":"com.docker.compose.service=db"}\n'
            ),
            stderr="",
        )
    )
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=registry,
        command_runner=runner,
    )

    registry.register(_sandbox(tmp_path))

    result = await orchestrator.health_check("sandbox-test")

    assert result is True
    assert runner.async_calls, "Expected command runner to receive docker-compose ps call"


@pytest.mark.asyncio
async def test_sandbox_orchestrator_health_check_ignores_optional_admin_services(tmp_path):
    registry = SandboxRegistry()
    runner = FakeRunner(
        async_result=CommandResult(
            returncode=0,
            stdout=(
                '{"Names":"sandbox-test-api-1","State":"running","Labels":"com.docker.compose.service=api"}\n'
                '{"Names":"sandbox-test-frontend-1","State":"running","Labels":"com.docker.compose.service=frontend"}\n'
                '{"Names":"sandbox-test-db-1","State":"running","Labels":"com.docker.compose.service=db"}\n'
                '{"Names":"sandbox-test-pgadmin-1","State":"restarting","Labels":"com.docker.compose.service=pgadmin"}\n'
            ),
            stderr="",
        )
    )
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=registry,
        command_runner=runner,
    )

    registry.register(_sandbox(tmp_path))

    result = await orchestrator.health_check("sandbox-test")

    assert result is True
