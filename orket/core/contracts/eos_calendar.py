"""Pure EOS calendar calculation over explicit time and immutable baseline values."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime


def _positive_integer(raw: str, default: int) -> int:
    try:
        return max(1, int(raw.strip() or str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class EosSprintBaseline:
    date: str = "2026-02-02"
    quarter: int = 1
    sprint: int = 6

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> EosSprintBaseline:
        return cls(
            date=environment.get("ORKET_EOS_SPRINT_BASE_DATE", "2026-02-02").strip() or "2026-02-02",
            quarter=_positive_integer(environment.get("ORKET_EOS_SPRINT_BASE_QUARTER", "1"), 1),
            sprint=_positive_integer(environment.get("ORKET_EOS_SPRINT_BASE_SPRINT", "6"), 6),
        )

    def current_sprint(self, now: datetime) -> str:
        timezone = now.tzinfo or UTC
        quarter, sprint = self.quarter, self.sprint
        try:
            parsed = datetime.fromisoformat(self.date)
            base = (datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone)
                    if parsed.tzinfo is None else parsed.astimezone(timezone))
        except ValueError:
            base = datetime(2026, 2, 2, tzinfo=timezone)
            quarter, sprint = 1, 6
        total = sprint + (now - base).days // 7
        return f"Q{quarter + (total - 1) // 13} S{(total - 1) % 13 + 1}"
