from __future__ import annotations

from typing import Any


RELEASE_CONFIDENCE_SCORECARD_SCHEMA_VERSION = "1.0"

_EXPECTED_DIMENSIONS = {
    "correctness",
    "degradation",
    "repair_visibility",
    "conformance",
    "trust_signal",
}


def release_confidence_scorecard_snapshot() -> dict[str, Any]:
    return {
        "schema_version": RELEASE_CONFIDENCE_SCORECARD_SCHEMA_VERSION,
        "promotion_threshold": 0.85,
        "dimensions": [
            {"name": "correctness", "weight": 0.3},
            {"name": "degradation", "weight": 0.2},
            {"name": "repair_visibility", "weight": 0.2},
            {"name": "conformance", "weight": 0.2},
            {"name": "trust_signal", "weight": 0.1},
        ],
    }


def validate_release_confidence_scorecard(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    scorecard = dict(payload or release_confidence_scorecard_snapshot())

    threshold = scorecard.get("promotion_threshold")
    if not isinstance(threshold, (float, int)):
        raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_THRESHOLD_SCHEMA")
    threshold_float = float(threshold)
    if not (0.0 <= threshold_float <= 1.0):
        raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_THRESHOLD_RANGE")

    rows = list(scorecard.get("dimensions") or [])
    if not rows:
        raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_DIMENSIONS_EMPTY")

    observed_dimensions: list[str] = []
    weight_total = 0.0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_ROW_SCHEMA")
        name = str(row.get("name") or "").strip()
        if not name:
            raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_DIMENSION_NAME_REQUIRED")
        weight = row.get("weight")
        if not isinstance(weight, (float, int)):
            raise ValueError(f"E_RELEASE_CONFIDENCE_SCORECARD_WEIGHT_SCHEMA:{name}")
        weight_float = float(weight)
        if not (0.0 < weight_float <= 1.0):
            raise ValueError(f"E_RELEASE_CONFIDENCE_SCORECARD_WEIGHT_RANGE:{name}")
        observed_dimensions.append(name)
        weight_total += weight_float

    if len(set(observed_dimensions)) != len(observed_dimensions):
        raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_DUPLICATE_DIMENSION")
    if {token for token in observed_dimensions} != _EXPECTED_DIMENSIONS:
        raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_DIMENSION_SET_MISMATCH")
    if abs(weight_total - 1.0) > 1e-9:
        raise ValueError("E_RELEASE_CONFIDENCE_SCORECARD_WEIGHT_TOTAL_INVALID")

    return tuple(sorted(observed_dimensions))
