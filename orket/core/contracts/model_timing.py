"""Pure normalization and provenance for reported provider phase durations."""
from __future__ import annotations

import math
from typing import Any

MODEL_TIMING_SCHEMA_VERSION = "model_provider_timing.v1"


def nonnegative_duration(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        duration = float(value)
    except OverflowError:
        return None
    return duration if math.isfinite(duration) and duration >= 0 else None


def nanoseconds_to_ms(value: Any) -> float | None:
    duration = nonnegative_duration(value)
    return duration / 1_000_000.0 if duration is not None else None


def phase_timing_posture(schema_version: Any, prompt_ms: float | None, predicted_ms: float | None) -> str:
    if prompt_ms is None and predicted_ms is None:
        return "unavailable"
    if schema_version != MODEL_TIMING_SCHEMA_VERSION:
        return "legacy_unverified"
    return "reported" if prompt_ms is not None and predicted_ms is not None else "partial"
