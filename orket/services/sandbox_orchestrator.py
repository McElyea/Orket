"""
Sandbox orchestration for Docker sandbox lifecycle management."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Optional

from orket.adapters.storage.async_executor_service import run_coroutine_blocking
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.adapters.storage.command_runner import CommandRunner
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_workload_catalog import (
    sandbox_runtime_workload_for_tech_stack,
)
from orket.application.services.sandbox_control_plane_effect_service import SandboxControlPlaneEffectService
from orket.application.services.sandbox_control_plane_execution_service import SandboxControlPlaneExecutionService
from orket.application.services.sandbox_control_plane_reservation_service import (
    SandboxControlPlaneReservationService,
)
from orket.application.services.sandbox_control_plane_operator_service import SandboxControlPlaneOperatorService
from orket.application.services.sandbox_control_plane_resource_service import (
    SandboxControlPlaneResourceService,
)
from orket.application.services.sandbox_restart_policy_service import SandboxRestartPolicyService
from orket.application.services.sandbox_runtime_inspection_service import SandboxRuntimeInspectionService
from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService
from orket.application.services.sandbox_runtime_recovery_service import SandboxRuntimeRecoveryService
from orket.core.domain import LeaseStatus, ReservationStatus
from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError, SandboxState as LifecycleState
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.domain.sandbox import PortAllocation, Sandbox, SandboxRegistry, SandboxStatus, TechStack
from orket.domain.verification import AGENT_OUTPUT_DIR
from orket.logging import log_event
from orket.runtime_paths import resolve_control_plane_db_path, resolve_sandbox_lifecycle_db_path


class SandboxOrchestrator:
    """Coordinates Docker sandbox creation, health, inspection, and cleanup."""

    def __init__(
        self,
        workspace_root: Path,
        registry: Optional[SandboxRegistry] = None,
        organization: Any = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
        command_runner: Optional[CommandRunner] = None,
        fs: Optional[AsyncFileTools] = None,
        lifecycle_db_path: Optional[str] = None,
        control_plane_db_path: Optional[str] = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.registry = registry or SandboxRegistry()
        self.organization = organization
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.sandbox_policy_node = self.decision_nodes.resolve_sandbox_policy(self.organization)
        self.command_runner = command_runner or CommandRunner()
        self.templates_dir = Path(__file__).parent.parent.parent / "infrastructure" / "sandbox_templates"
        self.fs = fs or AsyncFileTools(workspace_root)
        self.instance_id = f"{socket.gethostname()}:{os.getpid()}"
        default_docker_host_id = socket.gethostname()
        self.docker_context = os.getenv("DOCKER_CONTEXT", "default").strip() or "default"
        self.docker_host_id = (
            os.getenv("ORKET_DOCKER_HOST_ID", default_docker_host_id).strip() or default_docker_host_id
        )
        self.lifecycle_repository = AsyncSandboxLifecycleRepository(
            resolve_sandbox_lifecycle_db_path(lifecycle_db_path)
        )
        resolved_control_plane_db_path = (
            Path(lifecycle_db_path).with_name("control_plane_records.sqlite3")
            if lifecycle_db_path and control_plane_db_path is None
            else resolve_control_plane_db_path(control_plane_db_path)
        )
        self.control_plane_repository = AsyncControlPlaneRecordRepository(resolved_control_plane_db_path)
        self.control_plane_execution_repository = AsyncControlPlaneExecutionRepository(resolved_control_plane_db_path)
        self.control_plane_publication = ControlPlanePublicationService(repository=self.control_plane_repository)
        self.control_plane_execution = SandboxControlPlaneExecutionService(
            repository=self.control_plane_execution_repository,
            publication=self.control_plane_publication,
        )
        self.control_plane_effects = SandboxControlPlaneEffectService(
            publication=self.control_plane_publication,
            execution_repository=self.control_plane_execution_repository,
        )
        self.control_plane_operator = SandboxControlPlaneOperatorService(
            publication=self.control_plane_publication
        )
        self.control_plane_reservations = SandboxControlPlaneReservationService(
            publication=self.control_plane_publication
        )
        self.lifecycle_service = SandboxRuntimeLifecycleService(
            repository=self.lifecycle_repository,
            command_runner=self.command_runner,
            instance_id=self.instance_id,
            docker_context=self.docker_context,
            docker_host_id=self.docker_host_id,
            control_plane_publication=self.control_plane_publication,
            control_plane_execution=self.control_plane_execution,
            control_plane_effects=self.control_plane_effects,
        )
        self.lifecycle_recovery = SandboxRuntimeRecoveryService(lifecycle_service=self.lifecycle_service)
        self.restart_policy = SandboxRestartPolicyService(lifecycle_service=self.lifecycle_service)
        self.runtime_inspector = SandboxRuntimeInspectionService(command_runner=self.command_runner)
        self._allowed_log_services = {
            "api",
            "frontend",
            "db",
            "database",
            "pgadmin",
            "mongo",
            "mongo-express",
        }
        self._initial_health_attempts = int(os.getenv("ORKET_SANDBOX_INITIAL_HEALTH_ATTEMPTS", "20"))
        self._initial_health_delay_seconds = float(os.getenv("ORKET_SANDBOX_INITIAL_HEALTH_DELAY_SECONDS", "0.5"))

    async def create_sandbox(
        self,
        rock_id: str,
        project_name: str,
        tech_stack: TechStack,
        workspace_path: str,
    ) -> Sandbox:
        """Create and deploy a new sandbox environment."""
        sandbox_id = self.sandbox_policy_node.build_sandbox_id(rock_id)
        if await self.lifecycle_service.repository.get_record(sandbox_id):
            raise ValueError(f"Sandbox lifecycle record already exists for {sandbox_id}")
        ports = self.registry.port_allocator.allocate(sandbox_id, tech_stack)
        db_password = secrets.token_urlsafe(32)
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
            admin_url=f"http://localhost:{ports.admin_tool}" if ports.admin_tool else None,
        )
        reservation_id = None
        try:
            reservation = await self.control_plane_reservations.publish_allocation_reservation(
                sandbox_id=sandbox_id,
                run_id=rock_id,
                compose_project=sandbox.compose_project,
                ports=ports,
                creation_timestamp=sandbox.created_at,
                instance_id=self.instance_id,
            )
            reservation_id = reservation.reservation_id
        except ValueError:
            self.registry.port_allocator.release(sandbox_id)
            raise

        # 3. Create durable lifecycle authority before transient registration or Docker work.
        try:
            await self.lifecycle_service.create_record(
                sandbox_id=sandbox_id,
                compose_project=sandbox.compose_project,
                workspace_path=workspace_path,
                run_id=rock_id,
                source_reservation_id=reservation_id,
            )
            await self.lifecycle_service.mark_create_accepted(sandbox_id=sandbox_id)
            if reservation_id is None:
                raise ValueError(f"reservation publication missing for sandbox {sandbox_id}")
            await self.control_plane_execution.initialize_execution(
                sandbox_id=sandbox_id,
                run_id=rock_id,
                workload=sandbox_runtime_workload_for_tech_stack(tech_stack),
                compose_project=sandbox.compose_project,
                workspace_path=workspace_path,
                configuration_payload={
                    "tech_stack": tech_stack.value,
                    "ports": ports.model_dump(),
                },
                creation_timestamp=sandbox.created_at,
                admission_decision_receipt_ref=reservation_id,
                policy=self.lifecycle_service.policy,
            )
        except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError):
            if reservation_id is not None:
                latest_lease = await self.control_plane_repository.get_latest_lease_record(
                    lease_id=self.control_plane_reservations.lease_id_for_sandbox(sandbox_id)
                )
                if (
                    latest_lease is not None
                    and latest_lease.status is LeaseStatus.ACTIVE
                    and latest_lease.source_reservation_id == reservation_id
                ):
                    release_timestamp = self._now()
                    if release_timestamp < latest_lease.publication_timestamp:
                        release_timestamp = latest_lease.publication_timestamp
                    released_lease = await self.control_plane_publication.publish_lease(
                        lease_id=latest_lease.lease_id,
                        resource_id=latest_lease.resource_id,
                        holder_ref=latest_lease.holder_ref,
                        lease_epoch=latest_lease.lease_epoch,
                        publication_timestamp=release_timestamp,
                        expiry_basis="sandbox_create_record_failed",
                        status=LeaseStatus.RELEASED,
                        granted_timestamp=latest_lease.granted_timestamp,
                        last_confirmed_observation=latest_lease.last_confirmed_observation,
                        cleanup_eligibility_rule=latest_lease.cleanup_eligibility_rule,
                        source_reservation_id=latest_lease.source_reservation_id,
                    )
                    await SandboxControlPlaneResourceService(
                        publication=self.control_plane_publication
                    ).publish_from_lease_closeout(
                        sandbox_id=sandbox_id,
                        lease=released_lease,
                        observed_at=release_timestamp,
                        closeout_basis="sandbox_create_record_failed",
                    )
                latest_reservation = await self.control_plane_repository.get_latest_reservation_record(
                    reservation_id=reservation_id
                )
                if latest_reservation is not None and latest_reservation.status is ReservationStatus.ACTIVE:
                    await self.control_plane_reservations.invalidate_allocation_reservation(
                        sandbox_id=sandbox_id,
                        instance_id=self.instance_id,
                        invalidation_basis="sandbox_create_record_failed",
                    )
            self.registry.port_allocator.release(sandbox_id)
            raise
        self.registry.register(sandbox)

        # 4. Generate docker-compose.yml
        compose_path = self._compose_path(workspace_path)
        try:
            compose_content = self._generate_compose_file(sandbox, db_password)
            await self.fs.write_file(str(compose_path), compose_content)
            log_event(
                "sandbox_create",
                {
                    "sandbox_id": sandbox_id,
                    "rock_id": rock_id,
                    "tech_stack": tech_stack.value,
                    "ports": ports.model_dump(),
                },
                Path(workspace_path),
            )
            await self._deploy_sandbox(sandbox, compose_path)
            if not await self._wait_for_initial_health(sandbox_id=sandbox_id):
                raise RuntimeError("Sandbox startup health verification failed before reaching a running state.")
            sandbox.status = SandboxStatus.RUNNING
            sandbox.deployed_at = self._now()
            log_event("sandbox_deployed", {"sandbox_id": sandbox_id}, Path(workspace_path))
        except RuntimeError as e:
            sandbox.status = SandboxStatus.UNHEALTHY
            sandbox.last_error = str(e)
            await self.lifecycle_service.mark_start_failed(sandbox_id=sandbox_id)
            log_event(
                "sandbox_deploy_failed",
                {
                    "sandbox_id": sandbox_id,
                    "error": str(e),
                },
                Path(workspace_path),
            )
            raise
        except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError) as e:
            sandbox.status = SandboxStatus.UNHEALTHY
            sandbox.last_error = str(e)
            await self.lifecycle_service.mark_requires_reconciliation(
                sandbox_id=sandbox_id,
                reason="sandbox-create-outcome-unknown",
            )
            log_event(
                "sandbox_deploy_failed",
                {
                    "sandbox_id": sandbox_id,
                    "error": str(e),
                },
                Path(workspace_path),
            )
            raise

        return sandbox

    async def delete_sandbox(self, sandbox_id: str, operator_actor_ref: str | None = None) -> None:
        """
        Stop and remove all containers for a sandbox.

        Args:
            sandbox_id: Sandbox to delete
        """
        record = await self.lifecycle_service.repository.get_record(sandbox_id)
        if record is None:
            await self._delete_legacy_sandbox(sandbox_id)
            return
        before_record = record
        sandbox = self.registry.get(sandbox_id)
        if sandbox:
            sandbox.status = SandboxStatus.STOPPING
        current = await self.lifecycle_service.delete_sandbox(
            sandbox_id=sandbox_id,
            compose_path=self._compose_path(record.workspace_path),
        )
        if operator_actor_ref is not None:
            final_truth = None
            if before_record.run_id is not None:
                final_truth = await self.control_plane_repository.get_final_truth(run_id=before_record.run_id)
            await self.control_plane_operator.publish_cancel_run_action(
                actor_ref=operator_actor_ref,
                before_record=before_record,
                after_record=current,
                final_truth=final_truth,
            )
        if sandbox:
            sandbox.status = SandboxStatus.DELETED
            sandbox.deleted_at = self._now()
        self.registry.port_allocator.release(sandbox_id)
        self.registry.unregister(sandbox_id)
        log_event("sandbox_deleted", {"sandbox_id": sandbox_id}, Path(current.workspace_path))

    async def health_check(self, sandbox_id: str) -> bool:
        """
        Check if all containers in a sandbox are healthy.

        Returns:
            True if all containers running, False otherwise
        """
        sandbox = self.registry.get(sandbox_id)
        record = await self.lifecycle_service.repository.get_record(sandbox_id)
        if not sandbox and not record:
            return False
        workspace_path = record.workspace_path if record else str(sandbox.workspace_path)
        compose_project = record.compose_project if record else str(sandbox.compose_project)

        try:
            container_rows = await self.runtime_inspector.list_project_container_rows(
                compose_project=compose_project,
            )
            tracked = self.runtime_inspector.tracked_container_rows(container_rows)
            all_running = self.runtime_inspector.all_core_services_running(container_rows)
            observed_at = self._now()
            if record and tracked:
                assessed_record = await self.restart_policy.observe_runtime_health(
                    sandbox_id=sandbox_id,
                    container_rows=tracked,
                    observed_at=observed_at,
                )
                if assessed_record and assessed_record.state is LifecycleState.TERMINAL:
                    if sandbox:
                        sandbox.health_checks_failed += 1
                        sandbox.status = SandboxStatus.UNHEALTHY
                        sandbox.last_error = str(
                            assessed_record.terminal_reason.value if assessed_record.terminal_reason else "restart_loop"
                        )
                        sandbox.last_health_check = observed_at
                    return False

            if sandbox and all_running:
                sandbox.health_checks_passed += 1
                if sandbox.status == SandboxStatus.UNHEALTHY:
                    sandbox.status = SandboxStatus.RUNNING
            elif sandbox:
                sandbox.health_checks_failed += 1
                sandbox.status = SandboxStatus.UNHEALTHY

            if sandbox:
                sandbox.last_health_check = self._now()
            if record and all_running:
                if record.state is LifecycleState.STARTING:
                    await self.lifecycle_service.mark_deployment_verified(
                        sandbox_id=sandbox_id,
                        compose_project=compose_project,
                    )
                else:
                    await self.lifecycle_service.handle_healthy(sandbox_id=sandbox_id)
            elif record and not container_rows and record.state is LifecycleState.ACTIVE:
                await self.lifecycle_service.handle_missing_runtime(sandbox_id=sandbox_id)
            return all_running

        except SandboxLifecycleError as e:
            if sandbox:
                sandbox.health_checks_failed += 1
                sandbox.last_error = str(e)
                sandbox.last_health_check = self._now()
            log_event("sandbox_health_rejected", {"sandbox_id": sandbox_id, "error": str(e)}, Path(workspace_path))
            return False
        except (RuntimeError, ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError) as e:
            if sandbox:
                sandbox.health_checks_failed += 1
                sandbox.last_error = str(e)
                sandbox.last_health_check = self._now()
            return False

    async def list_sandboxes(self) -> list[dict[str, Any]]:
        views = await self.lifecycle_service.list_views()
        if views:
            return views
        return [item.model_dump() for item in self.registry.list_active()]

    async def reconcile_sandbox(self, sandbox_id: str) -> dict[str, Any]:
        record = await self.lifecycle_recovery.reconcile_sandbox(sandbox_id=sandbox_id)
        self._sync_registry_with_lifecycle(record)
        return record.model_dump(mode="json")

    async def sweep_due_cleanups(self, *, max_records: int = 1) -> list[dict[str, Any]]:
        records = await self.lifecycle_recovery.sweep_due_cleanups(max_records=max_records)
        for record in records:
            self._sync_registry_with_lifecycle(record)
        return [record.model_dump(mode="json") for record in records]

    async def discover_orphaned_sandboxes(self) -> list[dict[str, Any]]:
        return [record.model_dump(mode="json") for record in await self.lifecycle_recovery.discover_orphans()]

    async def reacquire_sandbox_ownership(self, sandbox_id: str) -> dict[str, Any]:
        record = await self.lifecycle_service.reacquire_ownership(sandbox_id=sandbox_id)
        return record.model_dump(mode="json")

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
        record = None
        if sandbox is None:
            record = run_coroutine_blocking(self.lifecycle_repository.get_record(sandbox_id))
        if not sandbox and not record:
            raise ValueError(f"Sandbox {sandbox_id} not found")
        compose_path = self._compose_path(record.workspace_path if record else sandbox.workspace_path)

        cmd = [
            "docker-compose",
            "-f",
            str(compose_path),
            "-p",
            record.compose_project if record else sandbox.compose_project,
            "logs",
            "--tail=100",
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

    async def _wait_for_initial_health(self, *, sandbox_id: str) -> bool:
        for attempt in range(self._initial_health_attempts):
            if await self.health_check(sandbox_id):
                return True
            record = await self.lifecycle_service.repository.get_record(sandbox_id)
            if record and record.state is LifecycleState.TERMINAL:
                return False
            if attempt + 1 < self._initial_health_attempts:
                await asyncio.sleep(self._initial_health_delay_seconds)
        return False

    async def _delete_legacy_sandbox(self, sandbox_id: str) -> None:
        sandbox = self.registry.get(sandbox_id)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_id} not found")
        sandbox.status = SandboxStatus.STOPPING
        result = await self.command_runner.run_async(
            "docker-compose",
            "-f",
            str(self._compose_path(sandbox.workspace_path)),
            "-p",
            sandbox.compose_project,
            "down",
            "-v",
        )
        if result.returncode != 0:
            sandbox.last_error = result.stderr
            raise RuntimeError(f"Failed to stop sandbox: {result.stderr}")
        sandbox.status = SandboxStatus.DELETED
        sandbox.deleted_at = self._now()
        self.registry.port_allocator.release(sandbox_id)
        self.registry.unregister(sandbox_id)
        log_event("sandbox_deleted", {"sandbox_id": sandbox_id}, Path(sandbox.workspace_path))

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat()

    def _sync_registry_with_lifecycle(self, record) -> None:
        if record.state is not LifecycleState.CLEANED:
            return
        sandbox = self.registry.get(record.sandbox_id)
        if sandbox:
            sandbox.status = SandboxStatus.DELETED
            sandbox.deleted_at = self._now()
        self.registry.port_allocator.release(record.sandbox_id)
        self.registry.unregister(record.sandbox_id)
