"""
Bug Fix Phase Manager - Phase 3: Elegant Failure & Recovery

Domain Service: Manages the post-deployment bug discovery and fixing phase.

When a Rock is marked DONE, it enters a Bug Fix Phase (1-4 weeks, configurable).
If bug discovery rate remains high, the phase is extended up to the max duration.
After the phase ends, remaining bugs are migrated to a "Phase 2" Rock, and the
sandbox is cleaned up.
"""
from __future__ import annotations
from typing import List, Dict, Optional
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field
import enum


class BugFixPhaseStatus(str, enum.Enum):
    """Bug fix phase lifecycle states."""
    ACTIVE = "active"          # Phase in progress, monitoring bugs
    EXTENDED = "extended"      # Phase extended due to high bug rate
    COMPLETED = "completed"    # Phase ended, bugs migrated
    ABORTED = "aborted"        # Phase ended early (e.g., Rock canceled)


class BugDiscoveryMetrics(BaseModel):
    """Metrics for tracking bug discovery rate."""
    total_bugs: int = 0
    critical_bugs: int = 0          # Bugs that block other work
    bugs_found_today: int = 0
    bugs_fixed_today: int = 0
    discovery_rate: float = 0.0     # Bugs per day

    # Thresholds from OrganizationConfig
    high_rate_threshold: float = 5.0  # More than 5 bugs/day = high rate
    critical_threshold: int = 3       # More than 3 blocking bugs = critical


class BugFixPhase(BaseModel):
    """
    Domain Entity: Represents a post-deployment bug fix window.

    Lifecycle:
    1. Rock → DONE → Phase ACTIVE (1 week initial)
    2. Monitor bug discovery rate daily
    3. If rate high → EXTENDED (add 1 week, max 4 weeks total)
    4. Phase ends → COMPLETED, migrate bugs to Phase 2 Rock
    5. Sandbox cleanup triggered
    """
    id: str                         # phase-{rock_id}
    rock_id: str                    # Parent Rock
    status: BugFixPhaseStatus = Field(default=BugFixPhaseStatus.ACTIVE)

    # Duration (from OrganizationConfig)
    initial_duration_days: int = 7    # Start with 1 week
    max_duration_days: int = 28       # Cap at 4 weeks
    current_duration_days: int = 7

    # Timeline
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    scheduled_end: str = Field(default_factory=lambda: (datetime.now(UTC) + timedelta(days=7)).isoformat())
    actual_end: Optional[str] = None

    # Metrics
    metrics: BugDiscoveryMetrics = Field(default_factory=BugDiscoveryMetrics)

    # Bug tracking
    bug_issue_ids: List[str] = Field(default_factory=list)  # Issues filed during this phase
    phase2_rock_id: Optional[str] = None  # Rock created for remaining bugs

    # Extensions
    extensions: List[Dict[str, str]] = Field(default_factory=list)  # [{date, reason, added_days}]

    def should_extend(self) -> bool:
        """
        Determine if phase should be extended based on bug discovery metrics.

        Extends if:
        - Discovery rate > threshold
        - Critical bugs exist
        - Haven't reached max duration yet
        """
        if self.current_duration_days >= self.max_duration_days:
            return False  # Already at max

        if self.metrics.discovery_rate > self.metrics.high_rate_threshold:
            return True  # High bug discovery rate

        if self.metrics.critical_bugs > self.metrics.critical_threshold:
            return True  # Too many blocking bugs

        return False

    def extend_phase(self, reason: str, added_days: int = 7) -> None:
        """
        Extend the phase by additional days.

        Args:
            reason: Why the extension is needed
            added_days: Days to add (default 7)
        """
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
        """Check if phase has reached its scheduled end."""
        return datetime.now(UTC) >= datetime.fromisoformat(self.scheduled_end)


class BugFixPhaseManager:
    """
    Application Service: Manages bug fix phases across all Rocks.

    Responsibilities:
    1. Create phase when Rock → DONE
    2. Monitor bug discovery rate daily
    3. Extend phase if needed (up to max duration)
    4. End phase and migrate bugs to Phase 2 Rock
    5. Trigger sandbox cleanup
    """

    def __init__(self, organization_config: Optional[Dict] = None):
        self.config = organization_config or {}
        self.active_phases: Dict[str, BugFixPhase] = {}  # rock_id -> BugFixPhase

    def start_phase(self, rock_id: str) -> BugFixPhase:
        """
        Begin bug fix phase for a Rock.

        Args:
            rock_id: Rock that was marked DONE

        Returns:
            BugFixPhase entity
        """
        phase_id = f"phase-{rock_id}"

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
            id=phase_id,
            rock_id=rock_id,
            initial_duration_days=initial_days,
            max_duration_days=max_days,
            current_duration_days=initial_days,
            metrics=metrics,
            scheduled_end=(datetime.now(UTC) + timedelta(days=initial_days)).isoformat()
        )

        self.active_phases[rock_id] = phase
        return phase

    def update_metrics(self, rock_id: str, bug_issue_ids: List[str], critical_bug_ids: List[str]) -> None:
        """
        Update bug discovery metrics for a phase.

        Args:
            rock_id: Rock being monitored
            bug_issue_ids: All bug Issue IDs filed
            critical_bug_ids: Subset of bugs that are blocking
        """
        phase = self.active_phases.get(rock_id)
        if not phase:
            return

        phase.bug_issue_ids = bug_issue_ids
        phase.metrics.total_bugs = len(bug_issue_ids)
        phase.metrics.critical_bugs = len(critical_bug_ids)

        # Calculate discovery rate (bugs per day)
        days_elapsed = (datetime.now(UTC) - datetime.fromisoformat(phase.started_at)).days
        if days_elapsed > 0:
            phase.metrics.discovery_rate = phase.metrics.total_bugs / days_elapsed
        else:
            phase.metrics.discovery_rate = phase.metrics.total_bugs  # Day 0

    def check_and_extend(self, rock_id: str) -> bool:
        """
        Check if phase should be extended and extend if needed.

        Returns:
            True if extended, False otherwise
        """
        phase = self.active_phases.get(rock_id)
        if not phase:
            return False

        if phase.should_extend():
            reason = self._get_extension_reason(phase)
            phase.extend_phase(reason, added_days=7)
            return True

        return False

    def end_phase(self, rock_id: str, create_phase2_rock: bool = True) -> Optional[str]:
        """
        End the bug fix phase and migrate remaining bugs.

        Args:
            rock_id: Rock to end phase for
            create_phase2_rock: If True, create Phase 2 Rock for remaining bugs

        Returns:
            Phase 2 Rock ID if created, None otherwise
        """
        phase = self.active_phases.get(rock_id)
        if not phase:
            return None

        phase.status = BugFixPhaseStatus.COMPLETED
        phase.actual_end = datetime.now(UTC).isoformat()

        # Create Phase 2 Rock for remaining bugs
        phase2_rock_id = None
        if create_phase2_rock and phase.bug_issue_ids:
            phase2_rock_id = f"{rock_id}-phase2"
            phase.phase2_rock_id = phase2_rock_id
            # TODO: Integrate with card system to actually create the Rock
            # For now, just record the ID

        # Remove from active tracking
        self.active_phases.pop(rock_id, None)

        return phase2_rock_id

    def get_phase(self, rock_id: str) -> Optional[BugFixPhase]:
        """Retrieve active phase for a Rock."""
        return self.active_phases.get(rock_id)

    def _get_extension_reason(self, phase: BugFixPhase) -> str:
        """Generate human-readable reason for extension."""
        reasons = []

        if phase.metrics.discovery_rate > phase.metrics.high_rate_threshold:
            reasons.append(f"High bug discovery rate ({phase.metrics.discovery_rate:.1f} bugs/day)")

        if phase.metrics.critical_bugs > phase.metrics.critical_threshold:
            reasons.append(f"{phase.metrics.critical_bugs} critical blocking bugs")

        return "; ".join(reasons) if reasons else "Quality concerns"
