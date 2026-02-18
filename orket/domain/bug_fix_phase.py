"""
Bug Fix Phase Manager - Phase 3: Elegant Failure & Recovery

Domain Service: Manages the post-deployment bug discovery and fixing phase.
Reconstructed for async persistence.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field
import enum
import json
from pathlib import Path

from orket.logging import log_event


class BugFixPhaseStatus(str, enum.Enum):
    """Bug fix phase lifecycle states."""
    ACTIVE = "active"
    EXTENDED = "extended"
    COMPLETED = "completed"
    ABORTED = "aborted"


class BugDiscoveryMetrics(BaseModel):
    """Metrics for tracking bug discovery rate."""
    total_bugs: int = 0
    critical_bugs: int = 0
    bugs_found_today: int = 0
    bugs_fixed_today: int = 0
    discovery_rate: float = 0.0

    high_rate_threshold: float = 5.0
    critical_threshold: int = 3


class BugFixPhase(BaseModel):
    """Domain Entity: Represents a post-deployment bug fix window."""
    id: str
    rock_id: str
    status: BugFixPhaseStatus = Field(default=BugFixPhaseStatus.ACTIVE)
    initial_duration_days: int = 7
    max_duration_days: int = 28
    current_duration_days: int = 7
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    scheduled_end: str = Field(default_factory=lambda: (datetime.now(UTC) + timedelta(days=7)).isoformat())
    actual_end: Optional[str] = None
    metrics: BugDiscoveryMetrics = Field(default_factory=BugDiscoveryMetrics)
    bug_issue_ids: List[str] = Field(default_factory=list)
    phase2_rock_id: Optional[str] = None
    extensions: List[Dict[str, str]] = Field(default_factory=list)

    def should_extend(self) -> bool:
        if self.current_duration_days >= self.max_duration_days:
            return False
        if self.metrics.discovery_rate > self.metrics.high_rate_threshold:
            return True
        if self.metrics.critical_bugs > self.metrics.critical_threshold:
            return True
        return False

    def extend_phase(self, reason: str, added_days: int = 7) -> None:
        new_duration = min(self.current_duration_days + added_days, self.max_duration_days)
        actual_added = new_duration - self.current_duration_days
        self.extensions.append({
            "date": datetime.now(UTC).isoformat(),
            "reason": reason,
            "added_days": str(actual_added)
        })
        self.current_duration_days = new_duration
        self.scheduled_end = (datetime.fromisoformat(self.started_at) + timedelta(days=new_duration)).isoformat()
        self.status = BugFixPhaseStatus.EXTENDED

    def is_expired(self) -> bool:
        return datetime.now(UTC) >= datetime.fromisoformat(self.scheduled_end)


class BugFixPhaseManager:
    """Application Service: Manages bug fix phases."""

    def __init__(self, organization_config: Optional[Dict] = None, db: Optional[Any] = None):
        self.config = organization_config or {}
        self.db = db
        self.active_phases: Dict[str, BugFixPhase] = {}

    async def start_phase(self, rock_id: str) -> BugFixPhase:
        """Begin bug fix phase for a Rock."""
        # Read thresholds from org config
        initial_days = self.config.get("bug_fix_initial_days", 7)
        max_days = self.config.get("bug_fix_max_days", 28)
        high_rate = self.config.get("bug_discovery_high_rate", 5.0)
        critical_count = self.config.get("bug_critical_threshold", 3)

        metrics = BugDiscoveryMetrics(
            high_rate_threshold=high_rate,
            critical_threshold=critical_count
        )

        phase = BugFixPhase(
            id=f"phase-{rock_id}",
            rock_id=rock_id,
            initial_duration_days=initial_days,
            max_duration_days=max_days,
            current_duration_days=initial_days,
            metrics=metrics,
            scheduled_end=(datetime.now(UTC) + timedelta(days=initial_days)).isoformat()
        )

        if self.db and hasattr(self.db, "save_bug_fix_phase"):
            await self.db.save_bug_fix_phase(phase)
            
        self.active_phases[rock_id] = phase
        log_event("bug_fix_phase_started", {"rock_id": rock_id, "ends_at": phase.scheduled_end}, Path("."))
        return phase

    async def update_metrics(self, rock_id: str, bug_issue_ids: List[str], critical_bug_ids: List[str]) -> None:
        """Update bug discovery metrics."""
        phase = self.active_phases.get(rock_id)
        if not phase and self.db:
            # Try loading from DB
            phase = await self.db.get_bug_fix_phase(rock_id)
            if phase: self.active_phases[rock_id] = phase

        if not phase: return

        phase.bug_issue_ids = bug_issue_ids
        phase.metrics.total_bugs = len(bug_issue_ids)
        phase.metrics.critical_bugs = len(critical_bug_ids)

        days_elapsed = (datetime.now(UTC) - datetime.fromisoformat(phase.started_at)).days
        phase.metrics.discovery_rate = phase.metrics.total_bugs / max(days_elapsed, 1)

        if self.db:
            await self.db.save_bug_fix_phase(phase)

    async def check_and_extend(self, rock_id: str) -> bool:
        """Check and extend phase if needed."""
        phase = self.active_phases.get(rock_id)
        if not phase: return False

        if phase.should_extend():
            reasons = []
            if phase.metrics.discovery_rate > phase.metrics.high_rate_threshold:
                reasons.append(f"High rate ({phase.metrics.discovery_rate:.1f}/d)")
            if phase.metrics.critical_bugs > phase.metrics.critical_threshold:
                reasons.append(f"{phase.metrics.critical_bugs} critical bugs")
            
            reason = "; ".join(reasons) or "Quality concerns"
            phase.extend_phase(reason)
            
            if self.db:
                await self.db.save_bug_fix_phase(phase)
            
            log_event("bug_fix_phase_extended", {"rock_id": rock_id, "new_end": phase.scheduled_end, "reason": reason}, Path("."))
            return True

        return False

    async def end_phase(self, rock_id: str) -> Optional[str]:
        """End the bug fix phase."""
        phase = self.active_phases.get(rock_id)
        if not phase: return None

        phase.status = BugFixPhaseStatus.COMPLETED
        phase.actual_end = datetime.now(UTC).isoformat()

        phase2_rock_id = None
        if phase.bug_issue_ids:
            phase2_rock_id = f"{rock_id}-phase2"
            phase.phase2_rock_id = phase2_rock_id

        if self.db:
            await self.db.save_bug_fix_phase(phase)

        self.active_phases.pop(rock_id, None)
        log_event("bug_fix_phase_completed", {"rock_id": rock_id, "phase2_rock": phase2_rock_id}, Path("."))
        return phase2_rock_id
