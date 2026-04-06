from __future__ import annotations

from typing import Any

DEMO_PRODUCTION_LABELING_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_LABELS = {
    "production_verified",
    "production_degraded",
    "demo_simulated",
    "demo_scripted",
}
_EXPECTED_SURFACES = {
    "runtime_status_banner",
    "artifact_header",
    "operator_summary",
}


def demo_production_labeling_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": DEMO_PRODUCTION_LABELING_POLICY_SCHEMA_VERSION,
        "labels": sorted(_EXPECTED_LABELS),
        "surfaces": sorted(_EXPECTED_SURFACES),
        "rules": [
            {
                "when_mode": "production",
                "allowed_labels": ["production_verified", "production_degraded"],
            },
            {
                "when_mode": "demo",
                "allowed_labels": ["demo_simulated", "demo_scripted"],
            },
        ],
    }


def validate_demo_production_labeling_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or demo_production_labeling_policy_snapshot())

    labels = [str(token or "").strip() for token in policy.get("labels", [])]
    if not labels or any(not token for token in labels):
        raise ValueError("E_DEMO_PRODUCTION_LABELING_LABELS_EMPTY")
    if {token for token in labels if token} != _EXPECTED_LABELS:
        raise ValueError("E_DEMO_PRODUCTION_LABELING_LABELS_MISMATCH")

    surfaces = [str(token or "").strip() for token in policy.get("surfaces", [])]
    if not surfaces or any(not token for token in surfaces):
        raise ValueError("E_DEMO_PRODUCTION_LABELING_SURFACES_EMPTY")
    if {token for token in surfaces if token} != _EXPECTED_SURFACES:
        raise ValueError("E_DEMO_PRODUCTION_LABELING_SURFACES_MISMATCH")

    rules = list(policy.get("rules") or [])
    if len(rules) != 2:
        raise ValueError("E_DEMO_PRODUCTION_LABELING_RULES_COUNT")
    for row in rules:
        if not isinstance(row, dict):
            raise ValueError("E_DEMO_PRODUCTION_LABELING_RULES_SCHEMA")
        mode = str(row.get("when_mode") or "").strip()
        allowed_labels = [str(token or "").strip() for token in row.get("allowed_labels", [])]
        if mode not in {"production", "demo"}:
            raise ValueError(f"E_DEMO_PRODUCTION_LABELING_MODE_INVALID:{mode or '<empty>'}")
        if not allowed_labels or any(not token for token in allowed_labels):
            raise ValueError(f"E_DEMO_PRODUCTION_LABELING_ALLOWED_LABELS_EMPTY:{mode}")
        for label in allowed_labels:
            if label not in _EXPECTED_LABELS:
                raise ValueError(f"E_DEMO_PRODUCTION_LABELING_ALLOWED_LABEL_INVALID:{mode}")

    return tuple(sorted(_EXPECTED_LABELS))
