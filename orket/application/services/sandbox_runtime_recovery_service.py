from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from orket.application.services.sandbox_cleanup_scheduler_service import SandboxCleanupSchedulerService
from orket.application.services.sandbox_lifecycle_reconciliation_service import SandboxObservation
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, OwnershipConfidence, SandboxLifecycleError, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord
from orket.domain.verification import AGENT_OUTPUT_DIR

if TYPE_CHECKING:
    from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService


class SandboxRuntimeRecoveryService:
    """Handles recovery flows for ambiguous runtime outcomes and scheduled cleanup."""

    def __init__(self, *, lifecycle_service: SandboxRuntimeLifecycleService) -> None:
        self.lifecycle_service = lifecycle_service
        self.scheduler = SandboxCleanupSchedulerService(lifecycle_service.mutations)

    async def reconcile_sandbox(self, *, sandbox_id: str) -> SandboxLifecycleRecord:
        record = await self.lifecycle_service.repository.get_record(sandbox_id)
        if record is None:
            raise ValueError(f"Sandbox lifecycle record not found for {sandbox_id}")
        observed_at = self.lifecycle_service._now()
        observed_resources = await self.lifecycle_service._observe_project_resources(record.compose_project)
        docker_present = bool(observed_resources)
        if record.requires_reconciliation:
            return await self._recover_reconciliation_block(
                record=record,
                observed_at=observed_at,
                observed_resources=observed_resources,
                docker_present=docker_present,
            )
        if record.state not in {SandboxState.ACTIVE, SandboxState.TERMINAL}:
            return record
        result = await self.lifecycle_service.reconciler.reconcile_existing_record(
            sandbox_id=sandbox_id,
            operation_id=f"runtime-reconcile:{sandbox_id}:{record.record_version}",
            observation=SandboxObservation(docker_present=docker_present, observed_at=observed_at),
        )
        return record if result is None else result.record

    async def sweep_due_cleanups(self, *, max_records: int = 1) -> list[SandboxLifecycleRecord]:
        if max_records < 1:
            return []
        cleaned: list[SandboxLifecycleRecord] = []
        sweep_token = uuid4().hex
        for index in range(max_records):
            try:
                claimed = await self.scheduler.claim_next_due_cleanup(
                    observed_at=self.lifecycle_service._now(),
                    claimant_id=self.lifecycle_service.instance_id,
                    operation_id_prefix=f"cleanup-sweep:{sweep_token}:{index}",
                )
                if claimed is None:
                    break
                cleaned.append(await self._execute_claimed_cleanup(record=claimed.record))
            except (SandboxLifecycleError, ValueError):
                continue
        return cleaned

    async def discover_orphans(self) -> list[SandboxLifecycleRecord]:
        compose_result = await self.lifecycle_service.command_runner.run_async(
            "docker-compose",
            "ls",
            "--format",
            "json",
        )
        if compose_result.returncode != 0:
            raise RuntimeError(f"Failed to list docker-compose projects: {compose_result.stderr}")
        rows = json.loads(compose_result.stdout or "[]")
        if not isinstance(rows, list):
            raise RuntimeError("docker-compose ls returned an unexpected payload.")
        known_projects = {record.compose_project for record in await self.lifecycle_service.repository.list_records()}
        created: list[SandboxLifecycleRecord] = []
        observed_at = self.lifecycle_service._now()
        for row in rows:
            compose_project = str((row or {}).get("Name") or "").strip()
            if not compose_project.startswith("orket-sandbox-") or compose_project in known_projects:
                continue
            observed_resources = await self.lifecycle_service._observe_project_resources(compose_project)
            if not observed_resources:
                continue
            record = self._build_orphan_record(
                compose_project=compose_project,
                observed_at=observed_at,
                observed_resources=observed_resources,
            )
            await self.lifecycle_service.repository.save_record(record)
            known_projects.add(compose_project)
            created.append(record)
        return created

    async def _recover_reconciliation_block(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
        observed_resources,
        docker_present: bool,
    ) -> SandboxLifecycleRecord:
        current = await self._clear_requires_reconciliation(record=record, reason="reconciliation completed")
        if current.state is SandboxState.STARTING:
            return await self._recover_starting_record(
                record=current,
                observed_at=observed_at,
                observed_resources=observed_resources,
                docker_present=docker_present,
            )
        if current.state not in {SandboxState.ACTIVE, SandboxState.TERMINAL}:
            return current
        result = await self.lifecycle_service.reconciler.reconcile_existing_record(
            sandbox_id=current.sandbox_id,
            operation_id=f"runtime-reconcile:{current.sandbox_id}:{current.record_version}",
            observation=SandboxObservation(docker_present=docker_present, observed_at=observed_at),
        )
        return current if result is None else result.record

    async def _recover_starting_record(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
        observed_resources,
        docker_present: bool,
    ) -> SandboxLifecycleRecord:
        current = record
        if docker_present:
            current = await self.lifecycle_service._apply_record_copy(
                record=current,
                operation_id=f"reconcile-inventory:{current.sandbox_id}:{current.record_version}",
                updates={
                    "managed_resource_inventory": self.lifecycle_service._inventory_from_resources(observed_resources)
                },
            )
            return (
                await self.lifecycle_service.mutations.transition_state(
                    sandbox_id=current.sandbox_id,
                    operation_id=f"reconcile-starting-active:{current.sandbox_id}:{current.record_version}",
                    expected_record_version=current.record_version,
                    event=LifecycleEvent.HEALTH_VERIFIED,
                    next_state=SandboxState.ACTIVE,
                )
            ).record
        return (
            await self.lifecycle_service.mutations.transition_state(
                sandbox_id=current.sandbox_id,
                operation_id=f"reconcile-starting-failed:{current.sandbox_id}:{current.record_version}",
                expected_record_version=current.record_version,
                event=LifecycleEvent.STARTUP_FAILURE,
                next_state=SandboxState.TERMINAL,
                terminal_reason=TerminalReason.START_FAILED,
                terminal_at=observed_at,
                cleanup_due_at=self.lifecycle_service.policy.cleanup_due_at_for(
                    state=SandboxState.TERMINAL,
                    terminal_reason=TerminalReason.START_FAILED,
                    reference_time=observed_at,
                ),
            )
        ).record

    async def _clear_requires_reconciliation(
        self,
        *,
        record: SandboxLifecycleRecord,
        reason: str,
    ) -> SandboxLifecycleRecord:
        return (
            await self.lifecycle_service.mutations.set_requires_reconciliation(
                sandbox_id=record.sandbox_id,
                operation_id=f"requires-reconciliation-clear:{record.sandbox_id}:{record.record_version}",
                expected_record_version=record.record_version,
                reason=reason,
                requires_reconciliation=False,
            )
        ).record

    @staticmethod
    def _compose_path(workspace_path: str) -> Path:
        return Path(workspace_path) / AGENT_OUTPUT_DIR / "deployment" / "docker-compose.sandbox.yml"

    def _build_orphan_record(
        self,
        *,
        compose_project: str,
        observed_at: str,
        observed_resources,
    ) -> SandboxLifecycleRecord:
        confidence, sandbox_id, run_id = self._ownership_metadata(compose_project=compose_project, observed_resources=observed_resources)
        terminal_reason = (
            TerminalReason.ORPHAN_DETECTED
            if confidence is OwnershipConfidence.VERIFIED
            else TerminalReason.ORPHAN_UNVERIFIED_OWNERSHIP
        )
        return SandboxLifecycleRecord(
            sandbox_id=sandbox_id,
            compose_project=compose_project,
            workspace_path=f"orphan:{compose_project}",
            run_id=run_id,
            session_id=None if run_id else f"orphan:{sandbox_id}",
            lease_epoch=0,
            state=SandboxState.ORPHANED,
            cleanup_state=CleanupState.NONE,
            record_version=1,
            created_at=observed_at,
            terminal_at=observed_at,
            terminal_reason=terminal_reason,
            cleanup_due_at=self.lifecycle_service.policy.cleanup_due_at_for(
                state=SandboxState.ORPHANED,
                terminal_reason=terminal_reason,
                reference_time=observed_at,
            ),
            cleanup_attempts=0,
            managed_resource_inventory=self.lifecycle_service._inventory_from_resources(observed_resources),
            requires_reconciliation=False,
            docker_context=self.lifecycle_service.docker_context,
            docker_host_id=self.lifecycle_service.docker_host_id,
        )

    @staticmethod
    def _ownership_metadata(*, compose_project: str, observed_resources) -> tuple[OwnershipConfidence, str, str | None]:
        default_sandbox_id = compose_project.removeprefix("orket-sandbox-") or compose_project
        sandbox_ids = {
            str(resource.labels.get("orket.sandbox_id") or "").strip()
            for resource in observed_resources
            if resource.labels.get("orket.managed") == "true"
        }
        sandbox_ids.discard("")
        run_ids = {
            str(resource.labels.get("orket.run_id") or "").strip()
            for resource in observed_resources
            if resource.labels.get("orket.managed") == "true"
        }
        run_ids.discard("")
        if len(sandbox_ids) == 1 and run_ids:
            return OwnershipConfidence.VERIFIED, next(iter(sandbox_ids)), sorted(run_ids)[0]
        return OwnershipConfidence.UNVERIFIED, default_sandbox_id, None

    async def _execute_claimed_cleanup(self, *, record: SandboxLifecycleRecord) -> SandboxLifecycleRecord:
        current = await self.lifecycle_service._apply_record_copy(
            record=record,
            operation_id=f"cleanup-attempt:{record.sandbox_id}:{record.record_version}",
            updates={"cleanup_attempts": record.cleanup_attempts + 1},
            expected_cleanup_state=CleanupState.IN_PROGRESS,
        )
        observed_before = await self.lifecycle_service._observe_project_resources(current.compose_project)
        if not current.managed_resource_inventory.containers and observed_before:
            current = await self.lifecycle_service._apply_record_copy(
                record=current,
                operation_id=f"cleanup-inventory:{current.sandbox_id}:{current.record_version}",
                updates={"managed_resource_inventory": self.lifecycle_service._inventory_from_resources(observed_before)},
                expected_cleanup_state=CleanupState.IN_PROGRESS,
            )
        compose_path = self._compose_path(current.workspace_path)
        authority = self.lifecycle_service.cleanup_authority.decide(
            record=current,
            observed_resources=observed_before,
            compose_path_available=compose_path.exists(),
        )
        if not authority.compose_cleanup_allowed:
            await self.lifecycle_service._mark_cleanup_failed(current, "cleanup authority blocked")
            raise RuntimeError(f"Cleanup authority blocked for sandbox {current.sandbox_id}")
        result = await self.lifecycle_service.command_runner.run_async(
            "docker-compose",
            "-f",
            str(compose_path),
            "-p",
            current.compose_project,
            "down",
            "-v",
            "--remove-orphans",
        )
        observed_after = await self.lifecycle_service._observe_project_resources(current.compose_project)
        verification = self.lifecycle_service.cleanup_verifier.verify_absence(
            record=current,
            observed_resources=observed_after,
        )
        if not verification.success:
            error = result.stderr or ",".join(verification.remaining_expected)
            await self.lifecycle_service._mark_cleanup_failed(current, error)
            raise RuntimeError(f"Failed to verify sandbox cleanup: {error}")
        current = await self.lifecycle_service.repository.get_record(current.sandbox_id)
        if current is None:
            raise ValueError(f"Sandbox lifecycle record not found for {record.sandbox_id}")
        return (
            await self.lifecycle_service.mutations.transition_state(
                sandbox_id=current.sandbox_id,
                operation_id=f"cleanup-complete:{current.sandbox_id}:{current.record_version}",
                expected_record_version=current.record_version,
                event=LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
                next_state=SandboxState.CLEANED,
                cleanup_state=CleanupState.COMPLETED,
            )
        ).record
