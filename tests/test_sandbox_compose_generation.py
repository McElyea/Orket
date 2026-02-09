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
    compose_content = orchestrator._generate_compose_file(sandbox)

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

    print("\n✅ FastAPI + React + Postgres compose generation test passed")
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

    compose_content = orchestrator._generate_compose_file(sandbox)

    assert "mongo:" in compose_content
    assert "mongo-express:" in compose_content
    assert "VUE_APP_API_URL" in compose_content
    assert f"{ports.database}:27017" in compose_content

    print("\n✅ FastAPI + Vue + MongoDB compose generation test passed")


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

    print("\n✅ Port allocation test passed")
    print(f"  Sandbox 1: API={ports1.api}, Frontend={ports1.frontend}, DB={ports1.database}")
    print(f"  Sandbox 2: API={ports2.api}, Frontend={ports2.frontend}, DB={ports2.database}")


if __name__ == "__main__":
    test_fastapi_react_postgres_compose()
    test_fastapi_vue_mongo_compose()
    test_port_allocation()
    print("\n🎉 All sandbox compose generation tests passed!")
