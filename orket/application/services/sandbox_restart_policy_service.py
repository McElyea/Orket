from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.core.domain.sandbox_lifecycle import SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord

if TYPE_CHECKING:
    from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService


@dataclass(frozen=True)
class SandboxServiceRuntimeSnapshot:
    observed_at: str
    service_name: str
    container_name: str
    state: str
    health_status: str | None
    restart_count: int


@dataclass(frozen=True)
class SandboxRestartAssessment:
    payload: dict[str, object]
    should_terminalize: bool


class SandboxRestartPolicyService:
    """Applies restart-loop and continuous-unhealthy policy using durable health observations."""

    def __init__(
        self,
        *,
        lifecycle_service: SandboxRuntimeLifecycleService,
        policy: SandboxLifecyclePolicy | None = None,
    ) -> None:
        self.lifecycle_service = lifecycle_service
        self.policy = policy or lifecycle_service.policy

    async def observe_runtime_health(
        self,
        *,
        sandbox_id: str,
        container_rows: list[dict[str, object]],
        observed_at: str,
    ):
        record = await self.lifecycle_service.repository.get_record(sandbox_id)
        if record is None or record.state not in {SandboxState.ACTIVE, SandboxState.STARTING}:
            return record
        if record.owner_instance_id not in {None, self.lifecycle_service.instance_id}:
            return record
        current_snapshots = await self._inspect_containers(container_rows=container_rows, observed_at=observed_at)
        if not current_snapshots:
            return record
        prior_events = await self.lifecycle_service.repository.list_events(sandbox_id)
        prior_snapshots = self._extract_prior_snapshots(prior_events)
        assessment = self.assess_runtime_health(
            policy=self.policy,
            current_snapshots=current_snapshots,
            prior_snapshots=prior_snapshots,
        )
        if assessment.should_terminalize and record.state is SandboxState.ACTIVE:
            terminal = await self.lifecycle_service.terminal_outcomes.record_workflow_terminal_outcome(
                sandbox_id=record.sandbox_id,
                terminal_reason=TerminalReason.RESTART_LOOP,
                evidence_payload=assessment.payload,
                operation_id_prefix="restart-loop",
                expected_owner_instance_id=self.lifecycle_service.instance_id,
                expected_lease_epoch=record.lease_epoch,
                terminal_at=observed_at,
                cleanup_due_at=self.policy.cleanup_due_at_for(
                    state=SandboxState.TERMINAL,
                    terminal_reason=TerminalReason.RESTART_LOOP,
                    reference_time=observed_at,
                ),
            )
            await self._emit_event(
                sandbox_id=sandbox_id,
                observed_at=observed_at,
                event_type="sandbox.restart_loop_classified",
                payload=assessment.payload,
            )
            return terminal
        await self._emit_event(
            sandbox_id=sandbox_id,
            observed_at=observed_at,
            event_type="sandbox.runtime_health_observed",
            payload=assessment.payload,
        )
        return record

    @staticmethod
    def assess_runtime_health(
        *,
        policy: SandboxLifecyclePolicy,
        current_snapshots: list[SandboxServiceRuntimeSnapshot],
        prior_snapshots: list[SandboxServiceRuntimeSnapshot],
    ) -> SandboxRestartAssessment:
        observed_at = max(snapshot.observed_at for snapshot in current_snapshots)
        observed_at_dt = datetime.fromisoformat(observed_at)
        window_start = observed_at_dt - timedelta(seconds=policy.restart_window_seconds)
        restart_services: list[dict[str, object]] = []
        health_services: list[dict[str, object]] = []
        triggered_services: list[str] = []

        for current in sorted(current_snapshots, key=lambda item: (item.service_name, item.container_name)):
            history = [
                snapshot
                for snapshot in prior_snapshots
                if snapshot.service_name == current.service_name
                and datetime.fromisoformat(snapshot.observed_at) >= window_start
            ]
            restart_baseline = min([current.restart_count, *[snapshot.restart_count for snapshot in history]])
            restart_delta = max(0, current.restart_count - restart_baseline)
            unhealthy_seconds = SandboxRestartPolicyService._continuous_unhealthy_seconds(
                current=current,
                prior_snapshots=prior_snapshots,
            )
            restart_threshold_exceeded = restart_delta > policy.restart_threshold_count
            unhealthy_threshold_exceeded = unhealthy_seconds >= policy.unhealthy_duration_seconds
            if restart_threshold_exceeded or unhealthy_threshold_exceeded:
                triggered_services.append(current.service_name)
            restart_services.append(
                {
                    "service": current.service_name,
                    "container_name": current.container_name,
                    "state": current.state,
                    "health_status": current.health_status,
                    "restart_count": current.restart_count,
                    "window_restart_delta": restart_delta,
                    "restart_threshold_exceeded": restart_threshold_exceeded,
                    "continuous_unhealthy_seconds": unhealthy_seconds,
                    "unhealthy_threshold_exceeded": unhealthy_threshold_exceeded,
                }
            )
            health_services.append(
                {
                    "service": current.service_name,
                    "container_name": current.container_name,
                    "state": current.state,
                    "health_status": current.health_status,
                    "continuous_unhealthy_seconds": unhealthy_seconds,
                }
            )

        payload = {
            "restart_summary": {
                "observed_at": observed_at,
                "restart_threshold_count": policy.restart_threshold_count,
                "restart_window_seconds": policy.restart_window_seconds,
                "services": restart_services,
                "triggered_services": sorted(set(triggered_services)),
            },
            "health_summary": {
                "observed_at": observed_at,
                "unhealthy_duration_seconds": policy.unhealthy_duration_seconds,
                "services": health_services,
            },
            "terminal_reason": TerminalReason.RESTART_LOOP.value if triggered_services else None,
        }
        return SandboxRestartAssessment(payload=payload, should_terminalize=bool(triggered_services))

    async def _inspect_containers(
        self,
        *,
        container_rows: list[dict[str, object]],
        observed_at: str,
    ) -> list[SandboxServiceRuntimeSnapshot]:
        container_names = [
            str(row.get("Name") or "").strip() for row in container_rows if str(row.get("Name") or "").strip()
        ]
        if not container_names:
            return []
        result = await self.lifecycle_service.command_runner.run_async("docker", "inspect", *container_names)
        if result.returncode != 0:
            return []
        payload = json.loads(result.stdout or "[]")
        if not isinstance(payload, list):
            return []
        return [
            SandboxServiceRuntimeSnapshot(
                observed_at=observed_at,
                service_name=str(
                    ((item.get("Config") or {}).get("Labels") or {}).get("com.docker.compose.service")
                    or str(item.get("Name") or "").lstrip("/"),
                ),
                container_name=str(item.get("Name") or "").lstrip("/"),
                state=str((item.get("State") or {}).get("Status") or ""),
                health_status=((item.get("State") or {}).get("Health") or {}).get("Status"),
                restart_count=int(item.get("RestartCount") or 0),
            )
            for item in payload
            if isinstance(item, dict)
        ]

    @staticmethod
    def _extract_prior_snapshots(events: list[SandboxLifecycleEventRecord]) -> list[SandboxServiceRuntimeSnapshot]:
        snapshots: list[SandboxServiceRuntimeSnapshot] = []
        for event in events:
            restart_summary = event.payload.get("restart_summary")
            if not isinstance(restart_summary, dict):
                continue
            observed_at = str(restart_summary.get("observed_at") or event.created_at)
            services = restart_summary.get("services")
            if not isinstance(services, list):
                continue
            for service in services:
                if not isinstance(service, dict):
                    continue
                snapshots.append(
                    SandboxServiceRuntimeSnapshot(
                        observed_at=observed_at,
                        service_name=str(service.get("service") or ""),
                        container_name=str(service.get("container_name") or ""),
                        state=str(service.get("state") or ""),
                        health_status=service.get("health_status"),
                        restart_count=int(service.get("restart_count") or 0),
                    )
                )
        return snapshots

    @staticmethod
    def _continuous_unhealthy_seconds(
        *,
        current: SandboxServiceRuntimeSnapshot,
        prior_snapshots: list[SandboxServiceRuntimeSnapshot],
    ) -> int:
        if current.health_status != "unhealthy":
            return 0
        streak_start = datetime.fromisoformat(current.observed_at)
        history = [snapshot for snapshot in prior_snapshots if snapshot.service_name == current.service_name]
        for snapshot in sorted(history, key=lambda item: item.observed_at, reverse=True):
            if snapshot.health_status != "unhealthy":
                break
            streak_start = datetime.fromisoformat(snapshot.observed_at)
        return max(0, int((datetime.fromisoformat(current.observed_at) - streak_start).total_seconds()))

    async def _emit_event(
        self,
        *,
        sandbox_id: str,
        observed_at: str,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        await self.lifecycle_service.event_publisher.emit(
            sandbox_id=sandbox_id,
            created_at=observed_at,
            event_type=event_type,
            payload=payload,
        )
