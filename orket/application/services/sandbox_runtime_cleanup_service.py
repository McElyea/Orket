from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from orket.application.services.sandbox_cleanup_decision_service import SandboxCleanupDecisionService
from orket.core.domain.sandbox_cleanup import DockerResourceType
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, SandboxLifecycleError, SandboxState
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord

if TYPE_CHECKING:
    from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService


class SandboxRuntimeCleanupService:
    """Executes claimed sandbox cleanup with compose-first and label-scoped fallback behavior."""

    def __init__(self, *, lifecycle_service: SandboxRuntimeLifecycleService) -> None:
        self.lifecycle_service = lifecycle_service
        self.decision_service = SandboxCleanupDecisionService(
            event_publisher=lifecycle_service.event_publisher
        )

    async def preview_cleanup(
        self,
        *,
        record: SandboxLifecycleRecord,
        compose_path: Path,
    ) -> dict[str, object]:
        observed_at = self.lifecycle_service._now()
        observed_resources = await self.lifecycle_service._observe_project_resources(record.compose_project)
        authority = self.lifecycle_service.cleanup_authority.decide(
            record=record,
            observed_resources=observed_resources,
            compose_path_available=compose_path.exists(),
        )
        decision = self.decision_service.build_decision(
            record=record,
            compose_path=compose_path,
            observed_resources=observed_resources,
            authority=authority,
            dry_run=True,
        )
        await self.decision_service.emit_decision(decision=decision, observed_at=observed_at)
        return decision.to_payload()

    async def execute_claimed_cleanup(
        self,
        *,
        record: SandboxLifecycleRecord,
        compose_path: Path,
    ) -> SandboxLifecycleRecord:
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
        authority = self.lifecycle_service.cleanup_authority.decide(
            record=current,
            observed_resources=observed_before,
            compose_path_available=compose_path.exists(),
        )
        decision = self.decision_service.build_decision(
            record=current,
            compose_path=compose_path,
            observed_resources=observed_before,
            authority=authority,
            dry_run=False,
        )
        await self.decision_service.emit_decision(
            decision=decision,
            observed_at=self.lifecycle_service._now(),
        )
        if authority.compose_cleanup_allowed:
            errors = await self._run_compose_cleanup(current=current, compose_path=compose_path)
        elif authority.fallback_resource_names:
            errors = await self._run_fallback_cleanup(
                observed_resources=observed_before,
                allowed_names=set(authority.fallback_resource_names),
            )
        else:
            await self.lifecycle_service._mark_cleanup_failed(current, "cleanup authority blocked")
            await self.decision_service.emit_execution_result(
                decision=decision,
                observed_at=self.lifecycle_service._now(),
                cleanup_result="blocked",
                error="cleanup authority blocked",
            )
            raise RuntimeError(f"Cleanup authority blocked for sandbox {current.sandbox_id}")
        observed_after = await self.lifecycle_service._observe_project_resources(current.compose_project)
        verification = self.lifecycle_service.cleanup_verifier.verify_absence(
            record=current,
            observed_resources=observed_after,
        )
        if observed_after or not verification.success:
            error = "; ".join(
                token
                for token in [
                    ", ".join(errors) if errors else "",
                    ",".join(verification.remaining_expected),
                    ",".join(verification.unexpected_managed_present),
                    ",".join(sorted(resource.name for resource in observed_after)),
                ]
                if token
            ) or "cleanup verification failed"
            await self.lifecycle_service._mark_cleanup_failed(current, error)
            await self.decision_service.emit_execution_result(
                decision=decision,
                observed_at=self.lifecycle_service._now(),
                cleanup_result="failed",
                error=error,
            )
            raise RuntimeError(f"Failed to verify sandbox cleanup: {error}")
        current = await self.lifecycle_service.repository.get_record(current.sandbox_id)
        if current is None:
            raise SandboxLifecycleError(f"Sandbox lifecycle record not found for {record.sandbox_id}")
        cleaned = (
            await self.lifecycle_service.mutations.transition_state(
                sandbox_id=current.sandbox_id,
                operation_id=f"cleanup-complete:{current.sandbox_id}:{current.record_version}",
                expected_record_version=current.record_version,
                event=LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
                next_state=SandboxState.CLEANED,
                cleanup_state=CleanupState.COMPLETED,
            )
        ).record
        await self.decision_service.emit_execution_result(
            decision=decision,
            observed_at=self.lifecycle_service._now(),
            cleanup_result="verified_complete",
        )
        return cleaned

    async def _run_compose_cleanup(
        self,
        *,
        current: SandboxLifecycleRecord,
        compose_path: Path,
    ) -> list[str]:
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
        return [result.stderr.strip()] if result.stderr.strip() else []

    async def _run_fallback_cleanup(
        self,
        *,
        observed_resources,
        allowed_names: set[str],
    ) -> list[str]:
        errors: list[str] = []
        priority = {
            DockerResourceType.CONTAINER: 0,
            DockerResourceType.NETWORK: 1,
            DockerResourceType.MANAGED_VOLUME: 2,
        }
        allowed_resources = sorted(
            (resource for resource in observed_resources if resource.name in allowed_names),
            key=lambda resource: (priority[resource.resource_type], resource.name),
        )
        for resource in allowed_resources:
            result = await self.lifecycle_service.command_runner.run_async(*self._remove_command(resource.resource_type, resource.name))
            if result.stderr.strip():
                errors.append(f"{resource.name}:{result.stderr.strip()}")
        if not allowed_resources:
            errors.append("no-fallback-authority")
        return errors

    @staticmethod
    def _remove_command(resource_type: DockerResourceType, resource_name: str) -> tuple[str, ...]:
        if resource_type is DockerResourceType.CONTAINER:
            return ("docker", "rm", "-f", resource_name)
        if resource_type is DockerResourceType.NETWORK:
            return ("docker", "network", "rm", resource_name)
        return ("docker", "volume", "rm", "-f", resource_name)
