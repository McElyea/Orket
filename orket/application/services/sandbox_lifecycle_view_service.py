from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


@dataclass(frozen=True)
class SandboxLifecycleOperatorView:
    sandbox_id: str
    compose_project: str
    state: str
    cleanup_state: str
    terminal_reason: str | None
    owner_instance_id: str | None
    cleanup_owner_instance_id: str | None
    lease_expires_at: str | None
    heartbeat_age_seconds: int | None
    restart_summary: dict[str, object] = field(default_factory=dict)
    cleanup_eligible: bool = False
    cleanup_due_at: str | None = None
    requires_reconciliation: bool = False


class SandboxLifecycleViewService:
    """Projects durable lifecycle records into operator-facing read models."""

    def __init__(self, repository):
        self.repository = repository

    async def list_views(self, *, observed_at: str) -> list[SandboxLifecycleOperatorView]:
        records = await self.repository.list_records()
        views = []
        for record in records:
            events = await self.repository.list_events(record.sandbox_id)
            views.append(self.build_view(record=record, observed_at=observed_at, events=events))
        return sorted(views, key=lambda item: (item.cleanup_due_at or "", item.sandbox_id))

    def build_view(
        self, *, record: SandboxLifecycleRecord, observed_at: str, events: list | None = None
    ) -> SandboxLifecycleOperatorView:
        heartbeat_age = self._heartbeat_age_seconds(record.last_heartbeat_at, observed_at)
        cleanup_eligible = (
            record.state in {SandboxState.TERMINAL, SandboxState.RECLAIMABLE, SandboxState.ORPHANED}
            and record.cleanup_state in {CleanupState.NONE, CleanupState.SCHEDULED}
            and not record.requires_reconciliation
        )
        return SandboxLifecycleOperatorView(
            sandbox_id=record.sandbox_id,
            compose_project=record.compose_project,
            state=record.state.value,
            cleanup_state=record.cleanup_state.value,
            terminal_reason=record.terminal_reason.value if record.terminal_reason else None,
            owner_instance_id=record.owner_instance_id,
            cleanup_owner_instance_id=record.cleanup_owner_instance_id,
            lease_expires_at=record.lease_expires_at,
            heartbeat_age_seconds=heartbeat_age,
            restart_summary=self._restart_summary(events or []),
            cleanup_eligible=cleanup_eligible,
            cleanup_due_at=record.cleanup_due_at,
            requires_reconciliation=record.requires_reconciliation,
        )

    @staticmethod
    def _heartbeat_age_seconds(last_heartbeat_at: str | None, observed_at: str) -> int | None:
        if not last_heartbeat_at:
            return None
        start = datetime.fromisoformat(last_heartbeat_at)
        end = datetime.fromisoformat(observed_at)
        return max(0, int((end - start).total_seconds()))

    @staticmethod
    def _restart_summary(events: list) -> dict[str, object]:
        for event in sorted(events, key=lambda item: (item.created_at, item.event_id), reverse=True):
            if str(event.event_type).startswith("sandbox.runtime_health") or str(event.event_type).startswith(
                "sandbox.restart_loop"
            ):
                if isinstance(event.payload, dict):
                    return dict(event.payload)
        return {}
