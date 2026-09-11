from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

from orket.application.services.governed_agent_effect_control_service import GovernedAgentEffectControlService
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from orket.application.services.governed_agent_run_control_service import GovernedAgentRunControlService
from orket.application.services.governed_agent_scheduled_wake_service import (
    GovernedAgentScheduledWakeService,
)
from orket.application.services.governed_agent_supervisor import GovernedAgentSupervisor
from orket.application.services.governed_agent_wake_control_service import (
    GovernedAgentWakeControlService,
)
from orket.application.services.governed_agent_wake_ingress_service import (
    GovernedAgentWakeIngressService,
)
from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeControlRepository,
    GovernedAgentWakeControlResult,
    GovernedAgentWakeEnqueueResult,
    GovernedAgentWakeRecord,
    GovernedAgentWakeRepository,
)
from orket.application.services.governed_agent_webhook_ingress_service import (
    GovernedAgentWebhookIngressService,
)


class GovernedAgentRuntime:
    """Application-owned continuous-agent ingress, inspection, and lifecycle."""

    def __init__(
        self,
        *,
        wake_repository: GovernedAgentWakeRepository,
        wake_control_repository: GovernedAgentWakeControlRepository,
        scheduled_wakes: GovernedAgentScheduledWakeService,
        webhook_ingress: GovernedAgentWebhookIngressService,
        effect_controls: GovernedAgentEffectControlService,
        run_controls: GovernedAgentRunControlService,
        inspector: GovernedAgentInspectionService,
        supervisor: GovernedAgentSupervisor,
        supervisor_enabled: bool,
        now_utc: Callable[[], str],
        provider_mode: str,
        capacity_limit: int,
    ) -> None:
        self._wakes = wake_repository
        self._inspector = inspector
        self._supervisor = supervisor
        self._enabled = supervisor_enabled
        self._provider_mode = provider_mode
        self._capacity_limit = capacity_limit
        self._ingress = GovernedAgentWakeIngressService(
            wake_repository=wake_repository,
            now_utc=now_utc,
            notify_ready=supervisor.notify,
        )
        self.wake_controls = GovernedAgentWakeControlService(wake_control_repository)
        self.scheduled_wakes = scheduled_wakes
        self.webhook_ingress = webhook_ingress
        self.effect_controls = effect_controls
        self.run_controls = run_controls

    async def enqueue_api_wake(self, payload: Mapping[str, Any]) -> GovernedAgentWakeEnqueueResult:
        return await self._ingress.enqueue(payload, source="api")

    async def get_wake(self, *, wake_id: str) -> GovernedAgentWakeRecord | None:
        return await self._wakes.get_wake(wake_id=wake_id)

    async def list_wakes(self, *, run_id: str | None = None) -> tuple[GovernedAgentWakeRecord, ...]:
        return cast(
            tuple[GovernedAgentWakeRecord, ...],
            await self._wakes.list_wakes(target_run_id=run_id),
        )

    async def cancel_wake(
        self,
        *,
        wake_id: str,
        payload: Mapping[str, Any],
    ) -> GovernedAgentWakeControlResult:
        return await self.wake_controls.cancel(wake_id=wake_id, payload=payload)

    async def recover_wake(
        self,
        *,
        wake_id: str,
        payload: Mapping[str, Any],
    ) -> GovernedAgentWakeControlResult:
        result = await self.wake_controls.recover(wake_id=wake_id, payload=payload)
        if result.status in {"applied", "idempotent"} and result.wake is not None and result.wake.state == "queued":
            self._supervisor.notify()
        return result

    async def inspect(self, *, run_id: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, await self._inspector.inspect(run_id=run_id))

    async def replay(self, *, run_id: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, await self._inspector.replay(run_id=run_id))

    async def start(self, task_owner: Any) -> None:
        if self._enabled and not self._supervisor.running:
            # Initialize WAL and wake schema before ingress can race the first claim.
            await self._wakes.list_wakes()
            self._supervisor.start(task_owner)

    async def close(self) -> None:
        await self._supervisor.close()

    def status(self) -> dict[str, Any]:
        return {
            "object_type": "governed_agent_runtime_status",
            "schema_version": "governed_agent_runtime_status.v1",
            "supervisor_enabled": self._enabled,
            "supervisor_running": self._supervisor.running,
            "provider_mode": self._provider_mode,
            "capacity_limit": self._capacity_limit,
            "webhook_ingress_configured": self.webhook_ingress.configured(),
        }


def governed_agent_wake_view(wake: GovernedAgentWakeRecord) -> dict[str, Any]:
    return {
        "wake_id": wake.wake_id,
        "source": wake.source,
        "target_kind": wake.target_kind,
        "target_run_id": wake.target_run_id,
        "workload_id": wake.workload_id,
        "occurrence_id": wake.occurrence_id,
        "state": wake.state,
        "claim_owner_id": wake.claim_owner_id,
        "lease_expires_at_utc": wake.lease_expires_at_utc,
        "fencing_generation": wake.fencing_generation,
        "cancellation_epoch": wake.cancellation_epoch,
        "uncertainty": wake.uncertainty,
        "result_ref": wake.result_ref,
        "last_reason": wake.last_reason,
        "trigger": _trigger_view(wake.payload.get("trigger")),
    }


def _trigger_view(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None
