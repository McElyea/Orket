from __future__ import annotations

from typing import Any


def _sorted_counts(counter: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(counter[key])
        for key in sorted(counter)
        if str(key or "").strip()
    }


def normalize_invalid_projection_field_counts(payload: Any) -> dict[str, dict[str, int]]:
    counts = payload if isinstance(payload, dict) else {}
    return {
        "sqlite": _sorted_counts(dict(counts.get("sqlite") or {})),
        "protocol": _sorted_counts(dict(counts.get("protocol") or {})),
    }


def extract_campaign_invalid_projection_field_counts(payload: Any) -> dict[str, dict[str, int]]:
    campaign = payload if isinstance(payload, dict) else {}
    delta = campaign.get("compatibility_telemetry_delta")
    if not isinstance(delta, dict):
        return {"sqlite": {}, "protocol": {}}
    return normalize_invalid_projection_field_counts(
        {
            "sqlite": dict(delta.get("sqlite_invalid_projection_field_counts") or {}),
            "protocol": dict(delta.get("protocol_invalid_projection_field_counts") or {}),
        }
    )


def invalid_projection_field_counts_present(counts: dict[str, dict[str, int]]) -> bool:
    return any(bool(side_counts) for side_counts in counts.values())


def merge_invalid_projection_field_counts(rows: list[dict[str, Any]], field_name: str) -> dict[str, dict[str, int]]:
    merged: dict[str, dict[str, int]] = {"sqlite": {}, "protocol": {}}
    for row in rows:
        counts = normalize_invalid_projection_field_counts(row.get(field_name))
        for side in ("sqlite", "protocol"):
            for key, value in counts[side].items():
                merged[side][key] = int(merged[side].get(key, 0)) + int(value)
    return normalize_invalid_projection_field_counts(merged)


def render_invalid_projection_field_counts_detail(*, prefix: str, value: Any, counts: dict[str, dict[str, int]]) -> str:
    return (
        f"{prefix}={value}, "
        f"sqlite_invalid_projection_field_counts={counts.get('sqlite') or {}}, "
        f"protocol_invalid_projection_field_counts={counts.get('protocol') or {}}"
    )


__all__ = [
    "extract_campaign_invalid_projection_field_counts",
    "invalid_projection_field_counts_present",
    "merge_invalid_projection_field_counts",
    "normalize_invalid_projection_field_counts",
    "render_invalid_projection_field_counts_detail",
]
