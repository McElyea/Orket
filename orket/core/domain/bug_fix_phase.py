"""Deterministic bug-fix window values; application services own persistence and events."""

from __future__ import annotations

import enum
from datetime import datetime, timedelta

from pydantic import BaseModel, Field, model_validator


class BugFixPhaseStatus(enum.StrEnum):
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
    started_at: str
    scheduled_end: str | None = None
    actual_end: str | None = None
    metrics: BugDiscoveryMetrics = Field(default_factory=BugDiscoveryMetrics)
    bug_issue_ids: list[str] = Field(default_factory=list)
    phase2_rock_id: str | None = None
    extensions: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _set_scheduled_end(self) -> BugFixPhase:
        if self.scheduled_end is None:
            start = datetime.fromisoformat(self.started_at)
            self.scheduled_end = (start + timedelta(days=self.initial_duration_days)).isoformat()
        return self

    def should_extend(self) -> bool:
        if self.current_duration_days >= self.max_duration_days:
            return False
        if self.metrics.discovery_rate > self.metrics.high_rate_threshold:
            return True
        return self.metrics.critical_bugs > self.metrics.critical_threshold

    def extend_phase(self, reason: str, added_days: int = 7, *, now: datetime) -> None:
        new_duration = min(self.current_duration_days + added_days, self.max_duration_days)
        actual_added = new_duration - self.current_duration_days
        self.extensions.append(
            {"date": now.isoformat(), "reason": reason, "added_days": str(actual_added)}
        )
        self.current_duration_days = new_duration
        self.scheduled_end = (datetime.fromisoformat(self.started_at) + timedelta(days=new_duration)).isoformat()
        self.status = BugFixPhaseStatus.EXTENDED

    def is_expired(self, *, now: datetime) -> bool:
        if self.scheduled_end is None:
            return False
        return now >= datetime.fromisoformat(self.scheduled_end)
