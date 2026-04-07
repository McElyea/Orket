from __future__ import annotations

from typing import Any

SAMPLING_DISCIPLINE_GUIDE_SCHEMA_VERSION = "1.0"

_EXPECTED_EVENT_CLASSES = {
    "fallback_event",
    "repair_event",
    "warning_event",
    "override_event",
}
_ALLOWED_SAMPLE_MODES = {"always", "rate"}


def sampling_discipline_guide_snapshot() -> dict[str, Any]:
    return {
        "schema_version": SAMPLING_DISCIPLINE_GUIDE_SCHEMA_VERSION,
        "rows": [
            {
                "event_class": "fallback_event",
                "sample_mode": "always",
                "sample_rate": 1.0,
            },
            {
                "event_class": "repair_event",
                "sample_mode": "always",
                "sample_rate": 1.0,
            },
            {
                "event_class": "warning_event",
                "sample_mode": "rate",
                "sample_rate": 0.5,
            },
            {
                "event_class": "override_event",
                "sample_mode": "always",
                "sample_rate": 1.0,
            },
        ],
    }


def validate_sampling_discipline_guide(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    guide = dict(payload or sampling_discipline_guide_snapshot())
    rows = list(guide.get("rows") or [])
    if not rows:
        raise ValueError("E_SAMPLING_DISCIPLINE_GUIDE_EMPTY")

    observed_event_classes: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_SAMPLING_DISCIPLINE_GUIDE_ROW_SCHEMA")
        event_class = str(row.get("event_class") or "").strip()
        if not event_class:
            raise ValueError("E_SAMPLING_DISCIPLINE_GUIDE_EVENT_CLASS_REQUIRED")

        sample_mode = str(row.get("sample_mode") or "").strip().lower()
        if sample_mode not in _ALLOWED_SAMPLE_MODES:
            raise ValueError(f"E_SAMPLING_DISCIPLINE_GUIDE_SAMPLE_MODE_INVALID:{event_class}")

        sample_rate = row.get("sample_rate")
        if not isinstance(sample_rate, (float, int)):
            raise ValueError(f"E_SAMPLING_DISCIPLINE_GUIDE_SAMPLE_RATE_SCHEMA:{event_class}")
        sample_rate_float = float(sample_rate)
        if not (0.0 <= sample_rate_float <= 1.0):
            raise ValueError(f"E_SAMPLING_DISCIPLINE_GUIDE_SAMPLE_RATE_RANGE:{event_class}")
        if sample_mode == "always" and sample_rate_float != 1.0:
            raise ValueError(f"E_SAMPLING_DISCIPLINE_GUIDE_ALWAYS_RATE_INVALID:{event_class}")
        if sample_mode == "rate" and sample_rate_float in {0.0, 1.0}:
            raise ValueError(f"E_SAMPLING_DISCIPLINE_GUIDE_RATE_MODE_INVALID:{event_class}")

        observed_event_classes.append(event_class)

    if len(set(observed_event_classes)) != len(observed_event_classes):
        raise ValueError("E_SAMPLING_DISCIPLINE_GUIDE_DUPLICATE_EVENT_CLASS")
    if {token for token in observed_event_classes} != _EXPECTED_EVENT_CLASSES:
        raise ValueError("E_SAMPLING_DISCIPLINE_GUIDE_EVENT_CLASS_SET_MISMATCH")

    return tuple(sorted(observed_event_classes))
