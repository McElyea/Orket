from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.adapters.storage.command_runner import CommandRunner
from orket.application.services.sandbox_cleanup_authority_service import SandboxCleanupAuthorityService
from orket.application.services.sandbox_cleanup_verification_service import SandboxCleanupVerificationService
from orket.application.services.sandbox_lifecycle_mutation_service import SandboxLifecycleMutationService
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.application.services.sandbox_lifecycle_reconciliation_service import SandboxLifecycleReconciliationService, SandboxObservation
from orket.application.services.sandbox_lifecycle_view_service import SandboxLifecycleViewService
from orket.core.domain.sandbox_cleanup import DockerResourceType, ObservedDockerResource
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord

class SandboxRuntimeLifecycleService:
    """Coordinates durable sandbox lifecycle state with live Docker observations."""

    def __init__(
        self,
        *,
        repository: AsyncSandboxLifecycleRepository,
        command_runner: CommandRunner,
        instance_id: str,
        docker_context: str,
        docker_host_id: str,
        policy: SandboxLifecyclePolicy | None = None,
    ) -> None:
        self.repository = repository
        self.command_runner = command_runner
        self.instance_id = instance_id
        self.docker_context = docker_context
        self.docker_host_id = docker_host_id
        self.policy = policy or SandboxLifecyclePolicy()
        self.mutations = SandboxLifecycleMutationService(repository)
        self.reconciler = SandboxLifecycleReconciliationService(mutation_service=self.mutations, policy=self.policy)
        self.views = SandboxLifecycleViewService(repository)
        self.cleanup_authority = SandboxCleanupAuthorityService()
        self.cleanup_verifier = SandboxCleanupVerificationService()

    async def create_record(
        self,
        *,
        sandbox_id: str,
        compose_project: str,
        workspace_path: str,
        run_id: str,
    ) -> SandboxLifecycleRecord:
        created_at = self._now()
        record = SandboxLifecycleRecord(
            sandbox_id=sandbox_id,
            compose_project=compose_project,
            workspace_path=workspace_path,
            run_id=run_id,
            owner_instance_id=self.instance_id,
            lease_epoch=1,
            lease_expires_at=self._lease_expires_at(created_at),
            state=SandboxState.CREATING,
            cleanup_state=CleanupState.NONE,
            record_version=1,
            created_at=created_at,
            last_heartbeat_at=created_at,
            cleanup_attempts=0,
            managed_resource_inventory=ManagedResourceInventory(),
            requires_reconciliation=False,
            docker_context=self.docker_context,
            docker_host_id=self.docker_host_id,
        )
        await self.repository.save_record(record)
        return record

    async def mark_create_accepted(self, *, sandbox_id: str) -> SandboxLifecycleRecord:
        return (await self.mutations.transition_state(
            sandbox_id=sandbox_id,
            operation_id=f"create-accepted:{sandbox_id}",
            expected_record_version=1,
            event=LifecycleEvent.CREATE_ACCEPTED,
            next_state=SandboxState.STARTING,
            expected_owner_instance_id=self.instance_id,
            expected_lease_epoch=1,
        )).record

    async def mark_deployment_verified(
        self,
        *,
        sandbox_id: str,
        compose_project: str,
    ) -> SandboxLifecycleRecord:
        record = await self._require_record(sandbox_id)
        record = await self._apply_record_copy(
            record=record,
            operation_id=f"inventory:{sandbox_id}",
            updates={
                "managed_resource_inventory": self._inventory_from_resources(
                    await self._observe_project_resources(compose_project)
                )
            },
        )
        return (
            await self.mutations.transition_state(
                sandbox_id=sandbox_id,
                operation_id=f"health-verified:{sandbox_id}",
                expected_record_version=record.record_version,
                event=LifecycleEvent.HEALTH_VERIFIED,
                next_state=SandboxState.ACTIVE,
                expected_owner_instance_id=self.instance_id,
                expected_lease_epoch=1,
            )
        ).record

    async def mark_start_failed(self, *, sandbox_id: str) -> SandboxLifecycleRecord:
        record = await self._require_record(sandbox_id)
        if record.state is not SandboxState.STARTING:
            return record
        return (
            await self.mutations.transition_state(
                sandbox_id=sandbox_id,
                operation_id=f"startup-failure:{sandbox_id}",
                expected_record_version=record.record_version,
                event=LifecycleEvent.STARTUP_FAILURE,
                next_state=SandboxState.TERMINAL,
                terminal_reason=TerminalReason.START_FAILED,
                expected_owner_instance_id=record.owner_instance_id,
                expected_lease_epoch=record.lease_epoch,
                terminal_at=self._now(),
                cleanup_due_at=self.policy.cleanup_due_at_for(
                    state=SandboxState.TERMINAL,
                    terminal_reason=TerminalReason.START_FAILED,
                    reference_time=self._now(),
                ),
            )
        ).record

    async def mark_requires_reconciliation(self, *, sandbox_id: str, reason: str) -> SandboxLifecycleRecord:
        record = await self._require_record(sandbox_id)
        return (
            await self.mutations.set_requires_reconciliation(
                sandbox_id=sandbox_id,
                operation_id=f"requires-reconciliation:{sandbox_id}:{record.record_version}",
                expected_record_version=record.record_version,
                reason=reason,
                requires_reconciliation=True,
            )
        ).record

    async def delete_sandbox(self, *, sandbox_id: str, compose_path: Path) -> SandboxLifecycleRecord:
        current = await self._require_record(sandbox_id)
        if current.requires_reconciliation:
            raise ValueError(f"Sandbox {sandbox_id} is blocked by requires_reconciliation=true")
        if current.state is SandboxState.ACTIVE:
            current = (
                await self.mutations.transition_state(
                    sandbox_id=sandbox_id,
                    operation_id=f"terminalize:{sandbox_id}",
                    expected_record_version=current.record_version,
                    event=LifecycleEvent.WORKFLOW_TERMINAL_OUTCOME,
                    next_state=SandboxState.TERMINAL,
                    terminal_reason=TerminalReason.CANCELED,
                    expected_owner_instance_id=current.owner_instance_id,
                    expected_lease_epoch=current.lease_epoch,
                    terminal_at=self._now(),
                    cleanup_due_at=self._now(),
                )
            ).record
        elif current.state is SandboxState.RECLAIMABLE:
            current = (
                await self.mutations.transition_state(
                    sandbox_id=sandbox_id,
                    operation_id=f"reclaim-terminal:{sandbox_id}",
                    expected_record_version=current.record_version,
                    event=LifecycleEvent.RECLAIM_TTL_ELAPSED,
                    next_state=SandboxState.TERMINAL,
                    terminal_reason=TerminalReason.LEASE_EXPIRED,
                    terminal_at=current.terminal_at or self._now(),
                    cleanup_due_at=self._now(),
                )
            ).record
        if current.state is not SandboxState.TERMINAL:
            raise ValueError(f"Sandbox {sandbox_id} is not cleanup-eligible from state {current.state.value}")
        if current.cleanup_state is CleanupState.NONE:
            current = (
                await self.mutations.transition_state(
                    sandbox_id=sandbox_id,
                    operation_id=f"cleanup-scheduled:{sandbox_id}",
                    expected_record_version=current.record_version,
                    event=LifecycleEvent.CLEANUP_SCHEDULED,
                    next_state=SandboxState.TERMINAL,
                    cleanup_state=CleanupState.SCHEDULED,
                    cleanup_due_at=current.cleanup_due_at or self._now(),
                )
            ).record
        current = (
            await self.mutations.claim_cleanup(
                sandbox_id=sandbox_id,
                operation_id=f"cleanup-claim:{sandbox_id}",
                claimant_id=self.instance_id,
                expected_record_version=current.record_version,
            )
        ).record
        current = await self._apply_record_copy(
            record=current,
            operation_id=f"cleanup-attempt:{sandbox_id}",
            updates={"cleanup_attempts": current.cleanup_attempts + 1},
            expected_cleanup_state=CleanupState.IN_PROGRESS,
        )
        observed_before = await self._observe_project_resources(current.compose_project)
        if not current.managed_resource_inventory.containers and observed_before:
            current = await self._apply_record_copy(
                record=current,
                operation_id=f"cleanup-inventory:{sandbox_id}",
                updates={"managed_resource_inventory": self._inventory_from_resources(observed_before)},
                expected_cleanup_state=CleanupState.IN_PROGRESS,
            )
        authority = self.cleanup_authority.decide(
            record=current,
            observed_resources=observed_before,
            compose_path_available=compose_path.exists(),
        )
        if not authority.compose_cleanup_allowed:
            await self._mark_cleanup_failed(current, "cleanup authority blocked")
            raise RuntimeError(f"Cleanup authority blocked for sandbox {sandbox_id}")
        result = await self.command_runner.run_async(
            "docker-compose",
            "-f",
            str(compose_path),
            "-p",
            current.compose_project,
            "down",
            "-v",
            "--remove-orphans",
        )
        observed_after = await self._observe_project_resources(current.compose_project)
        verification = self.cleanup_verifier.verify_absence(
            record=current,
            observed_resources=observed_after,
        )
        if not verification.success:
            error = result.stderr or ",".join(verification.remaining_expected)
            await self._mark_cleanup_failed(current, error)
            raise RuntimeError(f"Failed to verify sandbox cleanup: {error}")
        current = await self._require_record(sandbox_id)
        return (await self.mutations.transition_state(
            sandbox_id=sandbox_id,
            operation_id=f"cleanup-complete:{sandbox_id}",
            expected_record_version=current.record_version,
            event=LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
            next_state=SandboxState.CLEANED,
            cleanup_state=CleanupState.COMPLETED,
        )).record

    async def handle_healthy(self, *, sandbox_id: str) -> SandboxLifecycleRecord:
        record = await self._require_record(sandbox_id)
        if record.state is SandboxState.STARTING:
            return (
                await self.mutations.transition_state(
                    sandbox_id=sandbox_id,
                    operation_id=f"health-verified:{sandbox_id}:{record.record_version}",
                    expected_record_version=record.record_version,
                    event=LifecycleEvent.HEALTH_VERIFIED,
                    next_state=SandboxState.ACTIVE,
                    expected_owner_instance_id=record.owner_instance_id,
                    expected_lease_epoch=record.lease_epoch,
                )
            ).record
        if record.state is SandboxState.ACTIVE:
            return (
                await self.mutations.renew_lease(
                    sandbox_id=sandbox_id,
                    operation_id=f"lease-renew:{sandbox_id}:{record.record_version}",
                    expected_record_version=record.record_version,
                    expected_owner_instance_id=str(record.owner_instance_id),
                    expected_lease_epoch=record.lease_epoch,
                    last_heartbeat_at=self._now(),
                    lease_expires_at=self._lease_expires_at(self._now()),
                )
            ).record
        return record

    async def handle_missing_runtime(self, *, sandbox_id: str) -> SandboxLifecycleRecord | None:
        record = await self._require_record(sandbox_id)
        result = await self.reconciler.reconcile_existing_record(
            sandbox_id=sandbox_id,
            operation_id=f"reconcile-missing:{sandbox_id}:{record.record_version}",
            observation=SandboxObservation(docker_present=False, observed_at=self._now()),
        )
        return None if result is None else result.record

    async def list_views(self) -> list[dict[str, object]]:
        return [view.__dict__ for view in await self.views.list_views(observed_at=self._now())]

    async def _require_record(self, sandbox_id: str) -> SandboxLifecycleRecord:
        record = await self.repository.get_record(sandbox_id)
        if record is None:
            raise ValueError(f"Sandbox lifecycle record not found for {sandbox_id}")
        return record

    async def _mark_cleanup_failed(self, record: SandboxLifecycleRecord, error: str) -> None:
        await self._apply_record_copy(
            record=record,
            operation_id=f"cleanup-failed:{record.sandbox_id}:{record.record_version}",
            updates={
                "cleanup_state": CleanupState.FAILED,
                "cleanup_last_error": error,
                "cleanup_failure_reason": "cleanup_verification_failed",
            },
            expected_cleanup_state=CleanupState.IN_PROGRESS,
        )

    async def _apply_record_copy(
        self,
        *,
        record: SandboxLifecycleRecord,
        operation_id: str,
        updates: dict[str, object],
        expected_cleanup_state: CleanupState | None = None,
    ) -> SandboxLifecycleRecord:
        next_record = record.model_copy(update={**updates, "record_version": record.record_version + 1})
        await self.repository.apply_record_mutation(
            operation_id=operation_id,
            payload_hash=self._payload_hash(next_record.model_dump(mode="json")),
            record=next_record,
            expected_record_version=record.record_version,
            expected_lease_epoch=record.lease_epoch if record.owner_instance_id else None,
            expected_owner_instance_id=record.owner_instance_id,
            expected_cleanup_state=expected_cleanup_state.value if expected_cleanup_state else None,
        )
        return await self._require_record(record.sandbox_id)

    async def _observe_project_resources(self, compose_project: str) -> list[ObservedDockerResource]:
        return [
            *await self._list_resources(
                compose_project=compose_project,
                resource_type=DockerResourceType.CONTAINER,
                command=("docker", "ps", "-a"),
                name_field="Names",
            ),
            *await self._list_resources(
                compose_project=compose_project,
                resource_type=DockerResourceType.NETWORK,
                command=("docker", "network", "ls"),
                name_field="Name",
            ),
            *await self._list_resources(
                compose_project=compose_project,
                resource_type=DockerResourceType.MANAGED_VOLUME,
                command=("docker", "volume", "ls"),
                name_field="Name",
            ),
        ]

    async def _list_resources(
        self,
        *,
        compose_project: str,
        resource_type: DockerResourceType,
        command: tuple[str, ...],
        name_field: str,
    ) -> list[ObservedDockerResource]:
        result = await self.command_runner.run_async(
            *command,
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )
        if result.returncode != 0:
            return []
        return [
            ObservedDockerResource(
                resource_type=resource_type,
                name=str(row.get(name_field) or ""),
                docker_context=self.docker_context,
                docker_host_id=self.docker_host_id,
                labels=self._parse_label_blob(row.get("Labels")),
            )
            for row in self._parse_rows(result.stdout)
            if str(row.get(name_field) or "").strip()
        ]

    @staticmethod
    def _inventory_from_resources(resources: list[ObservedDockerResource]) -> ManagedResourceInventory:
        return ManagedResourceInventory(
            containers=sorted(r.name for r in resources if r.resource_type is DockerResourceType.CONTAINER),
            networks=sorted(r.name for r in resources if r.resource_type is DockerResourceType.NETWORK),
            managed_volumes=sorted(r.name for r in resources if r.resource_type is DockerResourceType.MANAGED_VOLUME),
        )

    @staticmethod
    def _parse_rows(raw: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for line in str(raw or "").splitlines():
            token = line.strip()
            if token:
                parsed = json.loads(token)
                if isinstance(parsed, dict):
                    rows.append(parsed)
        return rows

    @staticmethod
    def _parse_label_blob(raw: object) -> dict[str, str]:
        labels: dict[str, str] = {}
        for entry in str(raw or "").split(","):
            key, _, value = entry.partition("=")
            if key:
                labels[key.strip()] = value.strip()
        return labels

    def _lease_expires_at(self, now: str) -> str:
        return (datetime.fromisoformat(now) + timedelta(seconds=self.policy.lease_duration_seconds)).isoformat()

    @staticmethod
    def _payload_hash(payload: dict[str, object]) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat()
