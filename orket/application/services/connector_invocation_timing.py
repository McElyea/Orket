"""Observe one awaited connector call without influencing authorization/outcome."""
from __future__ import annotations

import logging
from collections.abc import Callable

from orket.core.contracts.invocation_timing import (
    InvocationTiming,
    InvocationTimingProvenance,
    optional_duration_ms,
    unavailable_invocation_timing,
)

logger = logging.getLogger(__name__)


class ConnectorInvocationTimer:
    def __init__(self, monotonic_ns: Callable[[], int], *, clock_ref: str) -> None:
        self._clock, self._clock_ref = monotonic_ns, clock_ref
        self._start, self._reason = self._sample()

    def finish(self) -> InvocationTiming:
        if self._start is None:
            return unavailable_invocation_timing(self._reason, clock=self._clock_ref)
        end, reason = self._sample()
        if end is None:
            return unavailable_invocation_timing(reason, clock=self._clock_ref)
        try:
            duration = optional_duration_ms((end - self._start) / 1_000_000)
        except OverflowError:
            duration = None
        if duration is None:
            logger.warning("Connector timing unavailable: invalid monotonic interval")
            return unavailable_invocation_timing("invalid_monotonic_interval", clock=self._clock_ref)
        return InvocationTiming(duration_ms=duration, timing=InvocationTimingProvenance(
            status="measured", clock=self._clock_ref))

    def _sample(self) -> tuple[int | None, str]:
        try:
            value = self._clock()
        except (OSError, RuntimeError, ValueError, TypeError, OverflowError) as exc:
            logger.warning("Connector monotonic clock unavailable: %s", type(exc).__name__, exc_info=True)
            return None, "clock_unavailable"
        if type(value) is not int:
            logger.warning("Connector timing unavailable: monotonic sample is not an integer")
            return None, "invalid_monotonic_sample"
        return value, ""
