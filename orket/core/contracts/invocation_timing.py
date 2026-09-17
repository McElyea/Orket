"""Measurement provenance is separate from connector outcome or effect truth."""
from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvocationTimingProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["invocation_timing.v1"] = "invocation_timing.v1"
    status: Literal["measured", "unavailable"]
    clock: Literal["python.time.perf_counter_ns", "python.time.monotonic_ns", "injected_monotonic_ns"] | None
    scope: Literal["awaited_connector_invocation"] = "awaited_connector_invocation"
    reason: str | None = None


class InvocationTiming(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    duration_ms: float | None = Field(default=None, strict=True, ge=0, allow_inf_nan=False)
    timing: InvocationTimingProvenance

    @model_validator(mode="after")
    def _validate_measurement(self) -> InvocationTiming:
        if self.timing.status == "measured":
            if self.duration_ms is None or self.timing.clock is None or self.timing.reason is not None:
                raise ValueError("E_INVOCATION_TIMING_MEASUREMENT_REQUIRED")
        elif self.duration_ms is not None or not self.timing.reason:
            raise ValueError("E_INVOCATION_TIMING_UNAVAILABLE_REASON_REQUIRED")
        return self


def unavailable_invocation_timing(reason: str, *, clock: str | None = None) -> InvocationTiming:
    return InvocationTiming(timing=InvocationTimingProvenance(status="unavailable", clock=clock, reason=reason))


def read_invocation_timing(payload: dict[str, Any]) -> InvocationTiming:
    """Old unmeasured connector numbers remain historical, without rewriting them."""
    if "timing" not in payload:
        return unavailable_invocation_timing("legacy_unmeasured")
    return InvocationTiming.model_validate({"duration_ms": payload.get("duration_ms"), "timing": payload["timing"]})


def optional_duration_ms(value: Any) -> float | None:
    """Projection must not turn absent, invalid or fractional timing into zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        duration = float(value)
    except OverflowError:
        return None
    return duration if math.isfinite(duration) and duration >= 0 else None
