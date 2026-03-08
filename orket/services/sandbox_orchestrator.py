"""
Sandbox Orchestrator - Phase 3: Elegant Failure & Recovery

Application Service: Manages the full lifecycle of sandbox environments.
Coordinates Docker Compose creation, deployment, health monitoring, and cleanup.
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from pathlib import Path
import secrets
import subprocess
import json
from datetime import datetime, UTC

from orket.domain.sandbox import (
    Sandbox,
    SandboxStatus,
    TechStack,
    PortAllocation,
    SandboxRegistry,
)
from orket.adapters.storage.command_runner import CommandRunner
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.domain.verification import AGENT_OUTPUT_DIR
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

    def __init__(
        self,
        workspace_root: Path,
        registry: Optional[SandboxRegistry] = None,
        organization: Any = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
        command_runner: Optional[CommandRunner] = None,
        fs: Optional[AsyncFileTools] = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.registry = registry or SandboxRegistry()
        self.organization = organization
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.sandbox_policy_node = self.decision_nodes.resolve_sandbox_policy(self.organization)
        self.command_runner = command_runner or CommandRunner()
        self.templates_dir = Path(__file__).parent.parent.parent / "infrastructure" / "sandbox_templates"
        self.fs = fs or AsyncFileTools(workspace_root)
        self._allowed_log_services = {
            "api",
            "frontend",
            "db",
            "database",
            "pgadmin",
            "mongo",
            "mongo-express",
        }
        self._optional_health_services = {"pgadmin", "mongo-express"}

    async def create_sandbox(
        self,
        rock_id: str,
        project_name: str,
        tech_stack: TechStack,
        workspace_path: str
    ) -> Sandbox:
        """
        Create and deploy a new sandbox environment.
        """
        sandbox_id = self.sandbox_policy_node.build_sandbox_id(rock_id)

        # 1. Allocate ports
        ports = self.registry.port_allocator.allocate(sandbox_id, tech_stack)
        
        # Hardened Credentials (v1.0 Ready)
        db_password = secrets.token_urlsafe(32)

        # 2. Create Sandbox entity
        sandbox = Sandbox(
            id=sandbox_id,
            rock_id=rock_id,
            project_name=project_name,
            tech_stack=tech_stack,
            ports=ports,
            compose_project=self.sandbox_policy_node.build_compose_project(sandbox_id),
            workspace_path=workspace_path,
            api_url=f"http://localhost:{ports.api}",
            frontend_url=f"http://localhost:{ports.frontend}",
            database_url=self._get_database_url(tech_stack, ports, db_password),
            admin_url=f"http://localhost:{ports.admin_tool}" if ports.admin_tool else None
        )

        # 3. Register sandbox
        self.registry.register(sandbox)

        # 4. Generate docker-compose.yml
        compose_content = self._generate_compose_file(sandbox, db_password)
        compose_path = self._compose_path(workspace_path)
        await self.fs.write_file(str(compose_path), compose_content)

        log_event("sandbox_create", {
            "sandbox_id": sandbox_id,
            "rock_id": rock_id,
            "tech_stack": tech_stack.value,
            "ports": ports.model_dump()
        }, Path(workspace_path))

        # 5. Deploy (docker-compose up -d)
        try:
            await self._deploy_sandbox(sandbox, compose_path)
            sandbox.status = SandboxStatus.RUNNING
            sandbox.deployed_at = datetime.now(UTC).isoformat()
            log_event("sandbox_deployed", {"sandbox_id": sandbox_id}, Path(workspace_path))
        except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as e:
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

        compose_path = self._compose_path(sandbox.workspace_path)

        try:
            result = await self.command_runner.run_async(
                "docker-compose",
                "-f",
                str(compose_path),
                "-p",
                sandbox.compose_project,
                "down",
                "-v",
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

        except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as e:
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
            result = await self.command_runner.run_async(
                "docker-compose",
                "-f",
                str(self._compose_path(sandbox.workspace_path)),
                "-p",
                sandbox.compose_project,
                "ps",
                "--format",
                "json",
            )

            if result.returncode != 0:
                sandbox.health_checks_failed += 1
                sandbox.last_health_check = datetime.now(UTC).isoformat()
                return False

            # Docker Compose emits either a JSON array or newline-delimited JSON objects.
            containers = self._parse_compose_ps_output(result.stdout)
            core_containers = [
                container
                for container in containers
                if str(container.get("Service") or "").strip() not in self._optional_health_services
            ]
            tracked = core_containers or containers
            all_running = all(c.get("State") == "running" for c in tracked)

            if all_running:
                sandbox.health_checks_passed += 1
                if sandbox.status == SandboxStatus.UNHEALTHY:
                    sandbox.status = SandboxStatus.RUNNING
            else:
                sandbox.health_checks_failed += 1
                sandbox.status = SandboxStatus.UNHEALTHY

            sandbox.last_health_check = datetime.now(UTC).isoformat()
            return all_running

        except (RuntimeError, ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError) as e:
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

        compose_path = self._compose_path(sandbox.workspace_path)

        cmd = [
            "docker-compose",
            "-f", str(compose_path),
            "-p", sandbox.compose_project,
            "logs", "--tail=100"
        ]

        if service:
            service_name = str(service).strip()
            if service_name not in self._allowed_log_services:
                raise ValueError(f"Unsupported sandbox service: {service_name}")
            cmd.append(service_name)

        result = self.command_runner.run_sync(*cmd, timeout=10)
        return result.stdout

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _generate_compose_file(self, sandbox: Sandbox, db_password: str) -> str:
        """
        Generate docker-compose.yml content through sandbox policy node.
        """
        admin_password = secrets.token_urlsafe(32)
        return self.sandbox_policy_node.generate_compose_file(
            sandbox=sandbox,
            db_password=db_password,
            admin_password=admin_password,
        )

    def _get_database_url(self, tech_stack: TechStack, ports: PortAllocation, db_password: str = "") -> str:
        return self.sandbox_policy_node.get_database_url(tech_stack, ports, db_password)

    @staticmethod
    def _compose_path(workspace_path: str | Path) -> Path:
        return Path(workspace_path) / AGENT_OUTPUT_DIR / "deployment" / "docker-compose.sandbox.yml"

    @staticmethod
    def _parse_compose_ps_output(raw: str) -> list[dict[str, Any]]:
        payload = str(raw or "").strip()
        if not payload:
            return []
        if payload.startswith("["):
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, list) else []
        rows: list[dict[str, Any]] = []
        for line in payload.splitlines():
            token = line.strip()
            if not token:
                continue
            parsed_line = json.loads(token)
            if isinstance(parsed_line, dict):
                rows.append(parsed_line)
        return rows

    async def _deploy_sandbox(self, sandbox: Sandbox, compose_path: Path) -> None:
        """Execute docker-compose up -d."""
        result = await self.command_runner.run_async(
            "docker-compose",
            "-f",
            str(compose_path),
            "-p",
            sandbox.compose_project,
            "up",
            "-d",
            "--build",
        )
        if result.returncode != 0:
            raise RuntimeError(f"Docker Compose failed: {result.stderr}")

        # Capture container IDs
        ps_result = await self.command_runner.run_async(
            "docker-compose",
            "-f",
            str(compose_path),
            "-p",
            sandbox.compose_project,
            "ps",
            "-q",
        )
        container_ids = ps_result.stdout.strip().split("\n")
        sandbox.container_ids = {f"container-{i}": cid for i, cid in enumerate(container_ids)}

