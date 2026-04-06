from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from orket.application.services.sandbox_cleanup_scheduler_service import SandboxCleanupSchedulerService
from orket.application.services.sandbox_lifecycle_reconciliation_service import SandboxObservation
from orket.application.services.sandbox_restart_policy_service import SandboxRestartPolicyService
from orket.application.services.sandbox_runtime_inspection_service import SandboxRuntimeInspectionService
from orket.core.domain.sandbox_cleanup import ObservedDockerResource
from orket.core.domain.sandbox_lifecycle import (
    CleanupState,
    LifecycleEvent,
    OwnershipConfidence,
    SandboxLifecycleError,
    SandboxState,
    TerminalReason,
)
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord
from orket.core.domain.verification import AGENT_OUTPUT_DIR

if TYPE_CHECKING:
    from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService


class SandboxRuntimeRecoveryService:
    """Handles recovery flows for ambiguous runtime outcomes and scheduled cleanup."""

    def __init__(self, *, lifecycle_service: SandboxRuntimeLifecycleService) -> None:
        self.lifecycle_service = lifecycle_service
        self.scheduler = SandboxCleanupSchedulerService(lifecycle_service.mutations)
        self.restart_policy = SandboxRestartPolicyService(lifecycle_service=lifecycle_service)
        self.runtime_inspector = SandboxRuntimeInspectionService(command_runner=lifecycle_service.command_runner)

    async def reconcile_sandbox(self, *, sandbox_id: str) -> SandboxLifecycleRecord:
        record = await self.lifecycle_service.repository.get_record(sandbox_id)
        if record is None:
            raise ValueError(f"Sandbox lifecycle record not found for {sandbox_id}")
        observed_at = self.lifecycle_service._now()
        if self.lifecycle_service.policy.hard_max_age_elapsed(
            created_at=record.created_at, observed_at=observed_at
        ) and record.state not in {
            SandboxState.TERMINAL,
            SandboxState.CLEANED,
            SandboxState.ORPHANED,
        }:
            terminal = await self._terminalize_hard_max_age(record=record, observed_at=observed_at)
            return await self._schedule_cleanup_if_needed(record=terminal, observed_at=observed_at)
        observed_resources = await self.lifecycle_service._observe_project_resources(record.compose_project)
        docker_present = bool(observed_resources)
        if record.state is SandboxState.ACTIVE and docker_present:
            restart_terminal = await self._terminalize_active_restart_loop_if_needed(
                record=record,
                observed_at=observed_at,
            )
            if restart_terminal is not None:
                return await self._schedule_cleanup_if_needed(record=restart_terminal, observed_at=observed_at)
            latest = await self.lifecycle_service.repository.get_record(sandbox_id)
            if latest is not None:
                record = latest
        if record.requires_reconciliation:
            return await self._recover_reconciliation_block(
                record=record,
                observed_at=observed_at,
                observed_resources=observed_resources,
                docker_present=docker_present,
            )
        if record.state is SandboxState.RECLAIMABLE:
            if record.cleanup_due_at and record.cleanup_due_at <= observed_at:
                terminal = await self.lifecycle_service.terminal_outcomes.record_policy_terminal_outcome(
                    sandbox_id=record.sandbox_id,
                    event=LifecycleEvent.RECLAIM_TTL_ELAPSED,
                    terminal_reason=TerminalReason.LEASE_EXPIRED,
                    evidence_payload={
                        "kind": "sandbox_lease_expiry_terminal_receipt",
                        "compose_project": record.compose_project,
                        "workspace_path": record.workspace_path,
                        "policy_match": "reclaim_ttl_elapsed",
                        "observed_at": observed_at,
                    },
                    operation_id_prefix="reclaim-ttl",
                    terminal_at=record.terminal_at or observed_at,
                    cleanup_due_at=observed_at,
                )
                return await self._schedule_cleanup_if_needed(record=terminal, observed_at=observed_at)
            return record
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

    async def preview_due_cleanups(self, *, max_records: int = 1) -> list[dict[str, object]]:
        if max_records < 1:
            return []
        previews: list[dict[str, object]] = []
        candidates = await self.scheduler.list_due_candidates(observed_at=self.lifecycle_service._now())
        for candidate in candidates[:max_records]:
            record = await self.lifecycle_service.repository.get_record(candidate.sandbox_id)
            if record is None:
                continue
            previews.append(
                await self.lifecycle_service.cleanup_executor.preview_cleanup(
                    record=record,
                    compose_path=self._compose_path(record.workspace_path),
                )
            )
        return previews

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
        observed_resources: list[ObservedDockerResource],
        docker_present: bool,
    ) -> SandboxLifecycleRecord:
        current = await self._clear_requires_reconciliation(record=record, reason="reconciliation completed")
        if current.state is SandboxState.STARTING:
            recovered = await self._recover_starting_record(
                record=current,
                observed_at=observed_at,
                observed_resources=observed_resources,
                docker_present=docker_present,
            )
            if recovered.state is SandboxState.TERMINAL:
                return await self._schedule_cleanup_if_needed(record=recovered, observed_at=observed_at)
            return recovered
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
        observed_resources: list[ObservedDockerResource],
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
            container_rows = await self.runtime_inspector.list_project_container_rows(
                compose_project=current.compose_project
            )
            if self.runtime_inspector.all_core_services_running(container_rows):
                record = (
                    await self.lifecycle_service.mutations.transition_state(
                        sandbox_id=current.sandbox_id,
                        operation_id=f"reconcile-starting-active:{current.sandbox_id}:{current.record_version}",
                        expected_record_version=current.record_version,
                        event=LifecycleEvent.HEALTH_VERIFIED,
                        next_state=SandboxState.ACTIVE,
                    )
                ).record
                await self.lifecycle_service._publish_control_plane_lease(
                    record=record,
                    publication_timestamp=observed_at,
                )
                await self.lifecycle_service._publish_control_plane_deploy_effect(
                    record=record,
                    publication_timestamp=observed_at,
                )
                await self.lifecycle_service._resume_control_plane_execution(run_id=record.run_id)
                return record
            return await self.lifecycle_service.terminal_outcomes.record_lifecycle_terminal_outcome(
                sandbox_id=current.sandbox_id,
                event=LifecycleEvent.STARTUP_FAILURE,
                terminal_reason=TerminalReason.START_FAILED,
                evidence_payload={
                    "kind": "sandbox_startup_failure_receipt",
                    "compose_project": current.compose_project,
                    "workspace_path": current.workspace_path,
                    "failure_stage": "reconciliation_present_but_core_services_not_running",
                    "observed_at": observed_at,
                    "docker_present": True,
                    "managed_resources_observed": len(observed_resources),
                },
                operation_id_prefix="reconcile-starting-failed-present",
                expected_owner_instance_id=current.owner_instance_id,
                expected_lease_epoch=current.lease_epoch if current.owner_instance_id else None,
                terminal_at=observed_at,
                cleanup_due_at=self.lifecycle_service.policy.cleanup_due_at_for(
                    state=SandboxState.TERMINAL,
                    terminal_reason=TerminalReason.START_FAILED,
                    reference_time=observed_at,
                ),
            )
        return await self.lifecycle_service.terminal_outcomes.record_lifecycle_terminal_outcome(
            sandbox_id=current.sandbox_id,
            event=LifecycleEvent.STARTUP_FAILURE,
            terminal_reason=TerminalReason.START_FAILED,
            evidence_payload={
                "kind": "sandbox_startup_failure_receipt",
                "compose_project": current.compose_project,
                "workspace_path": current.workspace_path,
                "failure_stage": "reconciliation_absent_runtime",
                "observed_at": observed_at,
                "docker_present": False,
            },
            operation_id_prefix="reconcile-starting-failed",
            expected_owner_instance_id=current.owner_instance_id,
            expected_lease_epoch=current.lease_epoch if current.owner_instance_id else None,
            terminal_at=observed_at,
            cleanup_due_at=self.lifecycle_service.policy.cleanup_due_at_for(
                state=SandboxState.TERMINAL,
                terminal_reason=TerminalReason.START_FAILED,
                reference_time=observed_at,
            ),
        )

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
        observed_resources: list[ObservedDockerResource],
    ) -> SandboxLifecycleRecord:
        confidence, sandbox_id, run_id = self._ownership_metadata(
            compose_project=compose_project, observed_resources=observed_resources
        )
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
            cleanup_state=CleanupState.SCHEDULED
            if terminal_reason is TerminalReason.ORPHAN_DETECTED
            else CleanupState.NONE,
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
    def _ownership_metadata(
        *,
        compose_project: str,
        observed_resources: list[ObservedDockerResource],
    ) -> tuple[OwnershipConfidence, str, str | None]:
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
        return await self.lifecycle_service.cleanup_executor.execute_claimed_cleanup(
            record=record,
            compose_path=self._compose_path(record.workspace_path),
        )

    async def _terminalize_active_restart_loop_if_needed(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> SandboxLifecycleRecord | None:
        container_rows = await self.runtime_inspector.list_project_container_rows(
            compose_project=record.compose_project
        )
        if not container_rows:
            return None
        tracked_rows = self.runtime_inspector.tracked_container_rows(container_rows)
        if not tracked_rows:
            return await self._terminalize_non_running_active_runtime(
                record=record,
                observed_at=observed_at,
                tracked_rows=container_rows,
            )
        assessed = await self.restart_policy.observe_runtime_health(
            sandbox_id=record.sandbox_id,
            container_rows=tracked_rows,
            observed_at=observed_at,
        )
        if assessed is not None and assessed.state is SandboxState.TERMINAL:
            return assessed
        if not self.runtime_inspector.all_core_services_running(container_rows):
            return await self._terminalize_non_running_active_runtime(
                record=record,
                observed_at=observed_at,
                tracked_rows=tracked_rows,
            )
        return None

    async def _terminalize_non_running_active_runtime(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
        tracked_rows: list[dict[str, object]],
    ) -> SandboxLifecycleRecord:
        return await self.lifecycle_service.terminal_outcomes.record_workflow_terminal_outcome(
            sandbox_id=record.sandbox_id,
            terminal_reason=TerminalReason.RESTART_LOOP,
            evidence_payload={
                "kind": "sandbox_runtime_non_running_receipt",
                "compose_project": record.compose_project,
                "observed_at": observed_at,
                "container_rows": tracked_rows,
            },
            operation_id_prefix="runtime-non-running",
            expected_owner_instance_id=record.owner_instance_id,
            expected_lease_epoch=record.lease_epoch,
            terminal_at=observed_at,
            cleanup_due_at=self.lifecycle_service.policy.cleanup_due_at_for(
                state=SandboxState.TERMINAL,
                terminal_reason=TerminalReason.RESTART_LOOP,
                reference_time=observed_at,
            ),
        )

    async def _schedule_cleanup_if_needed(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> SandboxLifecycleRecord:
        if record.state is not SandboxState.TERMINAL or record.cleanup_state is not CleanupState.NONE:
            return record
        return (
            await self.lifecycle_service.mutations.transition_state(
                sandbox_id=record.sandbox_id,
                operation_id=f"cleanup-scheduled:{record.sandbox_id}:{record.record_version}",
                expected_record_version=record.record_version,
                event=LifecycleEvent.CLEANUP_SCHEDULED,
                next_state=SandboxState.TERMINAL,
                cleanup_state=CleanupState.SCHEDULED,
                cleanup_due_at=record.cleanup_due_at or observed_at,
            )
        ).record

    async def _terminalize_hard_max_age(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> SandboxLifecycleRecord:
        return await self.lifecycle_service.terminal_outcomes.record_policy_terminal_outcome(
            sandbox_id=record.sandbox_id,
            event=LifecycleEvent.HARD_MAX_AGE_REACHED,
            terminal_reason=TerminalReason.HARD_MAX_AGE,
            evidence_payload={
                "kind": "sandbox_policy_terminal_receipt",
                "compose_project": record.compose_project,
                "workspace_path": record.workspace_path,
                "policy_match": "hard_max_age_elapsed",
            },
            operation_id_prefix="hard-max-age",
            expected_owner_instance_id=record.owner_instance_id,
            expected_lease_epoch=record.lease_epoch if record.owner_instance_id else None,
            terminal_at=observed_at,
            cleanup_due_at=observed_at,
        )
