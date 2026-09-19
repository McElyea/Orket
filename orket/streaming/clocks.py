"""Adapter observation clocks for stream transport."""
import time
from datetime import UTC, datetime

side_effecting = False


def mono_ts_ms_now() -> int:
    return int(time.monotonic_ns() / 1_000_000)


def wall_ts_now_iso() -> str:
    return datetime.now(UTC).isoformat()
