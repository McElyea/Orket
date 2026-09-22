"""Pure memory key and explicit observation-time normalization."""

from __future__ import annotations

from datetime import UTC, datetime


def logical_profile_key_name(key: str) -> str:
    parts = str(key or "").split(":", 2)
    if len(parts) == 3 and parts[0] == "ext" and parts[1].strip() and parts[2].strip():
        return parts[2].strip()
    return str(key or "").strip()


def memory_observation_time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("E_MEMORY_OBSERVATION_REQUIRES_TIMEZONE")
    return value.astimezone(UTC)


def memory_timestamp(value: datetime) -> str:
    return memory_observation_time(value).strftime("%Y-%m-%d %H:%M:%S")
