from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError, SandboxState, TerminalReason


@dataclass(frozen=True)
class SandboxLifecyclePolicy:
    lease_duration_seconds: int = 300
    heartbeat_interval_seconds: int = 30
    ttl_success_minutes: int = 15
    ttl_failed_hours: int = 1
    ttl_blocked_hours: int = 1
    ttl_canceled_hours: int = 1
    ttl_reclaimable_hours: int = 1
    ttl_orphan_verified_hours: int = 1
    ttl_hard_max_age_hours: int = 72
    restart_threshold_count: int = 5
    restart_window_seconds: int = 300
    unhealthy_duration_seconds: int = 600

    def cleanup_due_at_for(
        self,
        *,
        state: SandboxState,
        terminal_reason: TerminalReason,
        reference_time: str,
    ) -> str | None:
        base = _parse_iso_datetime(reference_time)
        delta = self._cleanup_delta(state=state, terminal_reason=terminal_reason)
        if delta is None:
            return None
        return (base + delta).isoformat()

    def _cleanup_delta(self, *, state: SandboxState, terminal_reason: TerminalReason) -> timedelta | None:
        if state is SandboxState.RECLAIMABLE:
            return timedelta(hours=self.ttl_reclaimable_hours)
        if state is SandboxState.ORPHANED:
            if terminal_reason is TerminalReason.ORPHAN_DETECTED:
                return timedelta(hours=self.ttl_orphan_verified_hours)
            if terminal_reason is TerminalReason.ORPHAN_UNVERIFIED_OWNERSHIP:
                return None
        if state is not SandboxState.TERMINAL:
            return None
        if terminal_reason is TerminalReason.SUCCESS:
            return timedelta(minutes=self.ttl_success_minutes)
        if terminal_reason in {
            TerminalReason.FAILED,
            TerminalReason.CREATE_FAILED,
            TerminalReason.START_FAILED,
            TerminalReason.RESTART_LOOP,
            TerminalReason.LOST_RUNTIME,
        }:
            return timedelta(hours=self.ttl_failed_hours)
        if terminal_reason is TerminalReason.BLOCKED:
            return timedelta(hours=self.ttl_blocked_hours)
        if terminal_reason is TerminalReason.CANCELED:
            return timedelta(hours=self.ttl_canceled_hours)
        if terminal_reason in {TerminalReason.LEASE_EXPIRED, TerminalReason.HARD_MAX_AGE}:
            return timedelta(0)
        return None

    def hard_max_age_elapsed(self, *, created_at: str, observed_at: str) -> bool:
        created = _parse_iso_datetime(created_at)
        observed = _parse_iso_datetime(observed_at)
        return observed >= created + timedelta(hours=self.ttl_hard_max_age_hours)


def _parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise SandboxLifecycleError(f"Invalid ISO datetime: {value}") from exc
