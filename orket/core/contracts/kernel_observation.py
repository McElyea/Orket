"""Explicit immutable Kernel event-time observation; no clock access."""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class KernelObservation:
    observed_at: datetime

    def __post_init__(self) -> None:
        value = self.observed_at
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("E_KERNEL_OBSERVATION_REQUIRES_TIMEZONE")
        object.__setattr__(self, "observed_at", value.astimezone(UTC))

    @property
    def timestamp(self) -> str:
        return self.observed_at.isoformat()
