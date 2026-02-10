"""
Sandbox Orchestrator - Phase 3: Elegant Failure & Recovery

Application Service: Manages the full lifecycle of sandbox environments.
Coordinates Docker Compose creation, deployment, health monitoring, and cleanup.
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from pathlib import Path
import subprocess
import json
from datetime import datetime, UTC

from orket.domain.sandbox import (
    Sandbox,
    SandboxStatus,
    TechStack,
    PortAllocation,
    SandboxRegistry,
    PortAllocator
)
from orket.logging import log_event


class SandboxOrchestrator:
    """
    Application Service: Orchestrates sandbox lifecycle.

    Responsibilities:
    1. Create Docker Compose configuration from templates
    2. Start containers (docker-compose up -d)
    3. Monitor health (docker ps, health checks)
    4. Provide inspection tools (logs, exec access)
    5. Clean up (docker-compose down -v)
    """

    def __init__(self, workspace_root: Path, registry: Optional[SandboxRegistry] = None):
        self.workspace_root = workspace_root
        self.registry = registry or SandboxRegistry()
        self.templates_dir = Path(__file__).parent.parent.parent / "infrastructure" / "sandbox_templates"

    async def create_sandbox(
        self,
        rock_id: str,
        project_name: str,
        tech_stack: TechStack,
        workspace_path: str
    ) -> Sandbox:
        """
        Create and deploy a new sandbox environment.

        Args:
            rock_id: Parent Rock ID
            project_name: Human-readable name
            tech_stack: Technology stack to deploy
            workspace_path: Path to project code

        Returns:
            Sandbox entity with allocated ports and URLs
        """
        sandbox_id = f"sandbox-{rock_id}"

        # 1. Allocate ports
        ports = self.registry.port_allocator.allocate(sandbox_id, tech_stack)

        # 2. Create Sandbox entity
        sandbox = Sandbox(
            id=sandbox_id,
            rock_id=rock_id,
            project_name=project_name,
            tech_stack=tech_stack,
            ports=ports,
            compose_project=f"orket-{sandbox_id}",
            workspace_path=workspace_path,
            api_url=f"http://localhost:{ports.api}",
            frontend_url=f"http://localhost:{ports.frontend}",
            database_url=self._get_database_url(tech_stack, ports),
            admin_url=f"http://localhost:{ports.admin_tool}" if ports.admin_tool else None
        )

        # 3. Register sandbox
        self.registry.register(sandbox)

        # 4. Generate docker-compose.yml
        compose_content = self._generate_compose_file(sandbox)
        compose_path = Path(workspace_path) / "docker-compose.sandbox.yml"
        compose_path.write_text(compose_content)

        log_event("sandbox_create", {
            "sandbox_id": sandbox_id,
            "rock_id": rock_id,
            "tech_stack": tech_stack.value,
            "ports": ports.dict()
        }, Path(workspace_path))

        # 5. Deploy (docker-compose up -d)
        try:
            await self._deploy_sandbox(sandbox, compose_path)
            sandbox.status = SandboxStatus.RUNNING
            sandbox.deployed_at = datetime.now(UTC).isoformat()
            log_event("sandbox_deployed", {"sandbox_id": sandbox_id}, Path(workspace_path))
        except Exception as e:
            sandbox.status = SandboxStatus.UNHEALTHY
            sandbox.last_error = str(e)
            log_event("sandbox_deploy_failed", {
                "sandbox_id": sandbox_id,
                "error": str(e)
            }, Path(workspace_path))
            raise

        return sandbox

    async def delete_sandbox(self, sandbox_id: str) -> None:
        """
        Stop and remove all containers for a sandbox.

        Args:
            sandbox_id: Sandbox to delete
        """
        sandbox = self.registry.get(sandbox_id)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_id} not found")

        sandbox.status = SandboxStatus.STOPPING

        compose_path = Path(sandbox.workspace_path) / "docker-compose.sandbox.yml"

        try:
            # docker-compose down -v (remove volumes)
            result = subprocess.run(
                [
                    "docker-compose",
                    "-f", str(compose_path),
                    "-p", sandbox.compose_project,
                    "down", "-v"
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to stop sandbox: {result.stderr}")

            sandbox.status = SandboxStatus.DELETED
            sandbox.deleted_at = datetime.now(UTC).isoformat()

            # Release ports
            self.registry.port_allocator.release(sandbox_id)

            # Unregister
            self.registry.unregister(sandbox_id)

            log_event("sandbox_deleted", {"sandbox_id": sandbox_id}, Path(sandbox.workspace_path))

        except Exception as e:
            sandbox.last_error = str(e)
            log_event("sandbox_delete_failed", {
                "sandbox_id": sandbox_id,
                "error": str(e)
            }, Path(sandbox.workspace_path))
            raise

    async def health_check(self, sandbox_id: str) -> bool:
        """
        Check if all containers in a sandbox are healthy.

        Returns:
            True if all containers running, False otherwise
        """
        sandbox = self.registry.get(sandbox_id)
        if not sandbox:
            return False

        try:
            # docker-compose ps --format json
            result = subprocess.run(
                [
                    "docker-compose",
                    "-f", str(Path(sandbox.workspace_path) / "docker-compose.sandbox.yml"),
                    "-p", sandbox.compose_project,
                    "ps", "--format", "json"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                sandbox.health_checks_failed += 1
                sandbox.last_health_check = datetime.now(UTC).isoformat()
                return False

            # Parse container status
            containers = json.loads(result.stdout) if result.stdout else []
            all_running = all(c.get("State") == "running" for c in containers)

            if all_running:
                sandbox.health_checks_passed += 1
                if sandbox.status == SandboxStatus.UNHEALTHY:
                    sandbox.status = SandboxStatus.RUNNING
            else:
                sandbox.health_checks_failed += 1
                sandbox.status = SandboxStatus.UNHEALTHY

            sandbox.last_health_check = datetime.now(UTC).isoformat()
            return all_running

        except Exception as e:
            sandbox.health_checks_failed += 1
            sandbox.last_error = str(e)
            sandbox.last_health_check = datetime.now(UTC).isoformat()
            return False

    def get_logs(self, sandbox_id: str, service: Optional[str] = None) -> str:
        """
        Retrieve logs from sandbox containers.

        Args:
            sandbox_id: Sandbox ID
            service: Optional service name (api, frontend, database)

        Returns:
            Log output
        """
        sandbox = self.registry.get(sandbox_id)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_id} not found")

        compose_path = Path(sandbox.workspace_path) / "docker-compose.sandbox.yml"

        cmd = [
            "docker-compose",
            "-f", str(compose_path),
            "-p", sandbox.compose_project,
            "logs", "--tail=100"
        ]

        if service:
            cmd.append(service)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _generate_compose_file(self, sandbox: Sandbox) -> str:
        """
        Generate docker-compose.yml content from template.

        For now, uses simple templates. Could be enhanced with Jinja2.
        """
        if sandbox.tech_stack == TechStack.FASTAPI_REACT_POSTGRES:
            return self._template_fastapi_react_postgres(sandbox)
        elif sandbox.tech_stack == TechStack.FASTAPI_VUE_MONGO:
            return self._template_fastapi_vue_mongo(sandbox)
        elif sandbox.tech_stack == TechStack.CSHARP_RAZOR_EF:
            return self._template_csharp_razor_ef(sandbox)
        else:
            raise ValueError(f"Unsupported tech stack: {sandbox.tech_stack}")

    def _template_fastapi_react_postgres(self, sandbox: Sandbox) -> str:
        """FastAPI + React + PostgreSQL template."""
        return f"""version: "3.8"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.api}:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/appdb
    depends_on:
      - db
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.frontend}:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:{sandbox.ports.api}
    depends_on:
      - api
    restart: unless-stopped

  db:
    image: postgres:16
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=appdb
    ports:
      - "{sandbox.ports.database}:5432"
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: unless-stopped

  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@orket.local
      - PGADMIN_DEFAULT_PASSWORD=admin
    ports:
      - "{sandbox.ports.admin_tool}:80"
    depends_on:
      - db
    restart: unless-stopped

volumes:
  db-data:
"""

    def _template_fastapi_vue_mongo(self, sandbox: Sandbox) -> str:
        """FastAPI + Vue + MongoDB template."""
        return f"""version: "3.8"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.api}:8000"
    environment:
      - MONGO_URL=mongodb://mongo:27017/appdb
    depends_on:
      - mongo
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.frontend}:3000"
    environment:
      - VUE_APP_API_URL=http://localhost:{sandbox.ports.api}
    depends_on:
      - api
    restart: unless-stopped

  mongo:
    image: mongo:7
    ports:
      - "{sandbox.ports.database}:27017"
    volumes:
      - mongo-data:/data/db
    restart: unless-stopped

  mongo-express:
    image: mongo-express:latest
    environment:
      - ME_CONFIG_MONGODB_URL=mongodb://mongo:27017/
    ports:
      - "{sandbox.ports.admin_tool}:8081"
    depends_on:
      - mongo
    restart: unless-stopped

volumes:
  mongo-data:
"""

    def _template_csharp_razor_ef(self, sandbox: Sandbox) -> str:
        """C# WebAPI + Razor Pages + EF Core template."""
        return f"""version: "3.8"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.api}:8080"
      - "{sandbox.ports.frontend}:8443"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ConnectionStrings__DefaultConnection=Server=db;Database=appdb;User=sa;Password=YourStrong!Passw0rd;TrustServerCertificate=True
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      - ACCEPT_EULA=Y
      - SA_PASSWORD=YourStrong!Passw0rd
    ports:
      - "{sandbox.ports.database}:1433"
    volumes:
      - mssql-data:/var/opt/mssql
    restart: unless-stopped

volumes:
  mssql-data:
"""

    def _get_database_url(self, tech_stack: TechStack, ports: PortAllocation) -> str:
        """Generate database connection URL."""
        if "mongo" in tech_stack.value:
            return f"mongodb://localhost:{ports.database}/appdb"
        elif "csharp" in tech_stack.value:
            return f"Server=localhost,{ports.database};Database=appdb;User=sa;Password=YourStrong!Passw0rd"
        else:
            return f"postgresql://postgres:postgres@localhost:{ports.database}/appdb"

    async def _deploy_sandbox(self, sandbox: Sandbox, compose_path: Path) -> None:
        """Execute docker-compose up -d."""
        result = subprocess.run(
            [
                "docker-compose",
                "-f", str(compose_path),
                "-p", sandbox.compose_project,
                "up", "-d", "--build"
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for build + deploy
        )

        if result.returncode != 0:
            raise RuntimeError(f"Docker Compose failed: {result.stderr}")

        # Capture container IDs
        ps_result = subprocess.run(
            [
                "docker-compose",
                "-f", str(compose_path),
                "-p", sandbox.compose_project,
                "ps", "-q"
            ],
            capture_output=True,
            text=True
        )

        container_ids = ps_result.stdout.strip().split("\n")
        sandbox.container_ids = {f"container-{i}": cid for i, cid in enumerate(container_ids)}
