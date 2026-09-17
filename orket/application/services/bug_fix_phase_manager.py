"""Own bug-fix persistence and events using explicitly composed time and workspace."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, TypeVar

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.core.domain.bug_fix_phase import BugDiscoveryMetrics, BugFixPhase, BugFixPhaseStatus
from orket.logging import log_event

Result = TypeVar("Result")


class BugFixPhasePersistenceError(RuntimeError):
    """A persisted phase did not match the requested value; no event was published."""


class BugFixPhaseManager:
    """Serialize this owner's transitions and retain admitted effects through cancellation."""

    def __init__(
        self, organization_config: dict[str, Any] | None = None, db: Any | None = None,
        *, workspace: Path, now_utc: Callable[[], datetime],
    ) -> None:
        self.config = dict(organization_config or {})
        self.db = db
        self.workspace = Path(workspace)
        self.now_utc = now_utc
        self.active_phases: dict[str, BugFixPhase] = {}
        self._lock = asyncio.Lock()

    async def _execute(self, operation: Callable[[], Awaitable[Result]]) -> Result:
        # Waiting for ownership is cancellable. Once admitted, persistence and its event drain together.
        async with self._lock:
            return await run_owned_io(operation, label="bug-fix-phase-transition", preserve_failure=True)

    async def start_phase(self, rock_id: str) -> BugFixPhase:
        return await self._execute(partial(self._start_phase, rock_id))

    async def _start_phase(self, rock_id: str) -> BugFixPhase:
        initial_days = self.config.get("bug_fix_initial_days", 7)
        phase = BugFixPhase(
            id=f"phase-{rock_id}", rock_id=rock_id,
            started_at=self.now_utc().isoformat(),
            initial_duration_days=initial_days,
            max_duration_days=self.config.get("bug_fix_max_days", 28),
            current_duration_days=initial_days,
            metrics=BugDiscoveryMetrics(
                high_rate_threshold=self.config.get("bug_discovery_high_rate", 5.0),
                critical_threshold=self.config.get("bug_critical_threshold", 3),
            ),
        )
        await self._publish(phase, "bug_fix_phase_started", {"rock_id": rock_id, "ends_at": phase.scheduled_end})
        return phase.model_copy(deep=True)

    async def update_metrics(self, rock_id: str, bug_issue_ids: list[str], critical_bug_ids: list[str]) -> None:
        await self._execute(partial(self._update_metrics, rock_id, tuple(bug_issue_ids), tuple(critical_bug_ids)))

    async def _update_metrics(self, rock_id: str, bug_ids: tuple[str, ...], critical_ids: tuple[str, ...]) -> None:
        phase = self.active_phases.get(rock_id)
        if phase is None and self.db is not None:
            phase = await self.db.get_bug_fix_phase(rock_id)
        if phase is None:
            return
        phase = phase.model_copy(deep=True)
        phase.bug_issue_ids = list(bug_ids)
        phase.metrics.total_bugs = len(bug_ids)
        phase.metrics.critical_bugs = len(critical_ids)
        elapsed_days = (self.now_utc() - datetime.fromisoformat(phase.started_at)).days
        phase.metrics.discovery_rate = len(bug_ids) / max(elapsed_days, 1)
        await self._publish(phase)

    async def check_and_extend(self, rock_id: str) -> bool:
        return await self._execute(partial(self._check_and_extend, rock_id))

    async def _check_and_extend(self, rock_id: str) -> bool:
        phase = self.active_phases.get(rock_id)
        if phase is None or not phase.should_extend():
            return False
        phase = phase.model_copy(deep=True)
        reasons = []
        if phase.metrics.discovery_rate > phase.metrics.high_rate_threshold:
            reasons.append(f"High rate ({phase.metrics.discovery_rate:.1f}/d)")
        if phase.metrics.critical_bugs > phase.metrics.critical_threshold:
            reasons.append(f"{phase.metrics.critical_bugs} critical bugs")
        reason = "; ".join(reasons) or "Quality concerns"
        phase.extend_phase(reason, now=self.now_utc())
        await self._publish(phase, "bug_fix_phase_extended", {
            "rock_id": rock_id, "new_end": phase.scheduled_end, "reason": reason,
        })
        return True

    async def end_phase(self, rock_id: str) -> str | None:
        return await self._execute(partial(self._end_phase, rock_id))

    async def _end_phase(self, rock_id: str) -> str | None:
        phase = self.active_phases.get(rock_id)
        if phase is None:
            return None
        phase = phase.model_copy(deep=True)
        phase.status = BugFixPhaseStatus.COMPLETED
        phase.actual_end = self.now_utc().isoformat()
        phase2_rock_id = f"{rock_id}-phase2" if phase.bug_issue_ids else None
        phase.phase2_rock_id = phase2_rock_id
        await self._publish(phase, "bug_fix_phase_completed", {"rock_id": rock_id, "phase2_rock": phase2_rock_id})
        return phase2_rock_id

    async def _publish(self, phase: BugFixPhase, event: str | None = None, payload: dict | None = None) -> None:
        if self.db is not None:
            await self.db.save_bug_fix_phase(phase)
            saved = await self.db.get_bug_fix_phase(phase.rock_id)
            if saved is None or saved.model_dump() != phase.model_dump():
                raise BugFixPhasePersistenceError(f"Bug-fix phase did not round-trip: {phase.rock_id}")
        if phase.status == BugFixPhaseStatus.COMPLETED:
            self.active_phases.pop(phase.rock_id, None)
        else:
            self.active_phases[phase.rock_id] = phase.model_copy(deep=True)
        if event is not None:
            await run_owned_thread(
                partial(log_event, event, payload, self.workspace), label=f"bug-fix-event:{event}",
            )
