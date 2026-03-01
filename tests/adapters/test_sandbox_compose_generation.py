"""
Test Docker Compose generation for sandboxes.

Verifies that SandboxOrchestrator generates valid docker-compose.yml files
for all supported tech stacks.
"""
import pytest
from pathlib import Path
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from orket.domain.sandbox import TechStack, SandboxRegistry


def test_fastapi_react_postgres_compose():
    """Test FastAPI + React + Postgres compose generation."""
    orchestrator = SandboxOrchestrator(
        workspace_root=Path.cwd(),
        registry=SandboxRegistry()
    )

    # Create a test sandbox (without deploying)
    from orket.domain.sandbox import Sandbox, PortAllocation, SandboxStatus

    ports = PortAllocation(
        api=8001,
        frontend=3001,
        database=5433,
        admin_tool=8081
    )

    sandbox = Sandbox(
        id="test-sandbox-1",
        rock_id="test-rock",
        project_name="Test Project",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        ports=ports,
        compose_project="orket-test-sandbox-1",
        workspace_path=str(Path.cwd() / "test_workspace"),
        api_url=f"http://localhost:{ports.api}",
        frontend_url=f"http://localhost:{ports.frontend}",
        database_url=f"postgresql://postgres:postgres@localhost:{ports.database}/appdb",
        admin_url=f"http://localhost:{ports.admin_tool}"
    )

    # Generate compose file
    compose_content = orchestrator._generate_compose_file(sandbox, db_password="test-password")

    # Verify content
    assert "version:" in compose_content
    assert "services:" in compose_content
    assert "api:" in compose_content
    assert "frontend:" in compose_content
    assert "db:" in compose_content
    assert "pgadmin:" in compose_content
    assert f"{ports.api}:8000" in compose_content
    assert f"{ports.frontend}:3000" in compose_content
    assert f"{ports.database}:5432" in compose_content
    assert f"{ports.admin_tool}:80" in compose_content
    assert "REACT_APP_API_URL" in compose_content

    print("\nâœ… FastAPI + React + Postgres compose generation test passed")
    print(f"\nGenerated compose file:\n{compose_content}")


def test_fastapi_vue_mongo_compose():
    """Test FastAPI + Vue + MongoDB compose generation."""
    orchestrator = SandboxOrchestrator(
        workspace_root=Path.cwd(),
        registry=SandboxRegistry()
    )

    from orket.domain.sandbox import Sandbox, PortAllocation

    ports = PortAllocation(
        api=8002,
        frontend=3002,
        database=27018,
        admin_tool=8082
    )

    sandbox = Sandbox(
        id="test-sandbox-2",
        rock_id="test-rock-2",
        project_name="Test Project 2",
        tech_stack=TechStack.FASTAPI_VUE_MONGO,
        ports=ports,
        compose_project="orket-test-sandbox-2",
        workspace_path=str(Path.cwd() / "test_workspace_2"),
        api_url=f"http://localhost:{ports.api}",
        frontend_url=f"http://localhost:{ports.frontend}",
        database_url=f"mongodb://localhost:{ports.database}/appdb",
        admin_url=f"http://localhost:{ports.admin_tool}"
    )

    compose_content = orchestrator._generate_compose_file(sandbox, db_password="test-password")

    assert "mongo:" in compose_content
    assert "mongo-express:" in compose_content
    assert "VUE_APP_API_URL" in compose_content
    assert f"{ports.database}:27017" in compose_content

    print("\nâœ… FastAPI + Vue + MongoDB compose generation test passed")


def test_port_allocation():
    """Test that port allocator prevents conflicts."""
    allocator = SandboxRegistry().port_allocator

    # Allocate ports for first sandbox
    ports1 = allocator.allocate("sandbox-1", TechStack.FASTAPI_REACT_POSTGRES)
    assert ports1.api == 8001
    assert ports1.frontend == 3001
    assert ports1.database == 5433

    # Allocate ports for second sandbox
    ports2 = allocator.allocate("sandbox-2", TechStack.FASTAPI_REACT_POSTGRES)
    assert ports2.api == 8002
    assert ports2.frontend == 3002
    assert ports2.database == 5434

    # Verify no conflicts
    assert ports1.api != ports2.api
    assert ports1.frontend != ports2.frontend
    assert ports1.database != ports2.database

    print("\nâœ… Port allocation test passed")
    print(f"  Sandbox 1: API={ports1.api}, Frontend={ports1.frontend}, DB={ports1.database}")
    print(f"  Sandbox 2: API={ports2.api}, Frontend={ports2.frontend}, DB={ports2.database}")


def test_csharp_razor_ef_compose():
    """Test C# Razor + SQL Server compose generation."""
    orchestrator = SandboxOrchestrator(
        workspace_root=Path.cwd(),
        registry=SandboxRegistry()
    )

    from orket.domain.sandbox import Sandbox, PortAllocation

    ports = PortAllocation(
        api=8010,
        frontend=3010,
        database=5442,
        admin_tool=8090
    )

    sandbox = Sandbox(
        id="test-sandbox-csharp",
        rock_id="test-rock-csharp",
        project_name="CSharp Project",
        tech_stack=TechStack.CSHARP_RAZOR_EF,
        ports=ports,
        compose_project="orket-test-sandbox-csharp",
        workspace_path=str(Path.cwd() / "test_workspace_csharp"),
        api_url=f"http://localhost:{ports.api}",
        frontend_url=f"http://localhost:{ports.frontend}",
        database_url=f"Server=localhost,{ports.database};Database=appdb;User=sa;Password=test-password",
        admin_url=f"http://localhost:{ports.admin_tool}"
    )

    compose_content = orchestrator._generate_compose_file(sandbox, db_password="test-password")

    assert "mcr.microsoft.com/mssql/server:2022-latest" in compose_content
    assert "ConnectionStrings__DefaultConnection" in compose_content
    assert "SA_PASSWORD=test-password" in compose_content
    assert f"{ports.database}:1433" in compose_content


@pytest.mark.asyncio
async def test_create_sandbox_uses_generated_password_in_database_url_and_compose(tmp_path, monkeypatch):
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry()
    )

    generated = iter(["db-pass-123", "admin-pass-456"])

    def _fake_token_urlsafe(_length: int) -> str:
        return next(generated)

    captured = {"path": None, "content": None}

    async def _fake_write_file(path: str, content: str):
        captured["path"] = path
        captured["content"] = content
        return path

    async def _fake_deploy(*_args, **_kwargs):
        return None

    monkeypatch.setattr("orket.services.sandbox_orchestrator.secrets.token_urlsafe", _fake_token_urlsafe)
    monkeypatch.setattr(orchestrator.fs, "write_file", _fake_write_file)
    monkeypatch.setattr(orchestrator, "_deploy_sandbox", _fake_deploy)

    sandbox = await orchestrator.create_sandbox(
        rock_id="rock-password",
        project_name="Password Test",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )

    assert "db-pass-123" in sandbox.database_url
    assert captured["content"] is not None
    assert "POSTGRES_PASSWORD=db-pass-123" in str(captured["content"])
    assert "PGADMIN_DEFAULT_PASSWORD=admin-pass-456" in str(captured["content"])


if __name__ == "__main__":
    test_fastapi_react_postgres_compose()
    test_fastapi_vue_mongo_compose()
    test_port_allocation()
    print("\nðŸŽ‰ All sandbox compose generation tests passed!")

